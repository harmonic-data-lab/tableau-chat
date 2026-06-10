# CHAD Implementation Plan — Dashboard Chat Assistant for Tableau

**Audience:** Claude Opus 4.8, acting as the implementing engineer in this codebase.
**Author context:** Plan produced from a requirements interview with the project owner on 2026-06-09. Demo for leadership is in **3 days**. Phase 1 must be complete in **2 days**.

---

## 1. Context — what exists today

- **CHAD** (Chat Assistant Dashboard) is a Tableau dashboard extension built on **The Information Lab's `tableau_mcp_starter_kit`** (https://github.com/TheInformationLab/tableau_mcp_starter_kit): a **Python/LangChain** application that serves the extension web UI and runs the agent loop server-side.
- The starter kit spawns the **official Tableau MCP server** (`@tableau/mcp-server`, https://github.com/tableau/tableau-mcp) as a child process via `TRANSPORT='stdio'`, pointed at a local build path (`TABLEAU_MCP_FILEPATH` in `.env`).
- Auth to Tableau is a **single PAT** in `.env`. The LLM is **Azure-hosted GPT-4o** (key also in `.env`, read server-side only).
- Everything currently runs from the owner's local machine in VS Code. **It works end-to-end today.** Do not break the working baseline.
- **Tableau Server (on-prem) 2025.1.8.** VizQL Data Service is enabled and `query-datasource` calls succeed. The server upgrades to 2025.3.6 five days from now (two days *after* the demo) — irrelevant to this plan; do not target 2025.3 features.
- **Scope of data:** one workbook, 4 dashboards. Each dashboard has a dedicated **published** data source (published copies of the originally embedded sources). CHAD may need to query more than one of them for complex questions.
- **No row-level security** on any of the four data sources. PAT-based auth is acceptable for v1.
- The Extensions API is **not yet integrated** — the chat is currently blind to dashboard state. That integration is the centerpiece of Phase 1.

## 2. Goals

1. **Demo-ready in 2 days:** a polished, single-user happy path running from the owner's laptop (Tableau Desktop hosting the extension from localhost).
2. **Dashboard-grounded answers:** CHAD answers questions about what is on screen using the *exact* data displayed, so answers never contradict the dashboard.
3. **Hybrid depth:** for questions beyond what's displayed, CHAD queries the published data sources via the Tableau MCP server, replaying the dashboard's current filters so deeper answers stay consistent with the on-screen view.
4. **Architecture that survives the refactor:** changes made now should not have to be undone when CHAD later moves to a Linux server, gets its own repo, and switches the MCP transport to HTTP.

## 3. Non-goals for Phase 1 (explicitly out of scope — do not build)

- **Linux server deployment.** The nonprod server's configuration and outbound network access are unverified. Demo runs from the laptop. (Phase 2.)
- **Per-user OAuth / Connected Apps.** PAT auth stands for the demo. With no RLS, this is an access-control gap, not a data-security gap. (Phase 2.)
- **Repo refactor / extraction from the starter kit.** Work within the existing project structure; keep new code in clearly separated modules so extraction is easy later. (Phase 2.)
- **Mark-selection awareness.** Subscribe only to filter and parameter changes. (Phase 2.)
- **Conversation persistence, multi-workbook configuration, usage telemetry.** (Phase 2.)
- **Dependency upgrades of any kind**, including `@tableau/mcp-server`. Pin/freeze everything as found. Stability beats freshness until after the demo.

## 4. Phase 1 — demo-critical work (next 2 days)

### Task 1.1 — Dashboard state capture module (extension front end)

Create a self-contained JS module (e.g. `dashboardState.js`) in the extension UI.

**Behavior:**
1. On extension load, call `tableau.extensions.initializeAsync()`.
2. Build a capture function that gathers, for the hosting dashboard:
   - **Worksheets:** `dashboard.worksheets`, names included.
   - **Filters per worksheet:** `worksheet.getFiltersAsync()`. Serialize by filter type: categorical → field name + applied values (+ `isExcludeMode`); range → field + min/max; relative date → field + period/range descriptor.
   - **Parameters:** `dashboard.getParametersAsync()` → name, current value, data type.
   - **Summary data per worksheet:** `worksheet.getSummaryDataAsync({ maxRows: <cap>, ignoreSelection: true })`. Default cap **500 rows per worksheet**, configurable. Record `isTotalRowCountLimited` (or compare returned vs total) and include a `truncated: true` flag in the payload when the cap is hit. If the installed Extensions API version lacks `maxRows` on `getSummaryDataAsync`, use `getSummaryDataReaderAsync` and read only the first page(s) up to the cap.
3. Subscribe to change events and set a `stale` flag — **do not** re-capture on every event (filter changes can fire in bursts):
   - `worksheet.addEventListener(tableau.TableauEventType.FilterChanged, …)` on every worksheet.
   - `parameter.addEventListener(tableau.TableauEventType.ParameterChanged, …)` on every parameter.
4. **Capture-on-send pattern:** when the user submits a chat message, if `stale` (or no capture yet), run a fresh capture and attach it to the request. This guarantees the agent always sees the state as of the question, with zero synchronization complexity. Show a brief "Reading dashboard…" state in the UI while capturing.

**Payload schema** (attach as `dashboard_context` on the chat request):

```json
{
  "dashboard_name": "string",
  "captured_at": "ISO-8601",
  "parameters": [{ "name": "string", "value": "any", "dataType": "string" }],
  "worksheets": [
    {
      "name": "string",
      "filters": [
        { "field": "string", "type": "categorical", "values": ["..."], "exclude": false },
        { "field": "string", "type": "range", "min": 0, "max": 0 },
        { "field": "string", "type": "relative-date", "description": "string" }
      ],
      "summary_data": {
        "columns": [{ "name": "string", "dataType": "string" }],
        "rows": [["..."]],
        "truncated": false,
        "total_row_count": 0
      }
    }
  ]
}
```

**Acceptance criteria:**
- [ ] Extension initializes in Tableau Desktop with no console errors.
- [ ] Changing any filter or parameter, then sending a message, results in a payload reflecting the *new* state.
- [ ] A worksheet with > cap rows produces `truncated: true` and exactly cap rows.
- [ ] Capture of a typical 4-worksheet dashboard completes in under ~2 seconds.
- [ ] If capture fails (e.g. a worksheet errors), the chat still works — send the message with partial context plus an `errors` array rather than blocking.

### Task 1.2 — Backend: accept and inject dashboard context (Python/LangChain)

1. Extend the chat endpoint to accept the optional `dashboard_context` object.
2. Render it into a clearly delimited context block (compact — tabular text for summary data, not raw JSON dumps) and inject it into the agent's prompt **per message**, not once per session, since state changes between messages.
3. Add a **data source manifest** as configuration (e.g. `manifest.json` or a `.env`-referenced file): for each of the 4 dashboards, the published data source **name, LUID, and a one-line description of its grain/contents**. Inject the manifest into the system prompt. This removes the need for the agent to spend tool calls discovering data sources and tells it which sources may be joined for cross-source questions.
4. Token budget: a 500-row × 10-column summary table per worksheet × 4 worksheets can be large. Render summary data compactly (CSV-style lines); if the rendered context block exceeds a configurable character budget (default ~60k chars), drop summary-data rows evenly per worksheet and note the truncation in the block.

**Acceptance criteria:**
- [ ] A request without `dashboard_context` behaves exactly as today (backward compatible).
- [ ] With context present, the model's prompt contains the state block and the manifest (verify via debug logging / Langfuse if configured).
- [ ] Oversized contexts are truncated gracefully, never erroring.

### Task 1.3 — Hybrid routing system prompt

Replace/extend the agent's system prompt with routing rules. Draft to adapt:

> You are CHAD, a chat assistant embedded in a Tableau dashboard. With each user message you receive DASHBOARD CONTEXT: the dashboard's current filters, parameters, and the exact summary data of each worksheet as currently displayed.
>
> Routing rules:
> 1. If the question is about what is currently shown (totals, comparisons, trends visible on the dashboard), answer **only** from the provided summary data. Never re-derive these numbers by querying.
> 2. If the question goes beyond what is shown (different fields, finer grain, other time ranges, cross-data-source questions), use your query tools against the data sources listed in the DATA SOURCE MANIFEST. When you query, apply the dashboard's currently active filters and parameter values to your query wherever the same fields exist, so your answer is consistent with the user's current view. If you intentionally ignore a dashboard filter (e.g. the user asks "across all regions"), say so explicitly.
> 3. In every answer, state your source: "from the dashboard as displayed" or "queried from <data source name>".
> 4. If a queried result appears to conflict with displayed data, trust the displayed data for what's on screen and explain the difference (e.g. filters not applied in your query).
> 5. If summary data is marked truncated and the question needs the full data, query the data source instead, applying the dashboard filters.

**Acceptance criteria** (manual test set — see Task 1.5):
- [ ] "What's the total <measure> shown right now?" → answered from context, value matches the dashboard exactly, no tool calls made.
- [ ] Change a filter, ask again → answer changes accordingly.
- [ ] A question requiring data not on the dashboard → agent queries the correct data source per the manifest and mentions which filters it applied.
- [ ] A cross-data-source question → agent queries ≥2 sources and synthesizes.

### Task 1.4 — UX polish for demo latency

A GPT-4o agent loop with 2–3 tool calls takes 20–40 seconds. Add a visible status indicator in the chat UI: at minimum a staged status line ("Reading dashboard…", "Thinking…", "Querying <data source>…", "Writing answer…"), driven by backend events if streaming is available, otherwise by optimistic client-side stages. Also add a friendly error state with a Retry button — never a blank hang.

**Acceptance criteria:**
- [ ] User always sees activity within 1 second of sending a message.
- [ ] Tool-call phases are visible when the agent queries.
- [ ] A backend failure shows a readable message and Retry, and Retry works.

### Task 1.5 — Demo hardening (half-day, do not skip)

1. **Freeze dependencies:** lock Python requirements; record the exact `tableau-mcp` build in use; verify `.env` files are git-ignored. No upgrades.
2. **Scripted demo run:** create `DEMO.md` with the exact three-tier question script: (a) "what's shown" question → matches the screen; (b) live filter change + re-ask → answer follows the dashboard; (c) a beyond-the-dashboard question hitting one data source, and one cross-source question. Include expected answers.
3. **Fallback assets:** after a successful rehearsal, save screenshots/screen recording of each scripted step.
4. **Smoke test script** (manual checklist is fine): MCP server starts, `query-datasource` succeeds against each of the 4 LUIDs, Azure endpoint reachable, extension loads in Tableau Desktop.

## 5. Phase 2 — post-demo backlog (priority order)

1. **Linux deployment:** verify outbound access from the nonprod box to Tableau Server and the Azure OpenAI endpoint; run Tableau MCP server as its own systemd service via `npx -y @tableau/mcp-server@latest` with `TRANSPORT=http`; run the CHAD Python backend as a second systemd service pointing at the MCP server's HTTP endpoint; provision HTTPS for the extension URL; have a Tableau Server admin add the extension URL to the extensions safe list. Update the `.trex` manifest to the served URL.
2. **Repo extraction:** CHAD becomes its own repository; the starter kit becomes ancestry. The MCP server endpoint, data source manifest, model config, and row caps all become configuration. Module boundaries created in Phase 1 (state-capture JS module, context-injection layer, manifest config) should lift out cleanly.
3. **Per-user OAuth (Connected Apps):** users sign in with their Tableau identity; queries execute as the user. Required before any rollout beyond a trusted pilot group; framed to stakeholders as access control and auditability (not data security, since there is no RLS).
4. **Mark-selection awareness** (`MarkSelectionChanged` + `getSelectedMarksAsync`) so users can select marks and ask "why is this point an outlier?"
5. **Observability and cost:** wire up the starter kit's Langfuse hooks; log tool calls, latency, token usage per question.
6. **Conversation history, multi-workbook config, response streaming.**

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Summary data too large → token blowups, slow/expensive calls | Row caps + character budget + truncation flags (Tasks 1.1/1.2) |
| Agent re-queries on-screen numbers and gets a mismatching answer | Routing rule 1 + rule 4 (trust displayed data); rehearse tier-(a) questions |
| Filter replay imperfect (filter field absent from the queried source) | Rule 2 requires the agent to disclose which filters were applied/skipped |
| Demo-day environment drift | Dependency freeze, no upgrades, rehearsal + screenshot fallback |
| Latency feels broken to executives | Status indicator (Task 1.4); pre-warm with one query before the demo |

## 7. Working agreements for the implementing agent

- The local end-to-end flow works today. Make changes incrementally and verify the baseline still runs after each task.
- Keep all new code in separable modules with config-driven values (row caps, character budgets, manifest path) — Phase 2 extraction depends on it.
- Do not touch auth, transports, or dependency versions in Phase 1.
- Where the installed Extensions API or starter-kit version differs from assumptions above (e.g. `getSummaryDataAsync` options), check the actual installed version in `node_modules` / the loaded `tableau.extensions` API and adapt rather than upgrading.
