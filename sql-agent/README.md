# SQL Assistant Agent Template

The SQL Assistant Agent connects to your existing MySQL database and translates natural language questions into SQL queries, then analyzes the results. The agent dynamically fetches your database schema to craft intelligent queries and is restricted to read-only operations for security.

## Requirements

Before deploying this agent, ensure you have:

1. **Tools installed:**
   - `pydo` and `doctl`

2. **DigitalOcean access:**
   - Valid DigitalOcean API token
   - Sufficient privileges to deploy DigitalOcean Functions and Gradient™ AI Platform agents
   - Optional: Valid `doctl` context

3. **Database:**
   - Existing deployed MySQL database
   - Database user with privileges to create new users

4. **Terms & Conditions:**
   - Accepted Terms & Conditions for using Llama 3.3 70B

## How It Works

The deployment follows these steps:

1. **Database Setup** - Creates a read-only user with specified credentials
2. **Function Deployment** - Deploys secure web functions via `doctl`:
   - `get_schema` - Fetches database schema information
   - `execute_query` - Executes SELECT queries safely
3. **Agent Creation** - Creates the Gradient AI Platform agent using `pydo`
4. **Tool Integration** - Attaches the database functions to the agent

## Usage

### Basic deployment:
```bash
python deploy_template.py \
  --token YOUR_DIGITALOCEAN_TOKEN \
  --context DOCTL_CONTEXT \
  --project-id YOUR_PROJECT_ID \
  --region region\
  --db-host your_db_host \
  --db-port your_db_port \
  --db-name your_database \
  --db-admin-user admin-user \
  --db-admin-password your_password \
  --agent-user-id agent_user_id \
  --namespace-label your-function-namespace-label\
```

### Using environment file:
```bash
python deploy_template.py --env-file production.env 
```
See the sample env file for an example


### Get help:
```bash
python deploy_template.py --help
```

## Notes

- The deployment will fail if there are existing resources provisioned with the names provided. 
- Model T&C must be accepted before running this script
- Unlike terraform deployments, this deployment script cannot be rolled back if a deployment fails midway. 
