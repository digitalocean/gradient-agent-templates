# 📣 Twilio Marketing Agent Template

This project provides a template for deploying a Generative AI Agent that can generate and send marketing text messages using [Twilio](https://www.twilio.com/) on the [DigitalOcean Gradient™ AI Platform](https://www.digitalocean.com/products/gradient).



## 🧰 Setup Requirements

Before running the deployment script, ensure the following:

### ✅ Local Setup

- Python **3.9+**
- `doctl` installed and authenticated. [Install instructions](https://docs.digitalocean.com/reference/doctl/how-to/install/)
- `doctl serverless` plugin installed  
   `doctl serverless install`
- Twilio account setup with:
  - A verified **Twilio Account SID**
  - A **Twilio Auth Token**
  - A **Twilio phone number** (can be toll-free, but requires verification to send messages). You can find one in your [Twilio Virtual Phone](https://console.twilio.com/us1/develop/sms/virtual-phone)

### 📦 Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
````

## 🧪 What this Template Does

Running the script:

1. Deploys a serverless function** using `doctl serverless` that sends SMS via Twilio's messages API.
2. Creates a new agent on the DigitalOcean Gradient AI Platform.
3. Attaches the Twilio messaging tool to the agent so it can send marketing messages on its own.


## 🔤 CLI Usage

```bash
python deploy_template.py \
  --env-file .env \
  --token YOUR_DO_TOKEN \
  --context default \
  --project-id YOUR_PROJECT_ID \
  --twilio-sid YOUR_TWILIO_SID \
  --twilio-token YOUR_TWILIO_AUTH_TOKEN \
  --twilio-from-number +1234567890 \
  --namespace my-twilio-marketing \
  --region tor1 \
  --model-uuid MODEL_UUID \
  --agent-name "SMS Marketing Agent"
```

### CLI Arguments

| Argument               | Required | Description                                          |
| ---------------------- | -------- | ---------------------------------------------------- |
| `--env-file`           | ❌        | Path to a `.env` file (optional)                     |
| `--token`              | ✅        | DigitalOcean API token                               |
| `--context`            | ✅        | `doctl` context name (default: `default`)            |
| `--project-id`         | ✅        | DigitalOcean project ID                              |
| `--twilio-sid`         | ✅        | Your Twilio Account SID                              |
| `--twilio-token`       | ✅        | Your Twilio Auth Token                               |
| `--twilio-from-number` | ✅        | Verified Twilio phone number (e.g., `+1234567890`)   |
| `--namespace`          | ✅        | Namespace for the deployed tool                      |
| `--region`             | ❌        | DigitalOcean region for deployment (default: `tor1`) |
| `--model-uuid`         | ❌        | Model UUID (Optional. If not provided, Llama 3.3 is used)       |
| `--agent-name`         | ❌        | Custom agent name (default: `Marketing Assistant`)            |

You can also store these values in a `.env` file:

```env
DIGITALOCEAN_TOKEN=your_token
DIGITALOCEAN_CONTEXT=default
PROJECT_ID=your_project_id
TWILIO_SID=your_twilio_sid
TWILIO_TOKEN=your_twilio_token
TWILIO_FROM_NUMBER=+1234567890
NAMESPACE=my-agent-tools
```

Then run:

```bash
python deploy_template.py --env-file .env
```

## 📝 Notes

* Toll-free Twilio numbers require verification before they can send SMS to other numbers. You must complete this in the Twilio console before sending live messages. If you don't verify your number, then you can only send messages to your [Twilio virtual phone](https://console.twilio.com/us1/develop/sms/virtual-phone)
* The agent may take a few minutes to initialize after deployment.

