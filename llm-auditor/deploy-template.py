import pydo
import os
from typing import Optional, List
import time
import subprocess
from agents.constants import (
    LLAMA_3_3_70B_UUID,
    CRITIC_AGENT_NAME,
    AUDITOR_AGENT_NAME,
    REVISOR_AGENT_NAME,
    DEFAULT_REGION,
    POLL_FREQUENCY,
    MAX_WAIT_TIME,
)
from agents.auditor.prompts import (
    AUDITOR_PROMPT,
    CRITIC_DESCRIPTION,
    CRITIC_INPUT_SCHEMA,
    CRITIC_OUTPUT_SCHEMA,
    REVISOR_DESCRIPTION,
    REVISOR_INPUT_SCHEMA,
    REVISOR_OUTPUT_SCHEMA,
)
from agents.critic.prompts import (
    CRITIC_PROMPT,
    SEARCH_DESCRIPTION,
    SEARCH_INPUT_SCHEMA,
    SEARCH_OUTPUT_SCHEMA,
)
from agents.revisor.prompts import REVISER_PROMPT

from dataclasses import dataclass
from dotenv import load_dotenv
import tempfile
import shutil
import secrets
import logging
import argparse
import json
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
    knowledge_base_uuids: Optional[List[str]] = None

    def to_dict(self):
        config = {
            "name": self.agent_name,
            "description": self.agent_description,
            "instruction": self.instruction,
            "model_uuid": self.model_uuid,
            "project_id": self.project_id,
            "region": self.region,
        }
        if self.knowledge_base_uuids is not None:
            config["knowledge_base_uuid"] = self.knowledge_base_uuids
        return config


@dataclass
class DeployedAgentInfo:
    agent_uuid: str
    agent_url: str
    agent_key: Optional[str] = None


def _create_info_from_deployment(deployment: dict, require_url: bool = True):
    agent_deployment = deployment.get("agent", {})
    url = agent_deployment.get("url") or agent_deployment.get("deployment").get("url")
    uuid = agent_deployment.get("uuid")
    if uuid is None:
        raise ValueError(f"Invalid UUID: {uuid} for agent deployment")
    if url is None and require_url:
        raise ValueError(f"Invalid URL: {url} for agent deployment")
    return DeployedAgentInfo(agent_uuid=uuid, agent_url=url)


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


# Deployment class for the agents using Pydo
class AgentDeployer:
    def __init__(self, token: str):
        self.client = pydo.Client(token=token)

    def _deploy_agent(self, config: AgentConfig):
        deployment = self.client.genai.create_agent(
            body=config.to_dict(),
        )
        return deployment

    def _create_component_agent(
        self,
        project_id: str,
        agent_name: str,
        agent_description: str,
        prompt: str,
        region: str = "tor1",
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
        kb_uuids: Optional[List[str]] = None,
    ):
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description=agent_description,
            instruction=prompt,
            model_uuid=model_uuid,
            project_id=project_id,
            region=region,
            knowledge_base_uuids=kb_uuids,
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

    def _has_url(self, agent_uuid: str):
        print(f"Checking status of {agent_uuid}")
        agent_response = self.client.genai.get_agent(agent_uuid).get("agent")
        has_url = agent_response.get("url") or agent_response.get("deployment").get(
            "url"
        )
        if has_url:
            return True
        return False

    def _wait_till_ready(
        self,
        critic_id: str,
        revisor_id: str,
        poll_frequency: int = POLL_FREQUENCY,
        max_wait_time: int = MAX_WAIT_TIME,
    ):
        # We need to wait till the critic and revisor are deployed so they have URLs. This is required in order to invoke them downstream as functions later
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            logging.info("Polling status of agents..")
            if self._has_url(critic_id) and self._has_url(revisor_id):
                return True
            time.sleep(poll_frequency)
        raise Exception(
            f"Agents did not finish deployment within {max_wait_time} seconds."
        )

    def create_agents(
        self,
        project_id: str,
        auditor_agent_name: str = AUDITOR_AGENT_NAME,
        critic_agent_name: str = CRITIC_AGENT_NAME,
        revisor_agent_name: str = REVISOR_AGENT_NAME,
        region: str = DEFAULT_REGION,
        model_uuid: str = LLAMA_3_3_70B_UUID,
        reference_kbs: Optional[List[str]] = None,
    ):
        # This function deploys three agents - the main auditor, the critic, and the revisor, and returns the ID of each of them
        logging.info("Creating auditor agent..")
        auditor_agent_deployment = self._create_component_agent(
            project_id=project_id,
            agent_name=auditor_agent_name,
            agent_description="The Auditor agent used to check the factual validity of a question and answer pair.",
            prompt=AUDITOR_PROMPT,
            region=region,
            model_uuid=model_uuid,
        )

        # Next create the critic agent, which may contain knowledge bases for additional context
        logging.info("Creating Critic Agent...")
        critic_agent_deployment = self._create_component_agent(
            project_id=project_id,
            agent_name=critic_agent_name,
            agent_description="The Critic sub agent used by the auditor agent.",
            prompt=CRITIC_PROMPT,
            region=region,
            model_uuid=model_uuid,
            kb_uuids=reference_kbs,
        )

        # Finally, create the revisor agent
        logging.info("Creating Revisor Agent...")
        revisor_agent_deployment = self._create_component_agent(
            project_id=project_id,
            agent_name=revisor_agent_name,
            agent_description="The Revisor sub-agent used by the auditor agent.",
            prompt=REVISER_PROMPT,
            region=region,
            model_uuid=model_uuid,
        )

        # Sleep for a few seconds
        time.sleep(10)

        auditor_uuid = auditor_agent_deployment.get("agent").get("uuid")
        critic_uuid = critic_agent_deployment.get("agent").get("uuid")
        revisor_uuid = revisor_agent_deployment.get("agent").get("uuid")

        self._wait_till_ready(critic_uuid, revisor_uuid)

        return {
            "auditor": _create_info_from_deployment(
                self.client.genai.get_agent(auditor_uuid), require_url=False
            ),
            "critic": _create_info_from_deployment(
                self.client.genai.get_agent(critic_uuid)
            ),
            "revisor": _create_info_from_deployment(
                self.client.genai.get_agent(revisor_uuid)
            ),
        }

    def _enable_api_key(self, deployed_agent_info: DeployedAgentInfo, key_name: str):
        logging.info(f"Enabling API key for agent {deployed_agent_info.agent_uuid}")
        key_creation = self.client.genai.create_agent_api_key(
            deployed_agent_info.agent_uuid,
            body={"agent_uuid": deployed_agent_info.agent_uuid, "name": key_name},
        )
        agent_key = key_creation.get("api_key_info", {}).get("secret_key")
        if agent_key is None:
            raise ValueError(f"Returned agent key is None")
        return DeployedAgentInfo(
            agent_uuid=deployed_agent_info.agent_uuid,
            agent_url=deployed_agent_info.agent_url,
            agent_key=agent_key,
        )

    def enable_programatic_access(self, deployment_dict: dict[str, DeployedAgentInfo]):
        # Enable API key based access for the critic and revisor so the auditor can invoke them
        deployment_dict["critic"] = self._enable_api_key(
            deployment_dict["critic"], "Auditor Agent Key"
        )
        deployment_dict["revisor"] = self._enable_api_key(
            deployment_dict["revisor"], "Auditor Agent Key"
        )
        return deployment_dict


class FunctionDeployer:
    def __init__(self, token: str, context: str):
        self.token = token
        self.context = context
        self.client = pydo.Client(token=token)

    def create_namespace(self, namespace: str, region: str):
        # Create a new namespace for the functions
        try:
            fn_namespace = self.client.functions.create_namespace(
                body={"label": namespace, "region": region}
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

    def _export_secrets_to_env(
        self,
        tools_path: str,
        tavily_api_key: str,
        agent_deployment_dict: dict[str, DeployedAgentInfo],
    ):
        # Create an .env to create access tokens for the tools and include secrets
        with open(f"{tools_path}/.env", "w") as f:
            # These first ones are to enable secure functions
            f.write(f"SEARCH_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"CRITIC_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"REVISOR_TOKEN={secrets.token_urlsafe(16)}\n")

            # Add in the API key to use tavily
            f.write(f"TAVILY_API_KEY={tavily_api_key}\n")

            # Finally, add in the agent URLs and keys to allow them to be invoked in a function call
            f.write(
                f"CRITIC_AGENT_ENDPOINT={agent_deployment_dict.get("critic").agent_url}\n"
            )
            f.write(
                f"CRITIC_AGENT_ACCESS_KEY={agent_deployment_dict.get("critic").agent_key}\n"
            )
            f.write(
                f"REVISOR_AGENT_ENDPOINT={agent_deployment_dict.get("revisor").agent_url}\n"
            )
            f.write(
                f"REVISOR_AGENT_ACCESS_KEY={agent_deployment_dict.get("revisor").agent_key}\n"
            )

    def deploy_functions(
        self,
        namespace: str,
        region: str,
        tavily_api_key: str,
        agent_deployment_dict: dict[str, DeployedAgentInfo],
    ):
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
        self._export_secrets_to_env(temp_fn_dir, tavily_api_key, agent_deployment_dict)
        self._connect_doctl_serverless(namespace_id)
        self._deploy_doctl_serverless(temp_fn_dir)
        return namespace_id


def deploy_auditor_agent_template(
    auth: DOAuth,
    project_id: str,
    tavily_api_key: str,
    namespace_label="auditor-agent-template-functions",
    auditor_agent_name: str = AUDITOR_AGENT_NAME,
    critic_agent_name: str = CRITIC_AGENT_NAME,
    revisor_agent_name: str = REVISOR_AGENT_NAME,
    region: str = DEFAULT_REGION,
    model_uuid: str = LLAMA_3_3_70B_UUID,
    reference_kbs: Optional[List[str]] = None,
):
    # Deployment happens in the following order:
    # 1. Three agents are created - the auditor, the critic and the revisor. Critic and revisor are used by the auditor
    # 2. API keys are generated for only critic and revisor
    # 3. Three functions are deployed to the namespace - the search tool, and functions to invoke the critic and revisor
    # 4. The critic agent is updated to use the search tool, and the auditor agent is updated to use the critic and revisor.

    # Step 0: Init
    agent_deployer = AgentDeployer(auth.token)
    function_deployer = FunctionDeployer(auth.token, auth.context)

    # Step 1: Create the agents
    logging.info("Starting Auditor agent template deployment....")

    agent_deployments = agent_deployer.create_agents(
        project_id=project_id,
        auditor_agent_name=auditor_agent_name,
        critic_agent_name=critic_agent_name,
        revisor_agent_name=revisor_agent_name,
        region=region,
        model_uuid=model_uuid,
        reference_kbs=reference_kbs,
    )

    # Sleep for a few seconds to prevent overloading the agent API
    time.sleep(5)

    # Step 2 - enable API access
    agent_deployments = agent_deployer.enable_programatic_access(agent_deployments)

    # Step 3 - deploy functions
    function_namespace_id = function_deployer.deploy_functions(
        namespace=namespace_label,
        region=region,
        tavily_api_key=tavily_api_key,
        agent_deployment_dict=agent_deployments,
    )

    # Step 4 : Add tools to the agents
    logging.info("Attaching search tool to critic agent ...")
    search_config = AgentFunctionConfig(
        agent_uuid=agent_deployments["critic"].agent_uuid,
        description=SEARCH_DESCRIPTION,
        faas_name="auditor-tools/search",
        faas_namespace=function_namespace_id,
        function_name="search-web",
        input_schema=SEARCH_INPUT_SCHEMA,
        output_schema=SEARCH_OUTPUT_SCHEMA,
    )
    agent_deployer._add_tool_to_agent(
        agent_deployments["critic"].agent_uuid, search_config
    )

    logging.info("Adding critic to auditor")
    critic_config = AgentFunctionConfig(
        agent_uuid=agent_deployments["auditor"].agent_uuid,
        description=CRITIC_DESCRIPTION,
        faas_name="auditor-tools/critic",
        faas_namespace=function_namespace_id,
        function_name="invoke-critic",
        input_schema=CRITIC_INPUT_SCHEMA,
        output_schema=CRITIC_OUTPUT_SCHEMA,
    )
    agent_deployer._add_tool_to_agent(
        agent_deployments["auditor"].agent_uuid, critic_config
    )
    logging.info("Adding revisor to auditor")
    revisor_config = AgentFunctionConfig(
        agent_uuid=agent_deployments["auditor"].agent_uuid,
        description=REVISOR_DESCRIPTION,
        faas_name="auditor-tools/revisor",
        faas_namespace=function_namespace_id,
        function_name="invoke-revisor",
        input_schema=REVISOR_INPUT_SCHEMA,
        output_schema=REVISOR_OUTPUT_SCHEMA,
    )
    agent_deployer._add_tool_to_agent(
        agent_deployments["auditor"].agent_uuid, revisor_config
    )

    logging.info("Tools attachment completed")

    logging.info(
        f"Auditor agent deployment completed!\nYou can find your agent at : https://cloud.digitalocean.com/gen-ai/agents/{agent_deployments["auditor"].agent_uuid}\nNote:It may be a few minutes before your agent is ready to use."
    )


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
    parser.add_argument("--context", help="doctl Context")
    parser.add_argument("--project-id", help="Project ID")
    parser.add_argument("--tavily-api-key", help="Tavily API Key")
    parser.add_argument("--namespace-label", help="Namespace for the functions")
    parser.add_argument("--region", help="Region")
    parser.add_argument("--model-uuid", help="The model ID to use")
    parser.add_argument(
        "--kbs",
        type=lambda a: json.loads("[" + a.replace(" ", ",") + "]"),
        default=None,
        help="List of Knowledge Base IDs (optional)",
    )

    args = parser.parse_args()

    if args.env_file:
        load_dotenv(dotenv_path=args.env_file)

    deploy_auditor_agent_template(
        auth=DOAuth(
            get_arg_or_env(args.token, "DIGITALOCEAN_TOKEN", nullable=False),
            get_arg_or_env(
                args.context, "DIGITALOCEAN_CONTEXT", default="default", nullable=False
            ),
        ),
        project_id=get_arg_or_env(args.project_id, "PROJECT_ID", nullable=False),
        tavily_api_key=get_arg_or_env(
            args.tavily_api_key, "TAVILY_API_KEY", nullable=False
        ),
        namespace_label=get_arg_or_env(
            args.namespace_label, "NAMESPACE_LABEL", nullable=False
        ),
        region=get_arg_or_env(args.region, "REGION", DEFAULT_REGION, nullable=False),
        model_uuid=get_arg_or_env(
            args.model_uuid, "MODEL_UUID", LLAMA_3_3_70B_UUID, nullable=False
        ),
        reference_kbs=get_arg_or_env(args.kbs, "KNOWLEDGE_BASE_IDS"),
    )


if __name__ == "__main__":
    main()
