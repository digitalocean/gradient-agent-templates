# 📝 Quiz Generation Agent Template

This project is a template for deploying a **quiz creation agent** on the [DigitalOcean Gradient™ AI Platform](https://www.digitalocean.com/products/gradient). The agent generates quizzes based on a knowledge base you provide.

Each quiz includes:

* **3 multiple-choice questions (MCQs)**
* **2 free-response questions**
* **Answer rubrics** for all questions

This makes it easy to build interactive quizzes and assessments from your own data.

## 🚀 Setup

Before running the script, ensure the following:

* Python **3.9 or higher**
* `virtualenv` or similar environment manager

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

You will also need:

* A valid **DigitalOcean API Token**
* A valid **Project ID**
* Access to a base model on the Gradient AI Platform (e.g., LLaMA 3.3 70B).

## 🛠️ What this Template Does

When you run `deploy_template.py`, the script will:

1. **Create a new bucket** in the specified DigitalOcean project to store your quiz source data.
2. **Create a knowledge base (KB)** connected to this bucket and index your data.

   * You can either create a **new OpenSearch DB** or use an **existing one**.
3. **Deploy a Gradient AI Platform agent** that generates quizzes from the indexed KB.

   * The agent is instructed to generate **3 MCQs, 2 free-response questions, and rubrics** based on the provided data.
4. **Configure the agent** with optimized retrieval and quiz generation prompts.



## 🧪 Usage

You can run the deployment script using CLI arguments, environment variables, or a combination of both. CLI arguments take precedence over environment variables.

```bash
python deploy_template.py \
  --token YOUR_DO_TOKEN \
  --project-id YOUR_PROJECT_ID \
  --data-description "Collection of math concepts and study material" \
  --kb-name math-kb \
  --bucket-name math-data-bucket \
  --data-path ./data \
  --region tor1 \
  --embedding-model EMBEDDING_MODEL_UUID \
  --model-uuid LLAMA_3_3_70B_UUID \
  --database-id EXISTING_DB_ID \
  --access-key YOUR_SPACES_ACCESS_KEY \
  --secret-key YOUR_SPACES_SECRET_KEY \
  --agent-name quiz-agent \
  --env-file .env
```

### 🔤 Arguments

| Argument             | Required | Description                                                         |
| -------------------- | -------- | ------------------------------------------------------------------- |
| `--env-file`         | ❌        | Path to a `.env` file to load environment variables from            |
| `--token`            | ✅        | DigitalOcean API token                                              |
| `--project-id`       | ✅        | Project ID to scope all resources                                   |
| `--data-description` | ✅        | Description of the data used to build the knowledge base            |
| `--kb-name`          | ✅        | Name of the knowledge base                                          |
| `--bucket-name`      | ✅        | Name of the bucket to store your data                               |
| `--data-path`        | ✅        | Local path to the folder containing the data                        |
| `--region`           | ❌        | Region for the bucket (default: `tor1`)                             |
| `--embedding-model`  | ❌        | UUID of the embedding model (default provided in script)            |
| `--model-uuid`       | ❌        | UUID of the LLM to use for quiz generation (default: LLaMA 3.3 70B) |
| `--database-id`      | ❌        | ID of an existing OpenSearch database (if reusing one)              |
| `--access-key`       | ❌        | Spaces access key (optional if set in `.env`)                       |
| `--secret-key`       | ❌        | Spaces secret key (optional if set in `.env`)                       |
| `--agent-name`       | ❌        | Optional custom name for the agent                                  |

You can also store values in a `.env` file:

```env
DO_API_TOKEN=your_token
PROJECT_ID=my_project
DATA_DESCRIPTION="Collection of training manuals"
...
```

Then run:

```bash
python deploy_template.py --env-file .env
```


## 📌 Notes

* If you use an existing OpenSearch DB, ensure it belongs to the same project as the agent. Indexing requires the KB and DB to be in the same project.
* It may take a few minutes for the quiz generation agent to become fully operational after deployment.
* This template is designed to be a flexible starting point. You may want to refine the agent’s prompt or configuration for your specific data domain.

