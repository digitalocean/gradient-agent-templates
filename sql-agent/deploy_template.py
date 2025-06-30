import pydo
import os
from typing import Optional
import subprocess

from agent.prompts import (
    SYSTEM_PROMPT,
    GET_SCHEMA_TOOL_DESCRIPTION,
    GET_SCHEMA_INPUT_SCHEMA,
    GET_SCHEMA_OUTPUT_SCHEMA,
    EXECUTE_QUERY_TOOL_DESCRIPTION,
    EXECUTE_QUERY_INPUT_SCHEMA,
    EXECUTE_QUERY_OUTPUT_SCHEMA,
)
from agent.constants import LLAMA_3_3_70B_UUID
from setup.database_setup import create_agent_user
from dataclasses import dataclass
from dotenv import load_dotenv
import tempfile
import shutil
import secrets
import logging
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


@dataclass
class AgentConfig:
    agent_name: str
    agent_description: str
    model_uuid: str
    project_id: str
    region: str
    instruction: str

    def to_dict(self):
        return {
            "name": self.agent_name,
            "description": self.agent_description,
            "instruction": self.instruction,
            "model_uuid": self.model_uuid,
            "project_id": self.project_id,
            "region": self.region,
        }


@dataclass
class AgentFunctionConfig:
    agent_uuid: str
    description: str
    faas_name: str
    faas_namespace: str
    function_name: str
    input_schema: dict
    output_schema: dict

    def to_dict(self):
        return {
            "agent_uuid": self.agent_uuid,
            "description": self.description,
            "faas_name": self.faas_name,
            "faas_namespace": self.faas_namespace,
            "function_name": self.function_name,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


@dataclass
class DBConfig:
    host: str
    port: int
    db_name: str
    user_id: str
    password: str

    def to_dict(self):
        return {
            "host": self.host,
            "port": self.port,
            "db_name": self.db_name,
            "user_id": self.user_id,
            "password": self.password,
        }


@dataclass
class DOAuth:
    token: str
    context: str


# Deployment class for the agent using Pydo
class AgentDeployer:
    def __init__(self, token: str):
        self.client = pydo.Client(token=token)

    def _deploy_agent(self, config: AgentConfig):
        deployment = self.client.genai.create_agent(
            body=config.to_dict(),
        )
        return deployment

    def create_template_agent(
        self,
        project_id: str,
        region: str = "tor1",
        agent_name: Optional[str] = "SQL Assistant",
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    ):
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description="An AI assistant for SQL databases",
            instruction=SYSTEM_PROMPT,
            model_uuid=model_uuid,
            project_id=project_id,
            region=region,
        )
        deployment = self._deploy_agent(config)
        return deployment

    def _add_tool_to_agent(self, agent_uuid: str, function_config: AgentFunctionConfig):
        # Add tools to the agent
        try:
            self.client.genai.attach_agent_function(
                agent_uuid=agent_uuid, body=function_config.to_dict()
            )
            logging.info(f"Tool added to agent {agent_uuid} successfully.")
        except Exception as e:
            logging.error(f"Error adding tool to agent {agent_uuid}: {e}")
            raise

    # Add the schema tool and the query execution tool to the agent
    def add_tools_to_agent(
        self, agent_id: str, schema_faas_name: str, query_faas_name: str, namespace: str
    ):
        schema_tool_config = AgentFunctionConfig(
            agent_uuid=agent_id,
            description=GET_SCHEMA_TOOL_DESCRIPTION,
            faas_name=schema_faas_name,
            faas_namespace=namespace,
            function_name="get_schema",
            input_schema=GET_SCHEMA_INPUT_SCHEMA,
            output_schema=GET_SCHEMA_OUTPUT_SCHEMA,
        )

        query_tool_config = AgentFunctionConfig(
            agent_uuid=agent_id,
            description=EXECUTE_QUERY_TOOL_DESCRIPTION,
            faas_name=query_faas_name,
            faas_namespace=namespace,
            function_name="execute_query",
            input_schema=EXECUTE_QUERY_INPUT_SCHEMA,
            output_schema=EXECUTE_QUERY_OUTPUT_SCHEMA,
        )

        self._add_tool_to_agent(agent_id, schema_tool_config)
        self._add_tool_to_agent(agent_id, query_tool_config)


class FunctionDeployer:
    def __init__(self, token: str, context: str):
        self.token = token
        self.context = context
        self.client = pydo.Client(token=token)

    def create_namespace(self, namespace: str, region: str):
        # Create a new namespace for the functions
        try:
            fn_namespace = self.client.functions.create_namespace(
                body={"" "label": namespace, "region": region}
            )
            return fn_namespace
        except Exception as e:
            logging.error(f"Error creating namespace '{namespace}': {e}")
            raise

    def _login_doctl(self):
        command = [
            "doctl",
            "auth",
            "init",
            "-t",
            self.token,
            "--context",
            self.context,
            "--interactive",
            "false",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            if result.returncode == 0:
                logging.info("doctl login successful")
            else:
                logging.error(f"Error logging in to doctl: {result.stderr}")
                raise Exception(f"doctl login failed: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"doctl login failed: {e.stderr}")
            raise Exception(f"doctl login failed: {e.stderr}")

    def _connect_doctl_serverless(self, namespace: str):
        command = [
            "doctl",
            "serverless",
            "connect",
            namespace,
            "-t",
            self.token,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            logging.info(f"Doctl output:{result.stdout}")
            if result.returncode == 0:
                logging.info("doctl serverless connection successful")
            else:
                logging.error(f"Error connecting to serverless doctl: {result.stderr}")
                raise Exception(f"doctl serverless connect failed: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"doctl serverless connection failed: {e.stderr}")
            raise Exception(f"doctl serverless connect failed: {e.stderr}")

    def _deploy_doctl_serverless(self, fn_dir: str):
        command = [
            "doctl",
            "serverless",
            "deploy",
            fn_dir,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            logging.info(f"Doctl output:{result.stdout}")
            if result.returncode == 0:
                logging.info("doctl deploy successful")
            else:
                logging.error(f"Error deploying to doctl serverless: {result.stderr}")
                raise Exception(f"doctl serverless deploy failed: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"doctl serverless failed: {e.stderr}")
            raise Exception(f"doctl serverless deploy failed: {e.stderr}")

    def _copy_tools_to_temp(self) -> str:
        temp_dir = tempfile.mkdtemp()
        dest = os.path.join(temp_dir, "tools")
        shutil.copytree("./tools", dest)
        return dest

    def _export_secrets_to_env(self, tools_path: str, db_config: DBConfig):
        # Create an intial .env to create access tokens for the tools
        with open(f"{tools_path}/.env", "w") as f:
            f.write(f"GET_SCHEMA_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"EXECUTE_QUERY_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"DB_HOST={db_config.host}\n")
            f.write(f"DB_PORT={db_config.port}\n")
            f.write(f"DB_NAME={db_config.db_name}\n")
            f.write(f"DB_AGENT_USER={db_config.user_id}\n")
            f.write(f"DB_AGENT_PASSWORD={db_config.password}\n")

    def deploy_functions(self, namespace: str, region: str, db_config: DBConfig):
        fn_namespace = self.create_namespace(namespace, region)
        try:
            namespace_id = fn_namespace.get("namespace", {}).get("namespace")
            if not namespace_id:
                raise Exception(
                    f"Failed to create namespace '{namespace}' in region '{region}: {fn_namespace}'."
                )
        except Exception as e:
            logging.error(f"Error creating namespace '{namespace}': {e}")
            raise

        self._login_doctl()
        temp_fn_dir = self._copy_tools_to_temp()
        self._export_secrets_to_env(temp_fn_dir, db_config)
        self._connect_doctl_serverless(namespace_id)
        self._deploy_doctl_serverless(temp_fn_dir)
        return namespace_id


def deploy_sql_agent_template(
    auth: DOAuth,
    project_id: str,
    db_config: DBConfig,
    region: str = "tor1",
    namespace_label: str = "sql-agent-template-functions",
    agent_name: Optional[str] = "SQL Assistant",
    model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    agent_user_id: Optional[str] = "ai_agent",
    agent_user_password: Optional[str] = None,
):
    # Deployment happens in the following order:
    # 1. A READ-ONLY user is created in the database with the provided credentials
    # 2. The functions used by the agent are deployed via DOCTL into a new namespace
    # 3. The agent is created using the Pydo client
    # 4. The tools are attached to the agent

    logging.info("Starting SQL Agent template deployment...")
    if agent_user_id is None:
        agent_user_id = "ai_agent"
    if agent_user_password is None:
        agent_user_password = secrets.token_urlsafe(16)

    # Step 1: Create the agent user in the database
    logging.info("Creating agent user in the database...")
    create_agent_user(
        database_name=db_config.db_name,
        database_host=db_config.host,
        database_port=db_config.port,
        database_root_user=db_config.user_id,
        database_root_password=db_config.password,
        agent_user=agent_user_id,
        agent_password=agent_user_password,
    )

    # Step 2: Deploy the functions
    logging.info("Deploying functions...")
    function_deployer = FunctionDeployer(token=auth.token, context=auth.context)
    # Create a new database config for the agent's user
    agent_db_config = DBConfig(
        host=db_config.host,
        port=db_config.port,
        db_name=db_config.db_name,
        user_id=agent_user_id,
        password=agent_user_password,
    )
    namespace_id = function_deployer.deploy_functions(
        namespace=namespace_label, region=region, db_config=agent_db_config
    )
    logging.info(f"Functions deployed in namespace: {namespace_id}")

    # Step 3: Create the agent
    logging.info("Creating agent...")
    agent_deployer = AgentDeployer(token=auth.token)
    agent = agent_deployer.create_template_agent(
        project_id=project_id,
        region=region,
        agent_name=agent_name,
        model_uuid=model_uuid,
    )
    logging.info(f"Agent created: {agent}")

    # Step 4: Attach the tools to the agent
    logging.info("Attaching tools to the agent...")
    agent_deployer.add_tools_to_agent(
        agent_id=agent.get("agent", {}).get("uuid"),
        schema_faas_name="sql-agent-tools/get_schema",
        query_faas_name="sql-agent-tools/execute_query",
        namespace=namespace_id,
    )
    logging.info("Tools attached to the agent successfully.")
    logging.info("SQL Agent template deployment completed successfully.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Deploy SQL Agent Template to DigitalOcean",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --token YOUR_TOKEN --context DO_CONTEXT --project-id PROJECT_ID --db-host localhost --db-port 5432 --db-name mydb --db-admin-user admin --db-admin-password secret

  %(prog)s --env-file custom.env
        """,
    )

    # Environment file option
    parser.add_argument(
        "--env-file",
        help="Path to .env file (default: .env in current directory)",
        default=".env",
    )

    # DigitalOcean Authentication
    parser.add_argument(
        "--token", help="DigitalOcean API token (or set DIGITALOCEAN_TOKEN env var)"
    )

    parser.add_argument(
        "--context",
        help="DigitalOcean context",
    )

    # Project configuration
    parser.add_argument(
        "--project-id", help="DigitalOcean project ID (or set PROJECT_ID env var)"
    )

    parser.add_argument(
        "--region",
        help='Deployment region (default: "tor1")',
    )

    # Database configuration
    db_group = parser.add_argument_group("Database Configuration")
    db_group.add_argument("--db-host", help="Database host (or set DB_HOST env var)")

    db_group.add_argument(
        "--db-port", type=int, help="Database port (or set DB_PORT env var)"
    )

    db_group.add_argument("--db-name", help="Database name (or set DB_NAME env var)")

    db_group.add_argument(
        "--db-admin-user", help="Database admin user (or set DB_ADMIN_USER env var)"
    )

    db_group.add_argument(
        "--db-admin-password",
        help="Database admin password (or set DB_ADMIN_PASSWORD env var)",
    )

    # Agent configuration
    agent_group = parser.add_argument_group("Agent Configuration")
    agent_group.add_argument(
        "--namespace-label",
        help='Kubernetes namespace label (default: "template-agent-sql")',
    )

    agent_group.add_argument(
        "--agent-name",
        help='Agent display name (default: "Template Agent : SQL Assistant")',
    )

    agent_group.add_argument(
        "--agent-user-id",
        help='Agent user ID (default: "sql-agent")',
    )

    agent_group.add_argument(
        "--agent-user-password", help="Agent user password (optional)"
    )

    # Utility options
    parser.add_argument(
        "--dry-run", action="store_true", help="Show configuration without deploying"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    return parser.parse_args()


def get_config_value(args, arg_name, env_name, required=True):
    """Get configuration value from args or environment variables."""
    value = getattr(args, arg_name.replace("-", "_"), None)
    if value is None:
        value = os.getenv(env_name)

    if required and value is None:
        print(
            f"Error: {arg_name} is required. Provide via --{arg_name} or {env_name} environment variable."
        )
        sys.exit(1)

    return value


def main():
    args = parse_args()

    # Load environment file if it exists
    if os.path.exists(args.env_file):
        load_dotenv(args.env_file)
        if args.verbose:
            print(f"Loaded environment from: {args.env_file}")
    elif args.env_file != ".env":
        print(f"Warning: Environment file '{args.env_file}' not found.")

    # Get configuration values
    token = get_config_value(args, "token", "DIGITALOCEAN_TOKEN")
    context = (
        get_config_value(args, "context", "DIGITALOCEAN_CONTEXT", required=False)
        or "default"
    )
    project_id = get_config_value(args, "project-id", "PROJECT_ID")

    # Database configuration
    db_host = get_config_value(args, "db-host", "DB_HOST")
    db_port = get_config_value(args, "db-port", "DB_PORT")
    db_name = get_config_value(args, "db-name", "DB_NAME")
    db_admin_user = get_config_value(args, "db-admin-user", "DB_ADMIN_USER")
    db_admin_password = get_config_value(args, "db-admin-password", "DB_ADMIN_PASSWORD")

    # Convert db_port to int if it's a string
    if isinstance(db_port, str):
        try:
            db_port = int(db_port)
        except ValueError:
            print(f"Error: DB_PORT must be a valid integer, got: {db_port}")
            sys.exit(1)

    # Agent configuration
    region = get_config_value(args, "region", "REGION", required=False)
    namespace_label = get_config_value(
        args, "namespace-label", "NAMESPACE_LABEL", required=False
    )
    agent_name = get_config_value(args, "agent-name", "AGENT_NAME", required=False)
    agent_user_id = get_config_value(
        args, "agent-user-id", "AGENT_USER_ID", required=False
    )
    agent_user_password = get_config_value(
        args, "agent-user-password", "AGENT_USER_PASSWORD", required=False
    )

    if args.verbose:
        print("Configuration:")
        print(
            f"  DigitalOcean Token: {'*' * (len(token) - 4) + token[-4:] if token else 'Not set'}"
        )
        print(f"  Context: {context}")
        print(f"  Project ID: {project_id}")
        print(f"  Region: {region}")
        print(f"  Database Host: {db_host}")
        print(f"  Database Port: {db_port}")
        print(f"  Database Name: {db_name}")
        print(f"  Database Admin User: {db_admin_user}")
        print(
            f"  Database Admin Password: {'*' * len(db_admin_password) if db_admin_password else 'Not set'}"
        )
        print(f"  Namespace Label: {namespace_label}")
        print(f"  Agent Name: {agent_name}")
        print(f"  Agent User ID: {agent_user_id}")
        print(f"  Agent User Password: {'Set' if agent_user_password else 'Not set'}")
        print()

    if args.dry_run:
        print("Dry run mode - configuration validated successfully.")
        print("Would deploy SQL Agent with the above configuration.")
        return

    # Create configuration objects
    auth = DOAuth(
        token=token,
        context=context,
    )

    db_config = DBConfig(
        host=db_host,
        port=db_port,
        db_name=db_name,
        user_id=db_admin_user,
        password=db_admin_password,
    )

    # Deploy the SQL agent
    try:
        print("Deploying SQL Agent Template...")
        deploy_sql_agent_template(
            auth=auth,
            project_id=project_id,
            db_config=db_config,
            region=region,
            namespace_label=namespace_label,
            agent_name=agent_name,
            agent_user_id=agent_user_id,
            agent_user_password=agent_user_password,
        )
        print("SQL Agent Template deployed successfully!")
    except Exception as e:
        print(f"Error during deployment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
