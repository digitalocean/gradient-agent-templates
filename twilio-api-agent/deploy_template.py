import os
import time
import secrets
import pydo
import shutil
import logging
import argparse
import tempfile
import subprocess
from dotenv import load_dotenv
from typing import Optional
from dataclasses import dataclass
from agent.constants import AGENT_NAME, LLAMA_3_3_70B_UUID
from agent.prompts import (
    SYSTEM_PROMPT,
    SEND_MESSAGE_INPUT_SCHEMA,
    SEND_MESSAGE_OUTPUT_SCHEMA,
    SEND_MESSAGE_TOOL_DESCRIPTION,
)

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
        agent_name: Optional[str] = AGENT_NAME,
        model_uuid: Optional[str] = LLAMA_3_3_70B_UUID,
    ):
        if model_uuid is None:
            model_uuid = LLAMA_3_3_70B_UUID
        # Create the config
        config = AgentConfig(
            agent_name=agent_name,
            agent_description="An intelligent marketing assistant that can send text messages.",
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

    # Add the send_message tool to the agent
    def add_tool_to_agent(
        self, agent_id: str, send_message_faas_name: str, namespace: str
    ):
        send_message_tool_config = AgentFunctionConfig(
            agent_uuid=agent_id,
            description=SEND_MESSAGE_TOOL_DESCRIPTION,
            faas_name=send_message_faas_name,
            faas_namespace=namespace,
            function_name="send_message",
            input_schema=SEND_MESSAGE_INPUT_SCHEMA,
            output_schema=SEND_MESSAGE_OUTPUT_SCHEMA,
        )

        self._add_tool_to_agent(agent_id, send_message_tool_config)


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

    def _export_secrets_to_env(
        self,
        tools_path: str,
        twilio_sid: str,
        twilio_token: str,
        twilio_from_number: str,
    ):
        # Create an intial .env to create access tokens for the tools
        with open(f"{tools_path}/.env", "w") as f:
            f.write(f"SEND_MESSAGE_TOKEN={secrets.token_urlsafe(16)}\n")
            f.write(f"TWILIO_ACCOUNT_SID={twilio_sid}\n")
            f.write(f"TWILIO_AUTH_TOKEN={twilio_token}\n")
            f.write(f"TWILIO_FROM_NUMBER={twilio_from_number}\n")

    def deploy_function(
        self,
        namespace: str,
        region: str,
        twilio_sid: str,
        twilio_token: str,
        twilio_from_number: str,
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
        self._export_secrets_to_env(
            temp_fn_dir, twilio_sid, twilio_token, twilio_from_number
        )
        self._connect_doctl_serverless(namespace_id)
        self._deploy_doctl_serverless(temp_fn_dir)
        return namespace_id


def deploy_twilio_marketing_agent(
    token: str,
    context: str,
    project_id: str,
    twilio_sid: str,
    twilio_token: str,
    twilio_from_number: str,
    namespace: str,
    region: str,
    agent_name: str,
    model_uuid: str,
):
    try:
        logging.info("Deploying functions..")
        function_deployer = FunctionDeployer(token, context)
        agent_deployer = AgentDeployer(token)
        namespace_id = function_deployer.deploy_function(
            namespace=namespace,
            region=region,
            twilio_sid=twilio_sid,
            twilio_token=twilio_token,
            twilio_from_number=twilio_from_number,
        )
        logging.info("Deploying agent....")
        agent_deployment = agent_deployer.create_template_agent(
            project_id=project_id,
            region=region,
            agent_name=agent_name,
            model_uuid=model_uuid,
        )
        time.sleep(5)
        logging.info("Attaching tool to agent...")
        agent_uuid = agent_deployment.get("agent", {}).get("uuid")
        agent_deployer.add_tool_to_agent(
            agent_id=agent_uuid,
            send_message_faas_name="twilio-agent-tools/send_message",
            namespace=namespace_id,
        )
        logging.info(
            f"Agent Deployment completed!\nYou can find your agent at: https://cloud.digitalocean.com/gen-ai/agents/{agent_uuid}\nNote:It may be a few minutes before your agent is ready to use."
        )
    except Exception as e:
        logging.error(f"An exception occurred: {e}", exc_info=True)


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
    parser.add_argument("--twilio-sid", help="Twilio SID")
    parser.add_argument("--twilio-token", help="Twilio Auth Token")
    parser.add_argument(
        "--twilio-from-number", help="Number to send Twilio messages from"
    )
    parser.add_argument("--namespace", help="Namespace to use for send message tool")
    parser.add_argument(
        "--region", help="Optional: DigitalOcean region. Defaults to tor1"
    )
    parser.add_argument("--model-uuid", help="Optional: LLM model UUID")
    parser.add_argument(
        "--agent-name",
        help=f"Optional: The name of the agent. If not provided, '{AGENT_NAME}' is used",
    )

    args = parser.parse_args()

    if args.env_file:
        load_dotenv(dotenv_path=args.env_file)

    deploy_twilio_marketing_agent(
        token=get_arg_or_env(args.token, "DIGITALOCEAN_TOKEN", nullable=False),
        context=get_arg_or_env(
            args.context, "DIGITALOCEAN_CONTEXT", default="default", nullable=False
        ),
        project_id=get_arg_or_env(args.project_id, "PROJECT_ID", nullable=False),
        twilio_sid=get_arg_or_env(args.twilio_sid, "TWILIO_SID", nullable=False),
        twilio_token=get_arg_or_env(args.twilio_token, "TWILIO_TOKEN", nullable=False),
        twilio_from_number=get_arg_or_env(
            args.twilio_from_number, "TWILIO_FROM_NUMBER", nullable=False
        ),
        namespace=get_arg_or_env(args.namespace, "NAMESPACE", nullable=False),
        region=get_arg_or_env(args.region, "REGION", "tor1"),
        model_uuid=get_arg_or_env(args.model_uuid, "MODEL_UUID", LLAMA_3_3_70B_UUID),
        agent_name=get_arg_or_env(args.agent_name, "AGENT_NAME", AGENT_NAME),
    )


if __name__ == "__main__":
    main()
