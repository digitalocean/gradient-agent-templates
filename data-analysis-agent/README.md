# 📊 Data Analysis Agent Template

This project is a template for deploying a Retrieval-Augmented Generation (RAG) agent on the [DigitalOcean Gradient™ AI Platform](https://www.digitalocean.com/products/gradient) that analyzes multiple CSV data files and provides insights, statistics, and data analysis. 

This template will do the following:

1. Upload your CSV data files to a new object storage bucket.
2. Create and index a new knowledge base (KB) with all your data files.
3. Deploy an agent connected to that KB to provide data analysis and insights across multiple datasets.
4. Optimize the agent's retrieval method and configuration for high RAG performance.

## ✅ What This Agent Is Good For

The data analysis agent excels at:

### **Accurate Mathematical Analysis**
- **Real statistical calculations**: Mean, median, mode, standard deviation, variance on actual data
- **Mathematical operations**: Performed on complete datasets loaded into memory
- **Deterministic results**: Same input always produces the same output
- **No approximations**: All calculations are mathematically accurate

### **Data Exploration & Understanding**
- **Column analysis**: Data types, null values, unique values, value distributions
- **Data quality assessment**: Missing values, outliers, data completeness
- **Sample data inspection**: First few rows to understand data structure
- **File metadata**: Size, modification dates, column information

### **Complex Data Queries**
- **Pandas code execution**: Run complex analysis using pandas operations
- **Custom calculations**: Generate and execute custom statistical formulas
- **Data filtering and grouping**: Advanced data manipulation operations
- **Cross-column analysis**: Relationships and correlations between variables

### **Business Intelligence**
- **Performance metrics analysis**: KPIs, growth rates, efficiency measures
- **Customer behavior insights**: Purchase patterns, engagement metrics
- **Financial analysis**: Revenue trends, cost analysis, profitability metrics
- **Operational insights**: Process efficiency, resource utilization

### **Multi-Dataset Analysis**
- **Cross-dataset comparisons**: Comparing metrics across different data sources
- **Data integration insights**: Finding connections between separate datasets
- **Consistent analysis**: Same methodology applied across all datasets

## 🔧 Available Tools

The agent has access to these specialized tools:

### **File Management**
- **`list_files`**: List all CSV files in the bucket with metadata
- **`load_csv`**: Load CSV files into memory as pandas DataFrames (max 10,000 rows)

### **Data Analysis**
- **`get_column_info`**: Get detailed information about specific columns
- **`calculate_stats`**: Calculate specific statistics (mean, median, std, variance, etc.)
- **`execute_pandas_code`**: Execute pandas code for complex analysis

### **Tool Usage Examples**
```python
# List available files
list_files()

# Load a CSV file
load_csv(filename="sales_data.csv", max_rows=5000)

# Get column information
get_column_info(filename="sales_data.csv", column_name="revenue")

# Calculate specific statistics
calculate_stats(filename="sales_data.csv", column_name="revenue", statistic="mean")

# Execute complex pandas code (use simple quotes, avoid escaping)
execute_pandas_code(
    filename="sales_data.csv",
    pandas_code="print(df.groupby('category')['revenue'].sum().sort_values(ascending=False))"
)

# More examples of safe pandas code:
execute_pandas_code(
    filename="sales_data.csv",
    pandas_code="print(df.describe())"
)

execute_pandas_code(
    filename="sales_data.csv", 
    pandas_code="print(df[df['revenue'] > 1000].head())"
)
```

## ❌ What This Agent Won't Do

### **Visualizations**
- **Cannot create charts, graphs, or plots**: Textual descriptions only
- **Cannot generate images or dashboards**: Text-based analysis only

### **Data Manipulation**
- **Cannot modify CSV files**: Read-only analysis
- **Cannot clean or transform data**: Analysis of existing data only

### **Real-time Analysis**
- **Cannot process streaming data**: Works with static CSV files only
- **Cannot connect to live databases**: CSV file analysis only

### **Advanced Features**
- **Cannot perform machine learning**: No predictive modeling capabilities
- **Cannot store analysis results**: Conversational analysis only
- **Memory limitations**: Large files can be limited by specifying max_rows parameter

## 🎯 Best Use Cases

This agent is perfect for:
- **Quick data exploration** of uploaded CSV files
- **Statistical summaries** and pattern identification
- **Business intelligence** insights from historical data
- **Data quality assessment** and cross-dataset analysis

## 🚀 Setup

Before running the script, ensure the following:

### **Prerequisites**

- Python **3.9 or higher**
- `virtualenv` or similar environment manager
- **doctl** (DigitalOcean CLI tool)
- **doctl serverless** plugin

### **Installation Steps**

1. **Install Python dependencies:**
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

2. **Install doctl:**
```bash
# macOS (using Homebrew)
brew install doctl

# Linux/Windows - Download from: https://github.com/digitalocean/doctl/releases
# Or use the installation script:
curl -sL https://github.com/digitalocean/doctl/releases/download/v1.94.0/doctl-1.94.0-linux-amd64.tar.gz | tar -xzv
sudo mv doctl /usr/local/bin
```

3. **Install doctl serverless plugin:**
```bash
doctl serverless install
```

4. **Verify installation:**
```bash
doctl version
doctl serverless --help
```

### **Required Credentials**

You will also need:

* A valid DigitalOcean API Token
* A valid Project ID
* You must have accepted the terms and conditions to use LLaMA 3.3 70B on the Gradient AI Platform (you can do this by manually creating a new agent using LLaMA 3.3 70B as the base model).


## 🛠️ What this Template Does

When you run `deploy_template.py`, the script:

1. **Creates a new bucket** in the specified DigitalOcean project to store your CSV data files.
2. **Uploads your CSV files** to the bucket for analysis.
3. **Creates a knowledge base** connected to this bucket and indexes your data.

   * You can either create a **new OpenSearch DB** or use an **existing one**.
4. **Deploys FaaS functions** for CSV analysis tools:
   - `list_files` - List available CSV files
   - `load_csv` - Load CSV files into memory as pandas DataFrames
   - `get_column_info` - Get detailed column information
   - `calculate_stats` - Calculate mathematical statistics
   - `execute_pandas_code` - Execute pandas code for complex analysis

5. **Creates a Gradient AI Platform agent** with both:
   - **Knowledge base access** for general data questions
   - **Tool access** for accurate mathematical analysis

6. **Attaches analysis tools** to the agent for:
   - **Accurate statistical calculations** on actual data
   - **Mathematical operations** performed in memory
   - **Complex queries** using pandas code execution

7. **Updates the agent's configuration** to:
   - Provide source citations
   - Optimize retrieval strategy for data analysis


## 🧪 Usage

You can run the deployment script using CLI arguments, environment variables, or a combination of both. CLI arguments take precedence over environment variables.

```bash
python deploy_template.py \
  --token YOUR_DO_TOKEN \
  --project-id YOUR_PROJECT_ID \
  --kb-name my-data-kb \
  --bucket-name my-data-files \
  --data-path ./data \
  --region tor1 \
  --embedding-model EMBEDDING_MODEL_UUID \
  --model-uuid LLAMA_3_3_70B_UUID \
  --database-id EXISTING_DB_ID \
  --access-key YOUR_SPACES_ACCESS_KEY \
  --secret-key YOUR_SPACES_SECRET_KEY \
  --agent-name my-data-agent \
  --env-file .env
```

### 🔤 Arguments

| Argument                | Required | Description                                              |
| ----------------------- | -------- | -------------------------------------------------------- |
| `--token`               | ✅        | DigitalOcean API token                                   |
| `--project-id`          | ✅        | Project ID to scope all resources                        |
| `--kb-name`             | ✅        | Name of the knowledge base                               |
| `--bucket-name`         | ✅        | Name of the bucket to store data files                   |
| `--data-path`           | ✅        | Path to your local data folder containing CSV files      |
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
KB_NAME=my-data-kb
BUCKET_NAME=my-data-files
DATA_PATH=./data
...
```

Then run:

```bash
python deploy_template.py --env-file .env
```



## 🔧 Troubleshooting

### **doctl Issues**

If you encounter issues with doctl:

1. **Verify doctl installation:**
```bash
doctl version
```

2. **Check serverless plugin:**
```bash
doctl serverless --help
```

3. **If serverless commands fail, reinstall:**
```bash
doctl serverless install
```

4. **Authentication issues:**
```bash
doctl auth init
```

### **Common Deployment Issues**

- **"doctl not found"**: Ensure doctl is installed and in your PATH
- **"serverless command not found"**: Run `doctl serverless install`
- **Authentication errors**: Verify your DigitalOcean API token
- **Function deployment fails**: Check that all required environment variables are set

### **Memory and Performance**

- **Large CSV files**: The agent limits files to 10,000 rows by default to prevent memory issues
- **Complex analysis**: Use `execute_pandas_code` for operations that need more memory
- **Multiple files**: Load and analyze one file at a time for best performance

## 📌 Notes

* If you use an existing OpenSearch DB, ensure it belongs to the same project as the new agent. Indexing requires the KB and DB to be in the same project.
* It may take a few minutes for the agent to become fully operational after deployment. 
* The FaaS functions are deployed using doctl, so ensure you have the proper permissions and doctl is installed.
* Since this is a template, it is designed to be a generic and flexible solution that can easily integrate with any CSV datasets. You may want to tweak the prompt and the agent's settings to better fit your requirements and perform better on your specific data.
 

