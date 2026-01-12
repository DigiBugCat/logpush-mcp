# Logpush MCP

MCP server for reading Cloudflare Workers logpush data from R2 buckets.

## Features

- List available log dates by environment (production/staging)
- Browse and read individual log files
- Search logs with filters (worker, status code, outcome, text)
- Get aggregated statistics
- Quick access to errors and exceptions
- Get latest logs with one command

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Configuration

Set these environment variables (or create a `.env` file):

```bash
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your-bucket-name
```

Get R2 API credentials from: Cloudflare Dashboard > R2 > Manage R2 API Tokens

## Usage

### Run locally

```bash
uv run logpush-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "logpush": {
      "command": "uv",
      "args": ["run", "logpush-mcp"],
      "cwd": "/path/to/arross-cf-mcp",
      "env": {
        "R2_ACCOUNT_ID": "your_account_id",
        "R2_ACCESS_KEY_ID": "your_access_key_id",
        "R2_SECRET_ACCESS_KEY": "your_secret_access_key",
        "R2_BUCKET_NAME": "your-bucket-name"
      }
    }
  }
}
```

## MCP Tools

### `list_log_dates`
List available date folders in the bucket.
- `environment`: production, staging, or omit for all
- `limit`: max dates to return (default 30)

### `list_log_files`
List log files for a specific date.
- `date`: YYYYMMDD format
- `environment`: production or staging
- `limit`: max files (default 50)
- `cursor`: pagination token

### `read_log_file`
Read contents of a specific log file.
- `path`: full object key
- `limit`: max entries (default 100)

### `search_logs`
Search logs with filters.
- `date`: YYYYMMDD format
- `environment`: production or staging
- `script_name`: filter by worker name
- `status_code`: exact status code
- `status_gte`: status >= value (e.g., 400)
- `status_lt`: status < value
- `outcome`: "ok" or "exception"
- `search_text`: search in URL and log messages
- `limit`: max entries (default 50)

### `get_log_stats`
Get aggregated statistics for a date.
- `date`: YYYYMMDD format
- `environment`: production or staging

### `get_errors`
Get error logs and exceptions.
- `date`: YYYYMMDD format
- `environment`: production or staging
- `script_name`: optional filter
- `limit`: max entries (default 50)

### `get_latest`
Get the most recent log entries.
- `environment`: production or staging
- `script_name`: optional filter
- `limit`: max entries (default 50)

## Log Structure

Expects Cloudflare Workers Trace Events logpush format:

```
bucket/
├── production/YYYYMMDD/*.log.gz
└── staging/YYYYMMDD/*.log.gz
```

Files are NDJSON with Cloudflare's workers_trace_events schema.

## Deployment to FastMCP Cloud

### Step 1: Sign up at FastMCP Cloud
1. Go to [fastmcp.cloud](https://fastmcp.cloud)
2. Sign in with your GitHub account

### Step 2: Create a new project
1. Click "Create Project"
2. Select this repository (`logpush-mcp`)
3. FastMCP will auto-detect the `pyproject.toml` entry point

### Step 3: Configure environment variables
In the FastMCP Cloud dashboard, add these environment variables:

| Variable | Description |
|----------|-------------|
| `R2_ACCOUNT_ID` | Your Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 API token access key ID |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret access key |
| `R2_BUCKET_NAME` | Name of your logpush R2 bucket |

### Step 4: Deploy
Click "Deploy" - FastMCP handles the rest automatically.

### Step 5: Connect to your MCP client
FastMCP Cloud provides a URL like `https://your-project.fastmcp.cloud/mcp`

For Claude Desktop, add to your config:
```json
{
  "mcpServers": {
    "logpush": {
      "command": "npx",
      "args": ["mcp-remote", "https://your-project.fastmcp.cloud/mcp"]
    }
  }
}
```

### Getting R2 API Credentials

1. Go to Cloudflare Dashboard → R2 → Manage R2 API Tokens
2. Create a new API token with:
   - **Permissions**: Object Read & Write
   - **Scope**: Specific bucket (your logpush bucket)
3. Copy the Access Key ID and Secret Access Key

## License

MIT
