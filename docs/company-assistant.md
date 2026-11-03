# Company assistant

The **Ask Bishnoi** button at the bottom-right opens a floating chat panel for any signed-in company member. It is mounted once in the authenticated app layout, stays available across module navigation, and preserves the conversation while minimized. The top-bar shortcut was removed. Existing `/assistant` bookmarks open the same widget. Source access is checked separately. There are no record-creation, editing, deletion, SQL, shell, arbitrary-HTTP or administrative tools.

## Setup

The one-app frontend must resolve its public origin correctly behind a reverse proxy. It reuses the sign-in URL handling (forwarded host/protocol, including Cloudflare's visitor scheme). You can pin the existing server-side `ONE_APP_URL=https://one.bishnoi.ai` on the **one-app frontend** to use your canonical domain; restart/redeploy after changing it. The proxy must replace client-supplied forwarding headers. Assistant requests require an Origin matching this public URL; missing origins, other sites and cross-site browser requests are refused. A “Cross-site assistant requests are refused” error happens before Platform or Ollama is contacted; this is not an Ollama CORS setting.

1. On the **Platform backend**, set `OLLAMA_BASE_URL` to the private Ollama origin reachable from that server, for example `http://ollama:11434` on a private container network. Do not use `localhost` unless Ollama runs in the same network namespace. Keep this variable server-only; never prefix it with `NEXT_PUBLIC_`.
2. On the Ollama host, install `qwen3:1.7b` using `ollama pull qwen3:1.7b`. No Ollama service is started, installed or published by Bishnoi One. The integration fixes this model, sets `think: false`, and bounds output/context sizes. See the official [chat API](https://docs.ollama.com/api/chat) and [thinking controls](https://docs.ollama.com/capabilities/thinking).
3. Attach Ollama and Platform to a private network. Do not publish Ollama's port or add a public reverse-proxy route for it. The Platform refuses Ollama hostnames resolving to public, unspecified, link-local or multicast addresses, refuses redirects and ignores environment HTTP proxies. Firewall/container network rules remain the operator's responsibility.
4. **Company settings come from the Platform database.** Finance reads its database company through the existing authenticated `/connect/links` configuration flow. With exactly one active subscribed company, Platform resolves and pins that company once. With multiple possible companies, open Operations > Services (`/operations/apis`), select Finance, and choose **Database company** from the existing company list. Platform administrators alone can save this selection. No slug is typed and no `ASSISTANT_COMPANY_SLUG` or `CRM_COMPANY` environment variable is needed.
   - Platform stores a stable company ID on the Finance service registration (migration `0027`); it derives slug, currency and timezone from that company's existing record.
   - Once pinned, removing or suspending that company never silently selects another one. An operator must explicitly confirm any reassignment; changing this setting does not move or convert the database's financial records.
   - Finance assistant reads fetch this binding fresh and match **both** company ID and slug to the signed read pass. Unavailable Platform, missing/ambiguous binding, revoked subscription or a company mismatch fails closed. Incoming sign-in/read requests and old `.env` slugs cannot establish ownership.
   - The same company metadata supplies Finance's CRM integration company header and company name/currency/timezone while connected. A standalone, unconnected installation retains the existing optional legacy `CRM_COMPANY` behavior for its other integrations; the assistant requires Platform ownership.
5. The active company's Finance application must be registered with its correct API address. Deploy Platform, Finance and the one app. The existing audit tables are used; Platform migration `0027` adds the service database-company ID. Other workspace features may have their own migrations.

With Ollama unset, the rest of the application still works and chat reports that it is not configured. A public Ollama address is refused. The browser never sees the address, a delegated pass or a direct model response.

## Authorization and isolation

- Company membership, active account/company, password-change and required two-step setup are checked server-side. A stale browser tab asking for another company is rejected. Browser history is not trusted as company data.
- Directory reads require company administrator authority, an Administrator role, or the explicit **Read company directory names and job titles** (`directory.read`) ability on the member's company role. This is a Platform-only ability, not an app permission. No existing non-administrator role receives it automatically.
- Directory queries filter active, undeleted, non-operator employees by the authenticated company. Only names, recorded job titles and opaque record references are returned. No password, email, telephone, role policy or security details are disclosed. A President is not inferred to be CEO.
- Finance requires an active company subscription, the member's app grant (or their existing administrator standing grant), and `journal.view`, matching the accounting reports. Legacy grants without centralized role permissions are refused unless they explicitly carry app administrator authority.
- Platform signs a 60-second `assistant-read` pass for the single `monthly-summary` tool, authenticated identity and active company. Finance verifies the signature, issuer, audience, kind/tool, permission and fresh Platform database-company binding before querying. The pass cannot be used as a browser login or a business write command. Finance reports currently have company-wide scope; per-person financial questions are unsupported.
- While any View as preview is active, the browser chat route refuses to use the underlying administrator's account. Stop viewing first.

## Data and calculations

Plain questions need no model (2026-11-03): a greeting, and the **total number of employees** ("How many employees do we have?") are recognised by fixed rules and answered from the directory count (active, undeleted, non-operator employees of the company; switched-off ones are mentioned), for the same people who may read the directory. A narrower count (per department, per team) isn't supported yet and goes to the model, which refuses it.

Ollama performs **intent planning only** using a strict schema (`directory`, `finance`, `clarify`, `unsupported`). It receives bounded user questions and a trusted current date, not employee records, financial results, credentials or SQL schemas. Raw model output and thinking are never streamed to the user. Fixed backend templates produce answers from authorized tool results, preventing the model from inventing names, numbers or source links.

Finance supports one explicit calendar month per question; an unclear month/year prompts clarification. A current month is truncated to today in Finance's company timezone, and future dates do not return actuals.

- **Revenue:** `management.revenue`, issued invoice totals less VAT by invoice date; drafts and voids excluded.
- **Expenses:** expense-account debits minus credits in approved journal entries.
- **Net profit:** journal income minus journal expenses, using `bir_reports.income_statement`. Journal income can include other income, so it is shown separately and may differ from invoiced revenue. Recorded cost of goods sold is included through expense accounts.
- **Approval correction:** `bir_reports.balances` now filters approved entries, matching the journal's documented rule. Waiting/rejected entries do not contribute to accounting statements.
- Missing invoices produce an unavailable revenue value; missing approved income/expense journal lines produce unavailable expenses/profit. Recorded zero values remain valid zero values. The assistant cannot assess whether the books are complete.

Every factual reply includes source references, retrieval time and financial date range when applicable. Financial sources link to Key figures and Profit and loss with the same date parameters. No values are inferred from the model's training data or another company.

## Streaming, limits and audit

The browser posts only to `/api/assistant/chat`; the Next server authenticates using the httpOnly account cookie and relays the Platform's SSE stream. Events are status, verified sources, answer text, error and done. Source records and numeric results never go back to Ollama. The model's structured planning finishes before verified answer text streams; this is deliberately not raw token streaming of an unconstrained answer.

Model calls have a bounded timeout; an entire backend request is bounded to 45 seconds. Finance requests have a separate 12-second timeout. The browser proxy bounds requests to 20 KB and waits at most 50 seconds. Questions are 2,000 characters, recent user context 8,000 characters total, and model plans 32 KB. There is no saved conversation database or browser storage. New chat clears the conversation; sign-out, company/account change, or a full reload drops it. Minimize and client-side page navigation preserve it. The panel is sized to the viewport, has an independently scrolling history and a fixed composer, supports Escape and focus return, and is hidden when printing.

Per worker: at most one active request per member/company, four requests active globally, and eight starts per member/company per minute, in addition to the existing HTTP guard. For a multi-worker installation, an upstream rate limit is needed for a cluster-wide quota; local limits are not billed usage controls.

The Platform audits completed, failed, denied and cancelled streamed lookups with actor, company and tool. Finance audits authorized monthly reads. Prompt text, conversation text, tokens, raw model output and financial values are not written to audit logs. No business records are modified.

## Verification

Backend tests use mocked Ollama and delegated Finance transports, disposable SQLite databases and the existing fixtures. They cover authorization, missing data, company binding, read isolation, recorded directory facts, malformed intents/timeouts and the approved accounting calculations. Frontend tests exercise split SSE frames, interrupted streams and errors. A live private Ollama deployment and PostgreSQL deployment still need an operator smoke test after configuration.

Latest local checks (2026-11-03): Platform assistant/catalog/ability tests 16 passed; Finance assistant/report/sign-in/BIR-report/journal-approval tests 41 passed; frontend SSE tests 3 passed; Next.js frontend TypeScript check passed. Live Ollama, browser and PostgreSQL smoke tests were not run.

Company-configuration checks (2026-11-03): Platform binding/connection tests 6 passed; Finance assistant/configuration tests 10 passed. These verify pinned ownership, an unambiguous automatic selection, explicit operator choices, current company fields, revoked access, stable service encryption keys and no stale/environment fallback for assistant reads.
