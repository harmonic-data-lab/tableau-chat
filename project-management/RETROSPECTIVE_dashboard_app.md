# Project Retrospective
**Project:** Tableau MCP Starter Kit — Dashboard Extension Setup  
**Date:** 2026-05-23

---

## What Didn't Work

- **The experimental repo was missing source files** — it forked from an older version of `tableau-mcp` and several modules didn't exist, requiring a manual `rsync` from the main repo before anything could build
- **`config.ts` was broken in multiple layers** — `jwtSubClaim` undefined, missing `authConfig` property, `isToolGroupName` not exported — each fix revealed the next, costing several restart cycles
- **The LLM generated invalid queries repeatedly** — wrong filter types (`CATEGORICAL` instead of `SET`), wrong value types for SET filters (strings vs integers for Year), `sortDirection`/`sortPriority` placed at the query root instead of inside field objects
- **`debug: true` was silently bloating every query response** — added SQL translation and execution plan to every tool result; wasn't noticed until the 200k TPM rate limit was hit
- **InMemorySaver state corruption** — when a request crashed mid-tool-call, the thread was permanently poisoned with an AIMessage containing dangling tool calls and no corresponding ToolMessages, causing every subsequent request to fail until a server restart
- **The rate limit retry loop** — enabling `handle_tool_errors=True` was the right fix, but combined with the LLM cycling through year values one by one, each request became a 20-step burn through the recursion limit before returning anything
- **Langfuse tracing was non-functional** — placeholder credentials caused a constant stream of 401 errors in the log, obscuring real errors and providing zero observability into LLM behaviour
- **The Superstore persona was hardcoded** — the agent was identifying itself as "Agent Superstore" and referencing the Superstore dataset even when connected to `global_disease_burden`

---

## What to Continue Doing

- **Step-by-step logging in `chat.py`** — once `[step N]` logs were added, the root cause of every loop became immediately visible without needing external tooling
- **Session-level UUID for thread ID** — provides multi-turn memory within a server session while guaranteeing a clean slate on restart; avoids the corruption problem of a static `"main_session"` string
- **`handle_tool_errors=True` on `ToolNode`** — the right architectural pattern; Zod and Tableau API errors feed back to the LLM as ToolMessages instead of crashing the request with a 500
- **Tool description as the first line of defence** — adding explicit filter type tables, value type rules, and sorting placement notes directly in the MCP tool description proved more effective than Python-side workarounds

---

## What to Do Better

- **Model choice** — `gpt-4o-mini` struggles to produce valid VizQL queries consistently; a smarter model (`gpt-4o` or `gpt-4.1`) would likely generate correct queries on the first attempt and avoid retry loops entirely
- **Set up Langfuse tracing from the start** — real credentials would have provided immediate visibility into tool calls, errors, and token usage without needing to build a custom step logger from scratch
- **Field type awareness in tool descriptions** — `list-fields-fixed` returns `dataType` (e.g. `INTEGER`, `STRING`) for every field, but neither the tool description nor the system prompt instructed the model to match filter value types to field data types; this caused the Year filter loop
- **Document the experimental repo setup** — it needs a clear README explaining what differs from the main `tableau-mcp` repo, which source files need to be copied across before building, and which exports are missing
- **Validate filter value types before sending to Tableau** — the Python-side filter validation correctly identified `"2010"` as a valid Year value (as a string), but the Tableau API rejected it because the field is `INTEGER`; the validator should cross-check value types against field `dataType`
