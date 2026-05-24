# Context

The user wants to follow the [TheInformationLab/tableau_mcp_starter_kit](https://github.com/TheInformationLab/tableau_mcp_starter_kit) setup guide. This is a Python + LangChain app that connects to a locally-built Tableau MCP server and exposes either a web UI or a Tableau Dashboard Extension (.trex) for querying Tableau data with AI.

**Current state:**
- `tableau-mcp` is already cloned and built at `/Users/austinkness/Tableau MCP/tableau-mcp/`
  - Build output: `/Users/austinkness/Tableau MCP/tableau-mcp/build/index.js`
- The `tableau_mcp_starter_kit` repo has NOT been cloned yet
- Node.js v22.17.0 ✓ (requirement: ≥22.15.0)
- Python 3.13.2 ✓ (requirement: ≥3.12)

**Selected mode:** Dashboard Extension (embed as `.trex` in a Tableau dashboard)

---

# Plan

## Step 1 — Clone the starter kit

```bash
cd "/Users/austinkness/Tableau MCP"
git clone https://github.com/TheInformationLab/tableau_mcp_starter_kit.git
cd tableau_mcp_starter_kit
```

## Step 2 — Create and activate Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

## Step 4 — Configure .env

```bash
cp .env_template .env
```

Then fill in these values in `.env`:

| Variable | Value |
|---|---|
| `TRANSPORT` | `'stdio'` |
| `SERVER` | Your Tableau Server/Cloud URL |
| `SITE_NAME` | Your Tableau site name |
| `PAT_NAME` | Your PAT name |
| `PAT_VALUE` | Your PAT secret |
| `TABLEAU_MCP_FILEPATH` | `/Users/austinkness/Tableau MCP/tableau-mcp/build/index.js` |
| `OPENAI_API_KEY` | Your OpenAI key |
| `FIXED_DATASOURCE_LUID` | LUID for your target datasource (found via GQL below) |

## Step 5 — Clone the experimental tools repo (Dashboard Extension dependency)

```bash
cd "/Users/austinkness/Tableau MCP"
git clone https://github.com/wjsutton/tableau-mcp-experimental.git
cd tableau-mcp-experimental
npm install
npm run build
```

Then update `dashboard_app.py` line 36 with the local filepath to this build.

## Step 6 — Find datasource LUID

Use the GraphQL query at `utilities/find_datasource_luid.gql` against the Tableau Metadata API to find the LUID of your target datasource. Add it to `.env` as `FIXED_DATASOURCE_LUID`.

## Step 7 — Run the dashboard app

```bash
source .venv/bin/activate
python dashboard_app.py
```

## Step 8 — Load the .trex in Tableau

Open a Tableau dashboard → Add Extension → load `tableau_langchain.trex` from the `dashboard_extension/` folder.

---

# Verification

- `dashboard_app.py` starts without errors
- Tableau accepts the `.trex` file and the extension panel loads
- A test query (e.g. "Show me outliers in the sales data") returns results from the configured datasource
