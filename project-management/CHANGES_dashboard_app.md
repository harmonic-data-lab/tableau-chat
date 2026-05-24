# Changes Applied
**Project:** Tableau MCP Starter Kit — Dashboard Extension Setup  
**Date:** 2026-05-23

Changes are grouped by file. All MCP server changes require `npm run build` in `tableau-mcp-experimental/` before restarting the app.

---

## `dashboard_app.py`

- [ ] Changed prompt import from `SUPERSTORE_AGENT_SYSTEM_PROMPT` to `AGENT_SYSTEM_PROMPT` — the Superstore-specific system prompt hardcoded "Agent Superstore" and "the legendary Superstore dataset," causing the agent to identify itself and its data incorrectly when connected to `global_disease_burden`
- [ ] Added `ToolNode` and `trim_messages` imports
- [ ] Added `import uuid`
- [ ] Added `SESSION_THREAD_ID = str(uuid.uuid4())` — single thread ID per server process for multi-turn memory with clean restarts
- [ ] Added `MAX_RESULT_LIMIT: "100"` to `custom_env` — caps rows returned per query to reduce context size
- [ ] Removed `read-metadata-fixed` from `tool_list` — unused tool was sending its schema with every LLM call
- [ ] Changed `ChatOpenAI` to `max_retries=0` — fails fast on rate limit instead of silently retrying for minutes
- [ ] Replaced `tools=mcp_tools` with `tool_node = ToolNode(mcp_tools, handle_tool_errors=True)` — MCP tool errors return to the LLM as ToolMessages instead of crashing the request with a 500
- [ ] Added `trim_history` pre_model_hook — trims conversation to the last 10 messages before each LLM call to prevent context bloat across turns
- [ ] Passed `SESSION_THREAD_ID` to `format_agent_response`

---

## `utilities/chat.py`

- [ ] Added `thread_id` parameter to `format_agent_response`
- [ ] Added `recursion_limit: 20` to astream config
- [ ] Added `RateLimitError` catch — returns a friendly message instead of a 500 error
- [ ] Added per-step logging (`[step N]`) — logs message type, tool calls, and content preview for each agent step to aid debugging

---

## `utilities/logging_config.py`

- [ ] Fixed `logging.getLogger('root')` → `logging.getLogger('dashboard')` — was creating a spurious named logger instead of configuring the actual root logger, causing child loggers to be silently dropped
- [ ] Added suppression for `httpx` and `openai` loggers — reduces noise in the log file
- [ ] Changed return value to `logging.getLogger('dashboard')` so logs from `chat.py` appear in the file

---

## `utilities/prompt.py`

- [ ] Added mandatory tool workflow to `AGENT_INSTRUCTIONS_PROMPT`: call `list-fields-fixed` once at the start of a conversation, never call it again if already called, then use only exact field names returned when calling `query-datasource-fixed`
- [ ] Added `DO NOT GUESS FIELD NAMES` restriction — prevents the model from hallucinating field names like "Country", "Sales", or "Region"

---

## `tableau-mcp-experimental/src/tools/queryDatasource/queryDatasourceFixed.ts`
*(requires `npm run build` after changes)*

- [ ] Changed `debug: true` → `debug: false` — removes SQL debug payload from every query response, significantly reducing token usage
- [ ] Added valid filterType reference table: SET, TOP, MATCH, DATE, QUANTITATIVE_NUMERICAL — with required fields and purpose for each
- [ ] Added explicit note that `CATEGORICAL` is not a valid filterType (common mistake from models trained on the Tableau REST API)
- [ ] Added SET filter value type rule: match value type to the field's `dataType` from `list-fields-fixed` — string fields use `["East"]`, integer fields use `[2010]`
- [ ] Added sorting placement note: `sortDirection` and `sortPriority` belong inside individual field objects, not at the root `query` level

---

## `tableau-mcp-experimental/src/config.ts`
*(required to fix startup crashes)*

- [ ] Replaced with merged version from main `tableau-mcp` repo base plus experimental additions
- [ ] Added `authConfig: AuthConfig` property — required by `restApiInstance.ts` for PAT authentication
- [ ] Added `fixedDatasourceLuid` parsing from `FIXED_DATASOURCE_LUID` environment variable
- [ ] Fixed `isToolGroupName` → `isToolName` — `isToolGroupName` is not exported by the experimental repo, causing build failure
