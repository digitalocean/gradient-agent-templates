import pydo
import os
import logging
import argparse
import boto3
import time
import subprocess
import tempfile
import shutil
import secrets
from typing import Optional
from agent.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
)
from agent.tool_schemas import (
    LIST_FILES_TOOL_DESCRIPTION,
    LIST_FILES_INPUT_SCHEMA,
    LIST_FILES_OUTPUT_SCHEMA,
    LOAD_CSV_TOOL_DESCRIPTION,
    LOAD_CSV_INPUT_SCHEMA,
    LOAD_CSV_OUTPUT_SCHEMA,
    GET_COLUMN_INFO_TOOL_DESCRIPTION,
    GET_COLUMN_INFO_INPUT_SCHEMA,
    GET_COLUMN_INFO_OUTPUT_SCHEMA,
    EXECUTE_PANDAS_CODE_TOOL_DESCRIPTION,
    EXECUTE_PANDAS_CODE_INPUT_SCHEMA,
    EXECUTE_PANDAS_CODE_OUTPUT_SCHEMA,
)
from agent.constants import LLAMA_3_3_70B_UUID, EMBEDDING_MODEL_UUID, AGENT_NAME
from dataclasses import dataclass
from dotenv import load_dotenv
import pydo

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
    knowledge_base_uuid: str

    def to_dict(self):
        return {
            "name": self.agent_name,
            "description": self.agent_description,
            "instruction": self.instruction,
            "model_uuid": self.model_uuid,
            "project_id": self.project_id,
            "region": self.region,
            "knowledge_base_uuid": [self.knowledge_base_uuid],
        }


@dataclass
class KBConfig:
    name: str
    project_id: str
    embedding_model_uuid: str
    spaces_bucket: str
    region: str
    database_id: Optional[str] = None

    # For ease of use, we only support local file paths for now
    def to_dict(self):
        return {
            "name": self.name,
            "database_id": self.database_id,
            "embedding_model_uuid": self.embedding_model_uuid,
            "project_id": self.project_id,
            "region": self.region,
            "datasources": [
                {
                    "spaces_data_source": {
                        "bucket_name": self.spaces_bucket,
                        "item_path": "",
                        "region": self.region,
                    }
                }
            ],
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


# Deployment class for the Spaces folder containing KB data
class SpacesDeployer:
    def __init__(
        self,
        token: str,
        project_id: str,
        bucket_name: str,
        region: str = "tor1",
        spaces_access_key: Optional[str] = None,
        spaces_secret_access_key: Optional[str] = None,
    ):
        self.client = pydo.Client(token=token)
        self.project_id = project_id
        self.generated_key = False
        self.bucket_name = bucket_name

        self.access_key = spaces_access_key
        self.secret_key = spaces_secret_access_key

        if self.access_key is None and self.secret_key is None:
            logging.info(
                "Creating access keys for new spaces bucket since no key was provided.."
            )
            self.generated_key = True
            key_response = self._create_spaces_key(bucket_name)
            self.access_key = key_response.get("key", {}).get("access_key")
            self.secret_key = key_response.get("key", {}).get("secret_key")

        if self.secret_key is None or self.access_key is None:
            raise ValueError(
                "Either the spaces access key or the secret key is None. Specify the key correctly, or set both to None to generate a new key"
            )

        session = boto3.session.Session()
        self.boto_client = session.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://{region}.digitaloceanspaces.com",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    # This creates a full access key first in order to create a new bucket
    # Unfortunately, full access keys can't have their permissions updated, so this key gets deleted later for security
    def _create_spaces_key(self, bucket_name):
        return self.client.spaces_key.create(
            body={
                "name": f"Docs Agent Key for {bucket_name}",
                "grants": [{"bucket": "", "permission": "fullaccess"}],
            }
        )

    def upload_folder_to_space(self, folder_path, prefix=""):
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, folder_path)
                s3_key = os.path.join(prefix, relative_path).replace("\\", "/")

                logging.info(
                    f"Uploading {local_path} to s3://{self.bucket_name}/{s3_key}"
                )
                self.boto_client.upload_file(local_path, self.bucket_name, s3_key)

    def create_bucket(self):
        self.boto_client.create_bucket(Bucket=self.bucket_name)
        # When a bucket is created, it is always added to the default project
        # The bucket needs to be moved into the project with the agent and DB
        bucket_urn = f"do:space:{self.bucket_name}"
        # Wait for a few seconds for the bucket creation request to be accepted
        time.sleep(5)
        logging.info("Moving bucket into project...")
        self.client.projects.assign_resources(
            project_id=self.project_id, body={"resources": [bucket_urn]}
        )

    def delete_generated_key(self):
        if self.generated_key:
            # This key was generated as part of the deployment. Delete it
            logging.info("Deleting spaces key generated during deployment..")
            self.client.spaces_key.delete(access_key=self.access_key)

    def wait_for_database_ready(self, kb_database_id: str, max_wait_time: int = 600):
        """
        Wait for the database associated with the knowledge base to be ready.
        Checks every 60 seconds until the database status is 'online' or max_wait_time is reached.
        """
        logging.info("Waiting for database to be ready...")
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                # Get database cluster status
                logging.info("Checking database status...")
                response = self.client.databases.get_cluster(
                    database_cluster_uuid=kb_database_id,
                )

                database_info = response.get("database", {})
                status = database_info.get("status", "unknown")

                logging.info(f"Database status: {status}")

                if status == "online":
                    logging.info("Database is ready!")
                    return True
                elif status == "creating":
                    elapsed = int(time.time() - start_time)
                    remaining = max_wait_time - elapsed
                    logging.info(
                        f"Database still creating (elapsed: {elapsed}s, remaining: {remaining}s). Waiting 60 seconds..."
                    )
                    time.sleep(60)
                elif status == "error":
                    logging.error("Database creation failed with error status")
                    return False
                else:
                    elapsed = int(time.time() - start_time)
                    remaining = max_wait_time - elapsed
                    logging.info(
                        f"Database status: {status} (elapsed: {elapsed}s, remaining: {remaining}s). Waiting 60 seconds..."
                    )
                    time.sleep(60)

            except Exception as e:
                logging.warning(
                    f"Error checking database status: {e}. Waiting 60 seconds..."
                )
                time.sleep(60)

        logging.error(f"Database did not become ready within {max_wait_time} seconds")
        return False


# Deployment class for the agent using Pydo
class AgentDeployer:
    def __init__(self, token: str):
        self.client = pydo.Client(token=token)

    def _list_models(self):
        return self.client.genai.list_models()

    def deploy_kb(self, config: KBConfig):
        logging.info("Creating knowledge base with config:")
        config_dict = config.to_dict()
        logging.info(f"KB config: {config_dict}")

        kb_deployment = self.client.genai.create_knowledge_base(body=config_dict)
        logging.info(f"Knowledge base creation response: {kb_deployment}")
        return kb_deployment

    def index_kb(self, kb_uuid: str):
        logging.info(f"Creating indexing job for knowledge base: {kb_uuid}")
        indexing_body = {
            "data_source_uuids": [],  # Use all datasources
            "knowledge_base_uuid": kb_uuid,
        }
        logging.info(f"Indexing job body: {indexing_body}")

        kb_indexing = self.client.genai.create_indexing_job(body=indexing_body)
        logging.info(f"Indexing job creation response: {kb_indexing}")
        return kb_indexing

    def _deploy_agent(self, config: AgentConfig):
        logging.info("Creating agent with config:")
        config_dict = config.to_dict()
        logging.info(f"Agent config: {config_dict}")

        deployment = self.client.genai.create_agent(
            body=config_dict,
        )
        logging.info(f"Agent creation response: {deployment}")
        return deployment

    def create_template_agent(
        self,
        project_id: str,
        knowledge_base_uuid: str,
        region: str = "tor1",
        agent_name: Optional[str] = AGENT_NAME,
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    ):
        system_instructions = SYSTEM_PROMPT_TEMPLATE
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description="An AI assistant for data analysis and insights from CSV files",
            instruction=system_instructions,
            model_uuid=model_uuid,
            project_id=project_id,
            region=region,
            knowledge_base_uuid=knowledge_base_uuid,
        )
        deployment = self._deploy_agent(config)
        return deployment

    def update_agent_retrieval(self, agent_id: str):
        # Update the retrieval mechanism for the agent
        logging.info(f"Updating agent retrieval settings for agent: {agent_id}")
        retrieval_body = {
            "provide_citations": True,
            "retrieval_method": "RETRIEVAL_METHOD_SUB_QUERIES",
            "temperature": 0.6,
            "k": 10,
            "max_tokens": 1024,
        }
        logging.info(f"Retrieval update body: {retrieval_body}")

        result = self.client.genai.update_agent(
            uuid=agent_id,
            body=retrieval_body,
        )
        logging.info(f"Agent retrieval update response: {result}")
        return result

    def _add_tool_to_agent(self, agent_uuid: str, function_config: AgentFunctionConfig):
        # Add tools to the agent using pydo
        try:
            logging.info(
                f"Adding tool {function_config.function_name} to agent {agent_uuid}"
            )
            logging.info(f"Tool config: {function_config.to_dict()}")
            self.client.genai.attach_agent_function(
                agent_uuid=agent_uuid, body=function_config.to_dict()
            )
            logging.info(
                f"Tool {function_config.function_name} added to agent {agent_uuid} successfully."
            )
        except Exception as e:
            logging.error(
                f"Error adding tool {function_config.function_name} to agent {agent_uuid}: {e}"
            )
            raise

    def add_tools_to_agent(self, agent_id: str, namespace: str):
        # Add the four remaining tools
        tools = [
            (
                "list_files",
                LIST_FILES_TOOL_DESCRIPTION,
                LIST_FILES_INPUT_SCHEMA,
                LIST_FILES_OUTPUT_SCHEMA,
            ),
            (
                "load_csv",
                LOAD_CSV_TOOL_DESCRIPTION,
                LOAD_CSV_INPUT_SCHEMA,
                LOAD_CSV_OUTPUT_SCHEMA,
            ),
            (
                "get_column_info",
                GET_COLUMN_INFO_TOOL_DESCRIPTION,
                GET_COLUMN_INFO_INPUT_SCHEMA,
                GET_COLUMN_INFO_OUTPUT_SCHEMA,
            ),
            (
                "execute_pandas_code",
                EXECUTE_PANDAS_CODE_TOOL_DESCRIPTION,
                EXECUTE_PANDAS_CODE_INPUT_SCHEMA,
                EXECUTE_PANDAS_CODE_OUTPUT_SCHEMA,
            ),
        ]

        logging.info(
            f"Adding {len(tools)} tools to agent {agent_id} in namespace {namespace}"
        )

        for i, (function_name, description, input_schema, output_schema) in enumerate(
            tools, 1
        ):
            logging.info(f"Processing tool {i}/{len(tools)}: {function_name}")
            tool_config = AgentFunctionConfig(
                agent_uuid=agent_id,
                description=description,
                faas_name=f"data-analysis-agent-tools/{function_name}",
                faas_namespace=namespace,
                function_name=function_name,
                input_schema=input_schema,
                output_schema=output_schema,
            )
            self._add_tool_to_agent(agent_id, tool_config)


class FunctionDeployer:
    def __init__(self, token: str, context: str = "default"):
        self.token = token
        self.context = context
        self.client = pydo.Client(token=token)

    def create_namespace(self, namespace: str, region: str):
        # Create a new namespace for the functions
        try:
            fn_namespace = self.client.functions.create_namespace(
                body={"label": namespace, "region": region}
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

    def _export_secrets_to_env(self, tools_path: str, spaces_config: dict):
        # Create an initial .env to create access tokens for the tools
        with open(f"{tools_path}/.env", "w") as f:
            f.write(f"LIST_FILES_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"LOAD_CSV_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"GET_COLUMN_INFO_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"EXECUTE_PANDAS_CODE_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"SPACES_ACCESS_KEY={spaces_config['access_key']}\n")
            f.write(f"SPACES_SECRET_KEY={spaces_config['secret_key']}\n")
            f.write(f"SPACES_BUCKET={spaces_config['bucket_name']}\n")
            f.write(f"SPACES_REGION={spaces_config['region']}\n")

    def deploy_functions(self, namespace: str, region: str, spaces_config: dict):
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
        self._export_secrets_to_env(temp_fn_dir, spaces_config)
        self._connect_doctl_serverless(namespace_id)
        self._deploy_doctl_serverless(temp_fn_dir)
        return namespace_id


def deploy_data_analysis_agent_template(
    token: str,
    project_id: str,
    kb_name: str,
    bucket_name: str,
    data_path: str,
    region: str = "tor1",
    embedding_model: str = EMBEDDING_MODEL_UUID,
    model_uuid: str = LLAMA_3_3_70B_UUID,
    database_id: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    agent_name: Optional[str] = None,
    namespace_label: str = "data-analysis-agent-tools",
):
    try:
        agent_deployer = AgentDeployer(token)

        # First, create a new spaces bucket for the data
        logging.info("Initializing Spaces deployer...")
        spaces_deployer = SpacesDeployer(
            token=token,
            project_id=project_id,
            bucket_name=bucket_name,
            region=region,
            spaces_access_key=access_key,
            spaces_secret_access_key=secret_key,
        )
        logging.info(
            f"Spaces deployer created for bucket: {bucket_name} in region: {region}"
        )

        # Next create a bucket, upload the data to the bucket
        logging.info("Creating a new bucket...")
        spaces_deployer.create_bucket()
        logging.info(f"Bucket created successfully: {bucket_name}")

        logging.info("Uploading data to bucket..")
        spaces_deployer.upload_folder_to_space(data_path)
        logging.info(f"Data uploaded successfully from path: {data_path}")

        # With the bucket created, instantiate a new KB
        logging.info("Creating knowledge base configuration...")
        kb_config = KBConfig(
            name=kb_name,
            project_id=project_id,
            spaces_bucket=bucket_name,
            region=region,
            embedding_model_uuid=embedding_model,
            database_id=database_id,
        )
        logging.info(f"KB config created: {kb_config.to_dict()}")

        logging.info("Deploying knowledge base..")
        kb_deployment = agent_deployer.deploy_kb(kb_config)

        logging.info(f"KB deployment response: {kb_deployment}")
        kb_uuid = kb_deployment.get("knowledge_base", {}).get("uuid")
        kb_database_id = kb_deployment.get("knowledge_base", {}).get("database_id")
        logging.info(f"Extracted KB UUID: {kb_uuid}")
        logging.info(f"Extracted KB Database ID: {kb_database_id}")

        # Check if we need to wait for database to be ready
        if database_id is None:
            # New database was created, wait for it to be ready
            logging.info(
                "New database was created. Waiting for database to be ready..."
            )
            if not spaces_deployer.wait_for_database_ready(kb_database_id):
                logging.error(
                    "Database did not become ready. Proceeding without indexing..."
                )
            else:
                logging.info("Database is ready. Proceeding with indexing...")
        else:
            # Existing database was used
            logging.info("Existing database was used. Proceeding with indexing...")

        # Create indexing job
        logging.info("Creating indexing job on the KB. This may take a few seconds...")
        try:
            logging.info(f"Starting indexing process for KB UUID: {kb_uuid}")
            agent_deployer.index_kb(kb_uuid)
            logging.info("Indexing job created successfully.")
        except Exception as e:
            logging.warning(
                f"Failed to create indexing job: {e}. Agent will still be created but may not have indexed data."
            )
            logging.warning(f"Indexing error details: {str(e)}")

        logging.info("Deploying agent...")
        agent_deployment = agent_deployer.create_template_agent(
            project_id=project_id,
            knowledge_base_uuid=kb_uuid,
            region=region,
            agent_name=agent_name,
            model_uuid=model_uuid,
        )
        logging.info(f"Agent deployment response: {agent_deployment}")
        agent_uuid = agent_deployment.get("agent", {}).get("uuid")
        logging.info(f"Extracted agent UUID: {agent_uuid}")

        # The API to create an agent does not yet support specifying retrieval options
        # To set the retrieval options to improve query performance, we use the update API

        logging.info(
            "Updating agent retrieval settings. This may take a few seconds..."
        )

        # Sending an update request immediately after creating an agent may cause errors
        # However, an update request does not require the agent to finish deployment
        # As such, instead of waiting for deployment to finish, which can take some time, we simply wait for a few seconds

        time.sleep(10)
        agent_deployer.update_agent_retrieval(agent_uuid)

        # Deploy FaaS functions for CSV analysis tools
        logging.info("Deploying FaaS functions for CSV analysis tools...")
        function_deployer = FunctionDeployer(token=token, context="default")
        logging.info("Function deployer created successfully")

        spaces_config = {
            "access_key": spaces_deployer.access_key,
            "secret_key": spaces_deployer.secret_key,
            "bucket_name": spaces_deployer.bucket_name,
            "region": region,
        }

        namespace_id = function_deployer.deploy_functions(
            namespace=namespace_label, region=region, spaces_config=spaces_config
        )
        logging.info(
            f"FaaS functions deployed successfully in namespace: {namespace_id}"
        )

        # Attach tools to agent
        logging.info("Attaching CSV analysis tools to agent...")
        # Add a delay to ensure the agent is fully ready before attaching tools
        time.sleep(5)
        agent_deployer.add_tools_to_agent(agent_id=agent_uuid, namespace=namespace_id)
        logging.info("CSV analysis tools attached to agent successfully.")

        logging.info("=" * 60)
        logging.info("🎉 DATA ANALYSIS AGENT DEPLOYMENT COMPLETED SUCCESSFULLY! 🎉")
        logging.info("=" * 60)
        logging.info(f"Agent UUID: {agent_uuid}")
        logging.info(
            f"Agent URL: https://cloud.digitalocean.com/gen-ai/agents/{agent_uuid}"
        )
        logging.info(f"Knowledge Base UUID: {kb_uuid}")
        logging.info(f"Spaces Bucket: {bucket_name}")
        logging.info(f"Functions Namespace: {namespace_id}")
        logging.info("=" * 60)
        logging.info(
            "Note: It may be a few minutes before your agent is ready to use as its knowledge base may still be indexing."
        )
        logging.info("=" * 60)

    except Exception as e:
        logging.error("=" * 60)
        logging.error("❌ DEPLOYMENT FAILED ❌")
        logging.error("=" * 60)
        logging.error(f"Error type: {type(e).__name__}")
        logging.error(f"Error message: {str(e)}")
        logging.error("=" * 60)
        logging.error("Full traceback:", exc_info=True)
        logging.error("=" * 60)
        raise


def get_arg_or_env(arg_value, env_var, default=None, nullable=True):
    if arg_value is not None:
        return arg_value
    val = os.getenv(env_var, default)
    if not nullable and val is None:
        raise ValueError(f"{env_var} cannot be None. Please specify it.")
    return val


def main():
    parser = argparse.ArgumentParser(description="Deploy data analysis agent")

    parser.add_argument(
        "--env-file", help="Path to a .env file to load environment variables from"
    )
    parser.add_argument("--token", help="API token")
    parser.add_argument("--project-id", help="Project ID")
    parser.add_argument("--kb-name", help="Knowledge base name")
    parser.add_argument("--bucket-name", help="DO Spaces bucket name")
    parser.add_argument(
        "--data-path", help="Local path to data folder containing CSV files"
    )
    parser.add_argument(
        "--region", help="Optional: DigitalOcean region. Defaults to tor1"
    )
    parser.add_argument("--embedding-model", help="Optional: Embedding model UUID")
    parser.add_argument("--model-uuid", help="Optional: LLM model UUID")
    parser.add_argument(
        "--database-id",
        help="Optional: An existing opensearch database ID. If not provided, a new opensearch DB is created.",
    )
    parser.add_argument(
        "--access-key",
        help="Optional: An existing DO Spaces access key with fullaccess",
    )
    parser.add_argument(
        "--secret-key",
        help="Optional: An existing DO Spaces secret key with fullaccess",
    )
    parser.add_argument(
        "--agent-name",
        help=f"Optional: The name of the agent. If not provided, '{AGENT_NAME}' is used",
    )
    parser.add_argument(
        "--namespace-label",
        help="Optional: Namespace label for FaaS functions. Defaults to data-analysis-agent-tools",
    )

    args = parser.parse_args()

    if args.env_file:
        load_dotenv(dotenv_path=args.env_file)

    deploy_data_analysis_agent_template(
        token=get_arg_or_env(args.token, "DIGITALOCEAN_TOKEN", nullable=False),
        project_id=get_arg_or_env(args.project_id, "PROJECT_ID", nullable=False),
        kb_name=get_arg_or_env(args.kb_name, "KB_NAME", nullable=False),
        bucket_name=get_arg_or_env(args.bucket_name, "BUCKET_NAME", nullable=True),
        data_path=get_arg_or_env(args.data_path, "DATA_PATH", nullable=False),
        region=get_arg_or_env(args.region, "REGION", "tor1"),
        embedding_model=get_arg_or_env(
            args.embedding_model, "EMBEDDING_MODEL", EMBEDDING_MODEL_UUID
        ),
        model_uuid=get_arg_or_env(args.model_uuid, "MODEL_UUID", LLAMA_3_3_70B_UUID),
        database_id=get_arg_or_env(args.database_id, "DATABASE_ID"),
        access_key=get_arg_or_env(args.access_key, "SPACES_ACCESS_KEY"),
        secret_key=get_arg_or_env(args.secret_key, "SPACES_SECRET_KEY"),
        agent_name=get_arg_or_env(args.agent_name, "AGENT_NAME"),
        namespace_label=get_arg_or_env(
            args.namespace_label, "NAMESPACE_LABEL", "data-analysis-agent-tools"
        ),
    )


if __name__ == "__main__":
    main()
