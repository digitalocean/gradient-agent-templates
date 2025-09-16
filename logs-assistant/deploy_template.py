import pydo
import os
from typing import Optional
import subprocess
from agent.prompts import (
    SYSTEM_PROMPT,
    GET_LOGS_INPUT_SCHEMA,
    GET_LOGS_TOOL_DESCRIPTION,
    GET_LOGS_OUTPUT_SCHEMA,
)
from agent.constants import LLAMA_3_3_70B_UUID
from dataclasses import dataclass
from dotenv import load_dotenv
import tempfile
import shutil
import secrets
import logging
import argparse
import sys
import time
from gradient import Gradient

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
class DOAuth:
    token: str
    context: str


# Deployment class for the agent using Pydo
class AgentDeployer:
    def __init__(self, token: str):
        self.client = Gradient(access_token=token)

    def _deploy_agent(self, config: AgentConfig):
        deployment = self.client.agents.create(**config.to_dict())
        return deployment

    def create_template_agent(
        self,
        project_id: str,
        region: str = "tor1",
        agent_name: Optional[str] = "Logs Assistant",
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    ):
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description="An AI assistant for analysing DO Application error Logs",
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
            self.client.agents.functions.create(
                path_agent_uuid=agent_uuid,
                body_agent_uuid=function_config.agent_uuid,
                description=function_config.description,
                faas_name=function_config.faas_name,
                faas_namespace=function_config.faas_namespace,
                function_name=function_config.function_name,
                input_schema=function_config.input_schema,
                output_schema=function_config.output_schema,
            )
            logging.info(f"Tool added to agent {agent_uuid} successfully.")
        except Exception as e:
            logging.error(f"Error adding tool to agent {agent_uuid}: {e}")
            raise

    # Add the log tool to the agent
    def add_tools_to_agent(self, agent_id: str, logs_faas_name: str, namespace: str):
        get_logs_tool_config = AgentFunctionConfig(
            agent_uuid=agent_id,
            description=GET_LOGS_TOOL_DESCRIPTION,
            faas_name=logs_faas_name,
            faas_namespace=namespace,
            function_name="get_logs",
            input_schema=GET_LOGS_INPUT_SCHEMA,
            output_schema=GET_LOGS_OUTPUT_SCHEMA,
        )

        self._add_tool_to_agent(agent_id, get_logs_tool_config)


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
            logging.info("Waiting for namespace creation.")
            time.sleep(10)
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

    def _export_secrets_to_env(self, tools_path: str, agent_token: str):
        # Create an intial .env to create access tokens for the tools
        with open(f"{tools_path}/.env", "w") as f:
            f.write(f"GET_LOGS_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"AGENT_TOKEN={agent_token}\n")

    def deploy_functions(self, namespace: str, region: str, agent_token: str):
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
        self._export_secrets_to_env(temp_fn_dir, agent_token)
        self._connect_doctl_serverless(namespace_id)
        self._deploy_doctl_serverless(temp_fn_dir)
        return namespace_id


def deploy_logs_agent_template(
    auth: DOAuth,
    project_id: str,
    agent_token: str,
    region: str = "tor1",
    namespace_label: str = "logs-assistant-template-functions",
    agent_name: Optional[str] = "Logs Assistant",
    model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
):
    logging.info("Starting Logs Assistant Agent template deployment...")

    # Step 1: Deploy the functions
    logging.info("Deploying functions...")
    function_deployer = FunctionDeployer(token=auth.token, context=auth.context)
    namespace_id = function_deployer.deploy_functions(
        namespace=namespace_label, region=region, agent_token=agent_token
    )
    logging.info(f"Functions deployed in namespace: {namespace_id}")

    # Step 2: Create the agent
    logging.info("Creating agent...")
    agent_deployer = AgentDeployer(token=auth.token)
    agent = agent_deployer.create_template_agent(
        project_id=project_id,
        region=region,
        agent_name=agent_name,
        model_uuid=model_uuid,
    )
    logging.info(f"Agent created: {agent}")

    # Step 3: Attach the tools to the agent
    logging.info("Attaching tools to the agent...")
    agent_deployer.add_tools_to_agent(
        agent_id=agent.agent.uuid,
        logs_faas_name="logs-assistant-tools/get_logs",
        namespace=namespace_id,
    )
    logging.info("Tools attached to the agent successfully.")
    logging.info("Logs Agent template deployment completed successfully.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Deploy SQL Agent Template to DigitalOcean",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --token YOUR_TOKEN --context DO_CONTEXT --project-id PROJECT_ID --agent-token AGENT_DO_TOKEN --agent-name LogsAssistant --model-uuid MODEL_UUID

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

    parser.add_argument(
        "--namespace-label",
        help='Namespace label to use for the deployed functions (default: "logs-assistant-template-functions")',
        default="logs-assistant-template-functions",
    )

    parser.add_argument(
        "--agent-token", help="DigitalOcean API token used by the agent"
    )

    parser.add_argument(
        "--agent-name",
        help='Agent Name (default: "Logs Assistant")',
        default="Logs Assistant",
    )

    parser.add_argument(
        "--model-uuid",
        help="The UUID of the model to use (defaults to the UUID for Llama 3.3 70B)",
        default=LLAMA_3_3_70B_UUID,
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
        print(f"Loaded environment from: {args.env_file}")
    elif args.env_file != ".env":
        print(f"Warning! Environment file '{args.env_file}' not found.")

    # Get configuration values
    token = get_config_value(args, "token", "DIGITALOCEAN_TOKEN")
    context = (
        get_config_value(args, "context", "DIGITALOCEAN_CONTEXT", required=False)
        or "default"
    )
    project_id = get_config_value(args, "project-id", "PROJECT_ID")
    agent_token = get_config_value(args, "agent-token", "AGENT_TOKEN")
    agent_name = get_config_value(args, "agent-name", "AGENT_NAME")
    model_uuid = get_config_value(args, "model-uuid", "MODEL_UUID")
    namespace_label = get_config_value(args, "namespace-label", "NAMESPACE_LABEL")

    # Create configuration objects
    auth = DOAuth(
        token=token,
        context=context,
    )

    # Deploy the SQL agent
    try:
        print("Deploying Logs Assistant Agent Template...")
        deploy_logs_agent_template(
            auth=auth,
            project_id=project_id,
            agent_token=agent_token,
            namespace_label=namespace_label,
            agent_name=agent_name,
            model_uuid=model_uuid,
        )
        print("Logs Assistant Agent Template deployed successfully!")
    except Exception as e:
        print(f"Error during deployment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
