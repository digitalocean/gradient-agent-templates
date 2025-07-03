# 📄 Product Documentation QA Agent Template

This project is a template for deploying a Retrieval-Augmented Generation (RAG) agent on the [DigitalOcean GenAI Platform](https://www.digitalocean.com/products/gen-ai) that answers user questions based on your product documentation. 

This template will do the following:

1. Upload your documentation to a new object storage bucket.
2. Create and index a new knowledge base (KB).
3. Deploy an agent connected to that KB to provide accurate, citation-rich answers.
4. Optimize the agent's retrieval method and configuration for high RAG performance.


## 🚀 Setup

Before running the script, ensure the following:

- Python **3.9 or higher**
- `virtualenv` or similar environment manager

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
````

You will also need:

* A valid DigitalOcean API Token
* A valid Project ID
* You must have accepted the terms and conditions to use LLaMA 3.3 70B on the GenAI platform (you can do this by manually creating a new agent using LLaMA 3.3 70B as the base model).


## 🛠️ What this Template Does

When you run `deploy_template.py`, the script:

1. **Creates a new bucket** in the specified DigitalOcean project to store your documentation files.
2. **Creates a knowledge base** connected to this bucket and indexes your docs.

   * You can either create a **new OpenSearch DB** or use an **existing one**.
3. **Creates a GenAI agent** using the indexed KB.

   * The agent will be instructed on your product using the name and description provided.
   * The agent is explicitly instructed to not answer questions unrelated to the product, or questions that cannot be answered via the documentation
4. **Updates the agent's configuration** to:

   * Provide source citations
   * Optimize retrieval strategy for accurate answers


## 🧪 Usage

You can run the deployment script using CLI arguments, environment variables, or a combination of both. CLI arguments take precedence over environment variables.

```bash
python deploy_template.py \
  --token YOUR_DO_TOKEN \
  --project-id YOUR_PROJECT_ID \
  --product-name "My Product" \
  --product-description "My Product's Description" \
  --kb-name my-product-kb \
  --bucket-name my-product-docs \
  --documentation-path ./docs \
  --region tor1 \
  --embedding-model EMBEDDING_MODEL_UUID \
  --model-uuid LLAMA_3_3_70B_UUID \
  --database-id EXISTING_DB_ID \
  --access-key YOUR_SPACES_ACCESS_KEY \
  --secret-key YOUR_SPACES_SECRET_KEY \
  --agent-name my-docs-agent \
  --env-file .env
```

### 🔤 Arguments

| Argument                | Required | Description                                              |
| ----------------------- | -------- | -------------------------------------------------------- |
| `--token`               | ✅        | DigitalOcean API token                                   |
| `--project-id`          | ✅        | Project ID to scope all resources                        |
| `--product-name`        | ✅        | Name of your product                                     |
| `--product-description` | ✅        | Description of your product (wrap in quotes)             |
| `--kb-name`             | ✅        | Name of the knowledge base                               |
| `--bucket-name`         | ✅        | Name of the bucket to store documentation                |
| `--documentation-path`  | ✅        | Path to your local documentation folder                  |
| `--region`              | ❌        | Region for the bucket (default: `tor1`)                  |
| `--embedding-model`     | ❌        | UUID of the embedding model (default provided in script) |
| `--model-uuid`          | ❌        | UUID of the LLM (default is LLAMA 3.3 70B)               |
| `--database-id`         | ❌        | ID of an existing OpenSearch database (if using one)     |
| `--access-key`          | ❌        | Spaces access key (optional if set in `.env`)            |
| `--secret-key`          | ❌        | Spaces secret key (optional if set in `.env`)            |
| `--agent-name`          | ❌        | Optional custom name for the agent                       |
| `--env-file`            | ❌        | Optional path to a `.env` file to load defaults          |

You can also store values in a `.env` file:

```env
DO_API_TOKEN=your_token
PROJECT_ID=my_project
PRODUCT_NAME=My Product
...
```

Then run:

```bash
python deploy_template.py --env-file .env
```



## 📌 Notes

* If you use an existing OpenSearch DB, ensure it belongs to the same project as the new agent. Indexing requires the KB and DB to be in the same project.
* It may take a few minutes for the agent to become fully operational after deployment. 
* Since this is a template, it is designed to be a generic and flexible solution that can easily integrate with any product documentation. You may want to tweak the prompt and the agent's settings to better fit your requirements and perform better on your data.
 

