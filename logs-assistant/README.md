# 📜 Logs Assistant Agent Template

This project provides a template for deploying a Generative AI Agent that can automatically fetch build, deploy, and runtime logs for your running [DigitalOcean App Platform](https://docs.digitalocean.com/products/app-platform/) applications. The agent uses a serverless function to access logs via a dedicated **agent access token** and can explain log errors and provide triage guidance.

---

## 🧰 Setup Requirements

Before running the deployment script, ensure the following:

### ✅ Local Setup

* Python **3.9+**
* `doctl` installed and authenticated. [Install instructions](https://docs.digitalocean.com/reference/doctl/how-to/install/)
* `doctl serverless` plugin installed

  ```bash
  doctl serverless install
  ```
* A **DigitalOcean Access token** (for deploying resources)
* A separate access token that can be used by the Logs Assistant (stored as `AGENT_TOKEN`)

---

### 📦 Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🧪 What this Template Does

Running the deployment script will:

1. Deploy a secure and token-protected serverless function to **fetch logs** from your DigitalOcean apps.
2. Create a new agent on the DigitalOcean Gradient™ AI Platform.
3. Give the agent access to your logs via the provided `AGENT_TOKEN`.
4. Enable the agent to **analyze and explain logs**, helping you debug and triage issues faster.

---

## 🔤 CLI Usage

```bash
python deploy_template.py \
  --env-file .env \
  --token YOUR_DO_TOKEN \
  --context default \
  --project-id YOUR_PROJECT_ID \
  --agent-token YOUR_AGENT_DO_TOKEN \
  --namespace-label logs-assistant-template-functions \
  --region tor1 \
  --model-uuid MODEL_UUID \
  --agent-name "Logs Assistant"
```

---

### CLI Arguments

| Argument            | Required | Description                                                                           |
| ------------------- | -------- | ------------------------------------------------------------------------------------- |
| `--env-file`        | ❌        | Path to a `.env` file (optional, defaults to `.env`)                                  |
| `--token`           | ✅        | DigitalOcean API token for deployment                                                 |
| `--context`         | ✅        | `doctl` context name (default: `default`)                                             |
| `--project-id`      | ✅        | DigitalOcean project ID                                                               |
| `--agent-token`     | ✅        | **Newly created token for the Logs Assistant** (set as `AGENT_TOKEN`)                 |
| `--namespace-label` | ❌        | Namespace label for deployed functions (default: `logs-assistant-template-functions`) |
| `--region`          | ❌        | DigitalOcean region for deployment (default: `tor1`)                                  |
| `--model-uuid`      | ❌        | Model UUID (optional, defaults to Llama 3.3 70B)                                      |
| `--agent-name`      | ❌        | Custom agent name (default: `Logs Assistant`)                                         |

---

### Example `.env` file

```env
DIGITALOCEAN_TOKEN=your_token
DIGITALOCEAN_CONTEXT=default
PROJECT_ID=your_project_id
AGENT_TOKEN=your_logs_assistant_token
NAMESPACE_LABEL=logs-assistant-template-functions
REGION=tor1
MODEL_UUID=your_model_uuid
AGENT_NAME=Logs Assistant
```

Then deploy with:

```bash
python deploy_template.py --env-file .env
```

---

## 📝 Notes

* You **must create a separate DigitalOcean API token** for the agent (stored as `AGENT_TOKEN`). This token allows the agent to fetch logs independently.
* The deployed Logs Assistant can:
  * Retrieve logs for apps in the specified project
  * Identify and explain error messages
  * Provide actionable triage recommendations
* It may take a few minutes for the agent to initialize after deployment.
* Please ensure that you have accept the necessary Terms and Conditions needed to use the model specified. Terms and Conditions can be accepted by creating a new agent with the model you wish to use in the control panel and accepting the Terms and Conditions before deploying. 


