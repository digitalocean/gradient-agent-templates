import pydo
import os
import logging
import argparse
import boto3
import time
from typing import Optional
from agent.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
)
from agent.constants import LLAMA_3_3_70B_UUID, EMBEDDING_MODEL_UUID, AGENT_NAME
from dataclasses import dataclass
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

import os


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
                f"Either the spaces access key or the secret key is None. Specify the key correctly, or set both to None to generate a new key"
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


# Deployment class for the agent using Pydo
class AgentDeployer:
    def __init__(self, token: str):
        self.client = pydo.Client(token=token)

    def _list_models(self):
        return self.client.genai.list_models()

    def deploy_kb(self, config: KBConfig):
        kb_deployment = self.client.genai.create_knowledge_base(body=config.to_dict())
        return kb_deployment

    def index_kb(self, kb_uuid: str):
        kb_indexing = self.client.genai.create_indexing_job(
            body={
                "data_source_uuids": [],  # Use all datasources
                "knowledge_base_uuid": kb_uuid,
            }
        )
        return kb_indexing

    def _deploy_agent(self, config: AgentConfig):
        deployment = self.client.genai.create_agent(
            body=config.to_dict(),
        )
        return deployment

    def create_template_agent(
        self,
        project_id: str,
        product_name: str,
        product_description: str,
        knowledge_base_uuid: str,
        region: str = "tor1",
        agent_name: Optional[str] = AGENT_NAME,
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    ):

        system_instructions = SYSTEM_PROMPT_TEMPLATE.format(
            product_name=product_name,
            product_description=product_description,
        )
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description=f"An AI assistant for to answer product documentation for {product_name}",
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
        return self.client.genai.update_agent(
            uuid=agent_id,
            body={
                "provide_citations": True,
                "retrieval_method": "RETRIEVAL_METHOD_SUB_QUERIES",
                "temperature": 0.6,
                "k": 10,
                "max_tokens": 1024,
            },
        )


def deploy_pdocs_agent_template(
    token: str,
    project_id: str,
    product_name: str,
    product_description: str,
    kb_name: str,
    bucket_name: str,
    documentation_path: str,
    region: str = "tor1",
    embedding_model: str = EMBEDDING_MODEL_UUID,
    model_uuid: str = LLAMA_3_3_70B_UUID,
    database_id: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    agent_name: Optional[str] = None,
):
    try:
        agent_deployer = AgentDeployer(token)

        # First, create a new spaces bucket for the data
        spaces_deployer = SpacesDeployer(
            token=token,
            project_id=project_id,
            bucket_name=bucket_name,
            region=region,
            spaces_access_key=access_key,
            spaces_secret_access_key=secret_key,
        )

        # Next create a bucket, upload the data to the bucket, and delete any temporary keys created in the process
        logging.info("Creating a new bucket...")
        spaces_deployer.create_bucket()
        logging.info("Uploading data to bucket..")
        spaces_deployer.upload_folder_to_space(documentation_path)
        spaces_deployer.delete_generated_key()

        # With the bucket created, instantiate a new KB
        kb_config = KBConfig(
            name=kb_name,
            project_id=project_id,
            spaces_bucket=bucket_name,
            region=region,
            embedding_model_uuid=embedding_model,
            database_id=database_id,
        )
        logging.info("Deploying knowledge base..")
        kb_deployment = agent_deployer.deploy_kb(kb_config)
        kb_uuid = kb_deployment.get("knowledge_base", {}).get("uuid")

        if database_id is not None:
            logging.info(
                "An existing database was used. Creating an indexing job on the KB. This may take a few seconds..."
            )
            # As a precaution, wait for a few seconds before sending the request to trigger indexing
            time.sleep(5)
            agent_deployer.index_kb(kb_uuid)

        logging.info("Deploying agent...")
        agent_deployment = agent_deployer.create_template_agent(
            project_id=project_id,
            product_name=product_name,
            product_description=product_description,
            knowledge_base_uuid=kb_uuid,
            region=region,
            agent_name=agent_name,
            model_uuid=model_uuid,
        )
        agent_uuid = agent_deployment.get("agent", {}).get("uuid")

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

        logging.info(
            f"Product documentation agent deployment completed!\nYou can find your agent at : https://cloud.digitalocean.com/gen-ai/agents/{agent_uuid}\nNote:It may be a few minutes before your agent is ready to use as its knowledge base may still be indexing."
        )

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        raise


def get_arg_or_env(arg_value, env_var, default=None, nullable=True):
    if arg_value is not None:
        return arg_value
    val = os.getenv(env_var, default)
    if not nullable and val is None:
        raise ValueError(f"{env_var} cannot be None. Please specify it.")
    return val


def main():
    parser = argparse.ArgumentParser(description="Deploy product documentation agent")

    parser.add_argument(
        "--env-file", help="Path to a .env file to load environment variables from"
    )
    parser.add_argument("--token", help="API token")
    parser.add_argument("--project-id", help="Project ID")
    parser.add_argument("--product-name", help="Name of the product")
    parser.add_argument("--product-description", help="Description of the product")
    parser.add_argument("--kb-name", help="Knowledge base name")
    parser.add_argument("--bucket-name", help="DO Spaces bucket name")
    parser.add_argument(
        "--documentation-path", help="Local path to documentation folder"
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

    args = parser.parse_args()

    if args.env_file:
        load_dotenv(dotenv_path=args.env_file)

    deploy_pdocs_agent_template(
        token=get_arg_or_env(args.token, "DIGITALOCEAN_TOKEN", nullable=False),
        project_id=get_arg_or_env(args.project_id, "PROJECT_ID", nullable=False),
        product_name=get_arg_or_env(args.product_name, "PRODUCT_NAME", nullable=False),
        product_description=get_arg_or_env(
            args.product_description, "PRODUCT_DESCRIPTION", nullable=False
        ),
        kb_name=get_arg_or_env(args.kb_name, "KB_NAME", nullable=False),
        bucket_name=get_arg_or_env(args.bucket_name, "BUCKET_NAME", nullable=False),
        documentation_path=get_arg_or_env(
            args.documentation_path, "DOCUMENTATION_PATH", nullable=False
        ),
        region=get_arg_or_env(args.region, "REGION", "tor1"),
        embedding_model=get_arg_or_env(
            args.embedding_model, "EMBEDDING_MODEL", EMBEDDING_MODEL_UUID
        ),
        model_uuid=get_arg_or_env(args.model_uuid, "MODEL_UUID", LLAMA_3_3_70B_UUID),
        database_id=get_arg_or_env(args.database_id, "DATABASE_ID"),
        access_key=get_arg_or_env(args.access_key, "SPACES_ACCESS_KEY"),
        secret_key=get_arg_or_env(args.secret_key, "SPACES_SECRET_KEY"),
        agent_name=get_arg_or_env(args.agent_name, "AGENT_NAME"),
    )


if __name__ == "__main__":
    main()
