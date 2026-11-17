# System map

What each app has, read from the code on 2026-11-17 by `scripts/system_map.py`.
Don't edit by hand: change the code, then run `python scripts/system_map.py` again.
Settings are listed by name only. The feature plan (Desktop, `bishnoi-one-feature-plan.html`) says where each app is going.

## At a glance

| App | Address | Screens | Records (tables) | Reports | Permission areas | API endpoints | Latest migration |
|---|---|---|---|---|---|---|---|
| [Platform (Admin Console)](#platform-admin-console) | `/platform` | 17 | 42 | 0 | 0 | 188 | 0029_dropped_features |
| [CRM](#crm) | `/crm` | 21 | 55 | 22 | 12 | 264 | 0083_dropped_features |
| [Inventory](#inventory) | `/inventory` | 18 | 45 | 35 | 14 | 181 | 0024_dropped_features |
| [Finance (Books)](#finance-books) | `/finance` | 28 | 56 | 27 | 18 | 211 | 0036_drop_foreign_currency_bills |
| [Pharmacy](#pharmacy) | `/pharmacy` | 11 | 23 | 14 | 12 | 84 | 0007_recycle_bin |
| [Executive Admin (Office)](#executive-admin-office) | `/admin` | 13 | 23 | 14 | 12 | 75 | 0011_recycle_bin |
| [In-Licensing](#in-licensing) | `/in-licensing` | 0 | 2 | 0 | 0 | 7 | 0002_record_numbers |
| [Regulatory](#regulatory) | `/regulatory` | 0 | 2 | 0 | 0 | 7 | 0002_record_numbers |

## Platform (Admin Console)

Code in `backend/modules/platform`, its API under `/platform` in the one backend, screens at `/platform` in the one app.

### Screens (the sidebar)

- **Pages:** Home (`/platform/home`)
- **Employees:** Employees (`/platform/roles/people`), Roles (`/platform/roles`), Organisation (`/platform/organisation`)
- **Company:** Company profile (`/platform/company`), Security (`/platform/company/security`), Activity log (`/platform/company/activity`), Data clean-up (`/platform/company/data-cleanup`)
- **App settings:** CRM (`${CRM_SETTINGS}/company`), Integrations (`/platform/company/integrations`), Reports (`/platform/reports`)
- **Companies:** Companies (`/operations/companies`), Find a person (`/operations/people`), Operators (`/operations/operators`)
- **Services:** Services and connections (`/operations/apis`)
- **Troubleshooting:** Events between apps (`/operations/events`), Your profile (`/platform/account`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbpl_users` | User |
| `nbpl_sessions` | One sign-in |
| `nbpl_accounts` | A person, once across Bishnoi One: their email, name, the one password, and whether they are an operator (they run Bishnoi One itself: the O |
| `nbpl_sign_in_links` | A one-time link (app/sign_in.py): forgot password ("reset"), a new person setting their own password ("invite"), or a sign-in waiting for it |
| `nbpl_sign_in_failures` | A wrong password, by email: counted for the lockout, in the database so a restart doesn't forget |
| `nbpl_signatures` | A person's e-signature on their account (step 10, app/signatures.py) |
| `nbpl_companies` | Company |
| `nbpl_org_units` | A department or a branch of one company |
| `nbpl_units` | One box on a company's org chart: a division, a department or a team, under another (or at the top), with the membership that heads it and t |
| `nbpl_branches` | Where people work (Main office, Cebu) |
| `nbpl_unit_heads` | Who heads a unit (2026-11-04): any number of people |
| `nbpl_membership_units` | A unit beyond a membership's main one: widens what they see and approve; reports still count them under their main unit |
| `nbpl_applications` | Application |
| `nbpl_deployments` | Deployment |
| `nbpl_integrations` | Something an application depends on outside itself: a payment gateway, another app's API, a mail service |
| `nbpl_app_links` | One application uses another (the CRM uses Inventory): the caller is given the other's address and a key, the other accepts that key |
| `nbpl_service_connections` | A company's details for an outside service (Zoho Books, Gmail...): which ones and what they need are in app/services.py |
| `nbpl_company_apps` | A company may use an application |
| `nbpl_company_passes` | A company pass the platform gave an application: asked for (every hour) or sent to it when the company changed (app/company_push.py) |
| `nbpl_identities` | A person at a company: their standing there (title, whether they run it, the applications they have) |
| `nbpl_access_roles` | AccessRole |
| `nbpl_access_role_abilities` | One ability a role has (app/abilities.py), with its limit where it takes one (step 6) |
| `nbpl_access_role_permissions` | One permission of one module ("crm", "customers.edit") |
| `nbpl_access_role_scopes` | Whose records the role reaches in one module, where the module has scopes (own, team, all) |
| `nbpl_saved_reports` | A report someone built from one of a module's reports (decided 2026-10-26): which report it starts from, and what was chosen (columns, filte |
| `nbpl_identity_sessions` | One sign-in to a Bishnoi One account (not the console's staff sign-in) |
| `nbpl_identity_apps` | One person may use one application, with a role there |
| `nbpl_access_requests` | AccessRequest |
| `nbpl_tickets` | Ticket |
| `nbpl_ticket_notes` | A note on a ticket, or a change of its status (then both are set) |
| `nbpl_incidents` | Something happening now that stops people working, as opposed to a ticket, which is one person's report of something wrong |
| `nbpl_incident_companies` | A company the incident reaches |
| `nbpl_incident_updates` | IncidentUpdate |
| `nbpl_health_checks` | One look at whether something answers, and how fast |
| `nbpl_traffic` | The Platform API's own requests, one row per minute |
| `nbpl_audit` | Who did what, and when |
| `nbpl_events` | Something meaningful one app (or the platform) said happened at a company, kept once by its id |
| `nbpl_event_deliveries` | One event to one app that takes it (app/events.py) |
| `nbpl_document_links` | One link in the document chain (step 9, app/document_chain.py): this document came from that one |
| `nbpl_announcements` | Something the platform tells people |
| `nbpl_settings` | One section of Settings, as JSON (see app/platform_settings.py) |
| `nbpl_access_policy_imports` | An administrator-owned preview and, once applied, an immutable policy version |

### Reports

- None.

### Permissions

- None declared.

### Links to other apps

- **Calls:** none
- **Offers to other apps:** `GET /platform/integrations`, `POST /platform/applications/{app_id}/integrations`, `PATCH /platform/integrations/{integration_id}`, `DELETE /platform/integrations/{integration_id}`, `GET /connect/links`, `GET /platform/connections`, `POST /connect/hello`, `POST /platform/applications/{app_id}/connect-key`, `DELETE /platform/applications/{app_id}/connect-key`, `POST /connect/events`, `GET /connect/signature`, `GET /connect/services`

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `BACKUP_FROM`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `SESSION_HOURS`, `IDENTITY_SESSION_HOURS`, `PASS_SIGNING_KEY`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `REQUIRE_TWO_STEP`, `RESET_LINK_HOURS`, `INVITE_LINK_HOURS`, `CRON_SECRET`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `ONE_APP_URL`, `BACKEND_URL`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_ANNOUNCEMENTS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`

### API endpoints

<details><summary>188 endpoints in 25 files</summary>

- **access:** `GET /platform/access/requests`, `POST /platform/access/requests`, `POST /platform/access/requests/{request_id}/decision`, `GET /platform/access/organizations`, `GET /platform/access/applications`, `GET /platform/access/roles`, `GET /platform/staff`, `POST /platform/staff`, `PATCH /platform/staff/{staff_id}`, `POST /platform/staff/{staff_id}/password`, `DELETE /platform/staff/{staff_id}`, `GET /platform/sessions`, `DELETE /platform/sessions/{session_id}`, `DELETE /platform/access/requests/{request_id}`
- **access_policy:** `GET /identity/access/policy/context`, `POST /identity/access/policy/prompt`, `GET /identity/access/policy/export`, `POST /identity/access/policy/validate`, `POST /identity/access/policy/{draft_id}/apply`, `GET /identity/access/policy/history`, `GET /identity/access/policy/history/{version_id}`
- **activity:** `GET /platform/activity`
- **applications:** `GET /platform/applications`, `POST /platform/applications`, `GET /platform/applications/{app_id}`, `POST /platform/applications/adopt-address`, `PATCH /platform/applications/{app_id}`, `POST /platform/applications/{app_id}/deployments`, `GET /platform/deployments`, `GET /platform/integrations`, `POST /platform/applications/{app_id}/integrations`, `PATCH /platform/integrations/{integration_id}`, `DELETE /platform/integrations/{integration_id}`, `DELETE /platform/applications/{app_id}`, `DELETE /platform/deployments/{deployment_id}`
- **auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `PATCH /auth/me`, `POST /auth/password`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/view-as`, `POST /auth/leave`
- **communications:** `GET /platform/announcements`, `POST /platform/announcements`, `PATCH /platform/announcements/{notice_id}`, `DELETE /platform/announcements/{notice_id}`
- **companies:** `GET /platform/companies`, `POST /platform/companies`, `GET /platform/companies/{company_id}`, `PATCH /platform/companies/{company_id}`, `PUT /platform/companies/{company_id}/applications`, `POST /platform/companies/{company_id}/units`, `PATCH /platform/companies/{company_id}/units/{unit_id}`, `DELETE /platform/companies/{company_id}/units/{unit_id}`, `DELETE /platform/companies/{company_id}`
- **company_access:** `GET /identity/access`, `POST /identity/access/roles`, `PATCH /identity/access/roles/{role_id}`, `GET /identity/access/abilities`, `POST /identity/access/roles/from-job`, `PUT /identity/access/roles/{role_id}/abilities`, `DELETE /identity/access/roles/{role_id}`, `PUT /identity/access/people/{person_id}/role`, `POST /identity/access/people`, `PATCH /identity/access/people/{person_id}`, `GET /identity/access/standard/{level}`, `PUT /identity/access/people/{person_id}/reporting`, `POST /identity/access/people/{person_id}/password`, `PUT /identity/access/people/{person_id}/apps/{key}`, `GET /identity/access/people/{person_id}`, `PUT /identity/access/people/{person_id}/apps/{key}/role`, `DELETE /identity/access/people/{person_id}/apps/{key}`, `POST /identity/access/import`, `DELETE /identity/access/people/{person_id}`, `GET /identity/access/bin`, `POST /identity/access/people/{person_id}/restore`, `POST /identity/access/people/{person_id}/erase`, `POST /identity/access/people/{person_id}/invite`, `POST /identity/access/people/{person_id}/two-step/reset`, `POST /identity/access/people/import`
- **company_console:** `GET /identity/company/letterhead`, `GET /identity/company`, `PATCH /identity/company`, `GET /identity/company/apps`, `GET /identity/company/services`, `PUT /identity/company/services/{key}`, `POST /identity/company/services/{key}/check`, `GET /identity/company/activity`, `GET /identity/company/security`, `POST /identity/company/security/people/{person_id}/sign-out`, `GET /identity/company/administrators`, `PUT /identity/company/administrators/{person_id}`, `GET /identity/company/overview`, `GET /identity/company/reports`, `GET /identity/company/reports/{key}`
- **connections:** `GET /connect/links`, `GET /platform/connections`, `POST /connect/hello`, `POST /platform/applications/{app_id}/connect-key`, `DELETE /platform/applications/{app_id}/connect-key`, `POST /platform/links`, `PATCH /platform/links/{link_id}`, `POST /platform/links/{link_id}/new-key`, `DELETE /platform/links/{link_id}`
- **dashboard:** `GET /platform/dashboard`, `GET /platform/banner`, `GET /platform/options`, `GET /platform/frame`
- **events:** `POST /connect/events`, `GET /platform/events`, `POST /platform/events/{event_id}/{target}/retry`, `POST /platform/events/{event_id}/{target}/skip`, `POST /platform/events/run`, `POST /platform/events/check`, `GET /cron/events-check`
- **identity:** `POST /identity/login`, `POST /identity/login/code`, `POST /identity/logout`, `GET /identity/me`, `POST /identity/switch`, `POST /identity/pass`, `POST /identity/password`, `GET /identity/signature`, `PUT /identity/signature`, `POST /identity/signature/remove`, `GET /connect/signature`, `GET /identity/documents/trail`, `GET /pass/key`, `POST /identity/password/forgot`, `GET /identity/password/link`, `POST /identity/password/set`, `GET /identity/two-step`, `POST /identity/two-step/start`, `POST /identity/two-step/confirm`, `POST /identity/two-step/off`
- **incidents:** `GET /platform/incidents`, `POST /platform/incidents`, `GET /platform/incidents/{incident_id}`, `PATCH /platform/incidents/{incident_id}`, `POST /platform/incidents/{incident_id}/updates`, `DELETE /platform/incidents/{incident_id}`
- **monitoring:** `GET /platform/monitoring`, `GET /platform/monitoring/history`, `GET /platform/traffic`
- **operators:** `GET /platform/operators`, `PUT /platform/operators/{account_id}`, `POST /platform/operators`
- **organisation:** `GET /identity/organisation`, `POST /identity/organisation/units`, `PATCH /identity/organisation/units/{unit_id}`, `POST /identity/organisation/branches`, `PATCH /identity/organisation/branches/{branch_id}`, `PUT /identity/organisation/people/{person_id}`
- **profile:** `GET /auth/account`, `GET /auth/profile`, `PUT /auth/profile`, `GET /auth/activity`
- **public:** `GET /public/applications`, `GET /public/notices`, `GET /public/company-pass`
- **saved_reports:** `GET /identity/reports`, `GET /identity/reports/{report_id}`, `POST /identity/reports`, `PATCH /identity/reports/{report_id}`, `DELETE /identity/reports/{report_id}`
- **services:** `GET /platform/companies/{company_id}/services`, `PUT /platform/companies/{company_id}/services/{key}`, `POST /platform/companies/{company_id}/services/{key}/check`, `GET /connect/services`
- **settings:** `GET /platform/settings`, `PUT /platform/settings/{section}`
- **support:** `GET /platform/tickets`, `POST /platform/tickets`, `GET /platform/tickets/{ticket_id}`, `PATCH /platform/tickets/{ticket_id}`, `POST /platform/tickets/{ticket_id}/notes`, `DELETE /platform/tickets/{ticket_id}`
- **unset:** `GET /platform/unset`
- **users:** `GET /platform/users`, `POST /platform/users`, `GET /platform/users/{user_id}`, `PATCH /platform/users/{user_id}`, `PUT /platform/users/{user_id}/applications/{app_id}`, `DELETE /platform/users/{user_id}/applications/{app_id}`, `DELETE /platform/users/{user_id}`, `POST /platform/users/{user_id}/password`

</details>

## CRM

Code in `backend/modules/crm`, its API under `/crm` in the one backend, screens at `/crm` in the one app.

### Screens (the sidebar)

- **Home:** Dashboard (`/crm`)
- **Sales:** Customers (`/crm/customers`), Contacts (`/crm/contacts`), Deals (`/crm/deals`), Quotes (`/crm/quotes`), Sales orders (`/crm/sales`), Order links (`/crm/order-links`), Retention (`/crm/retention`)
- **Activities:** Calendar (`/crm/calendar`), Activities (`/crm/activities`)
- **Field sales:** Team progress (`/crm/field`), Accounts to visit (`/crm/field/doctors`), Visits (`/crm/visits`), Patient assistance (`/crm/field/assistance`)
- **Products:** Products (`/crm/products`), Price books (`/crm/prices`), Promotions (`/crm/promos`), Bundles (`/crm/bundles`)
- **Documents:** Documents (`/crm/media`), Promotional materials (`/crm/materials`)
- **Reports:** Reports (`/crm/reports`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbcm_teams` | Team |
| `nbcm_roles` | Role |
| `nbcm_role_permissions` | RolePermission |
| `nbcm_user_teams` | One of the other teams a person is in (their main team is users.team_id) |
| `nbcm_users` | User |
| `nbcm_user_managers` | Who sees a person (2026-11-04, from the platform): the heads of their unit and of every unit above it, and who they were linked to by hand |
| `nbcm_platform_passes` | A pass from the platform already taken: each one works once |
| `nbcm_sessions` | One sign-in |
| `nbcm_audit_log` | Who changed what, and when |
| `nbcm_customer_types` | What kind of customer a company is: Prospect, Customer, Partner |
| `nbcm_companies` | Company |
| `nbcm_contacts` | Contact |
| `nbcm_activities` | A call, meeting, email, note or task, about a company and/or a contact |
| `nbcm_price_types` | A way of pricing a quote: "Patient", "Drugstore/Hospital", "Requested price" |
| `nbcm_products` | Product |
| `nbcm_product_prices` | The company's price for a product under a price type |
| `nbcm_team_price_types` | The price types a team quotes with |
| `nbcm_team_prices` | A team's own price, standing over the company's for its quotes |
| `nbcm_promos` | A price promotion |
| `nbcm_bundles` | Products sold together at one set price |
| `nbcm_issuers` | Who may pay for a quote with a guarantee letter: DSWD, PCSO |
| `nbcm_sales_settings` | The CRM's own rules |
| `nbcm_quotes` | A priced offer to a company or a contact |
| `nbcm_stored_files` | An uploaded file (a quote's guarantee letter), kept in the database itself: a server without a lasting disk (Vercel) keeps it all the same,  |
| `nbcm_form_sections` | FormSection |
| `nbcm_form_fields` | FormField |
| `nbcm_balances` | What a doctor owed on a date, as accounting said (Field work → Upload balances) |
| `nbcm_visits` | A field agent's visit to a doctor, and what came of it: a payment collected (with its receipt), a promise to pay, nobody in, details updated |
| `nbcm_trail_batches` | Where a field agent went while the CRM was open: one row per upload (about every 15 minutes), its points packed (app/trail.py) |
| `nbcm_route_days` | One person's day on the road, summed up as their trail comes in |
| `nbcm_price_groups` | A group of customers priced alike: Hospital, Drugstore chain, Clinic |
| `nbcm_price_conditions` | One pricing rule, over the days it applies |
| `nbcm_quote_templates` | A quotation form an admin set up: designed here ("form"), or their own Excel form uploaded and filled in ("excel") |
| `nbcm_quote_controls` | The control number a quote got on a template, the first time it was printed or downloaded with it; the same number every time after |
| `nbcm_deal_stages` | A step a deal goes through: Qualify, Proposal, Negotiation |
| `nbcm_deals` | Business expected from a customer: how much, by when, and how likely |
| `nbcm_merged_records` | A customer or contact merged into another (Customers → Possible duplicates) |
| `nbcm_not_duplicates` | Two records someone said are different, so they aren't offered again |
| `nbcm_kpis` | Kpi |
| `nbcm_kpi_targets` | A KPI's target for a month (YYYY-MM), for one person or one team |
| `nbcm_scorecards` | A division's monthly scorecard from its sales playbook, for its reps, coaches or mentor (app/scorecards.py scores it) |
| `nbcm_kpi_entries` | A manual KPI's result for a person and a month, entered by hand |
| `nbcm_connections` | No longer used (since 2026-10-09): outside services are connected on Bishnoi One Platform, per company (app/connections.py) |
| `nbcm_attention_rules` | When something is worth a prompt on the home page: one row for everyone (team_id None), and a row for a division that wants its own |
| `nbcm_attention_dismissals` | A prompt someone put aside: until a day (snoozed), or for good (None) |
| `nbcm_media` | An approved presentation, PDF or video that reps show customers: a file kept here (StoredFile), or a link to one kept elsewhere (a shared dr |
| `nbcm_association_labels` | What a link between two kinds of record means, read from each side: a doctor "Works at" a hospital, whose page lists them under "People here |
| `nbcm_associations` | One record linked to another, with a label |
| `nbcm_activity_links` | An activity on more customers than its own: a visit note on the doctor and the hospital |
| `nbcm_quote_links` | A link a rep gives a customer to order from (app/routers/quote_links.py): the customer searches the medicines at their own prices, picks qua |
| `nbcm_material_requests` | Promotional materials Admin asks to give to a team (or one person in it): the team's manager approves or rejects it here (app/routers/materi |
| `nbcm_plan_stops` | A doctor on a field agent's plan for a day (Rx playbook: red zone in the morning, yellow midday, green in the afternoon; at least 8 a day) |
| `nbcm_week_plans` | A field agent's week as a whole: when they sent it to their coach, and when the coach went over it (playbook: every Monday morning) |
| `nbcm_assistance` | A government assistance application (PAP, Rx playbook) for a doctor's patient on a GetMeds product: DSWD-AICS, PCSO-IMAP, the Office of the  |
| `nbcm_saved_views` | A list as someone left it, kept by name (benchmark E2, after Twenty's views): its filters, search and sort, as the list's own address keeps  |

### Reports

- **Activities:** Activities by person, Overdue activities
- **Customers:** Customers by type, Customers without recent activity, New customers
- **Field sales:** Coverage by tier, Patient assistance, Products presented, Visits by agent
- **Management:** Customer lifetime value, Pipeline coverage
- **Performance:** Sales against target, Scorecard results, Top customers (A/B/C), Top products
- **Retention:** Customers at risk, Retention by department, Retention trend
- **Sales:** Deals won and lost, Lost deals by reason, Pipeline by stage, Quotes by person

### Permissions

| Area | Group | Actions |
|---|---|---|
| Dashboard (`dashboard`) | CRM | view |
| Customers & contacts (`customers`) | CRM | view, create, edit, delete |
| Deals (`deals`) | CRM | view, create, edit, delete |
| Activities (calls, meetings, emails, notes, tasks) (`activities`) | CRM | view, create, edit, delete |
| Products & services (`products`) | Catalogue & paperwork | prices, approve |
| Quotes (`quotes`) | Catalogue & paperwork | approve |
| Sales orders (`orders`) | Catalogue & paperwork | approve, credit |
| Visits & collections (`visits`) | Field work | view, create, edit, delete |
| Targets and balances (`goals`) | Field work | view, manage, import |
| Reports (`reports`) | Insight & tools | view, export |
| Department settings (`department`) | Administration | manage |
| Administration (`admin`) | Administration | users, roles, teams, types, settings, audit |

### Links to other apps

- **Calls:** inventory, finance, pharmacy
- **Offers to other apps:** `GET /admin/connections`, `GET /integration/customers`, `GET /integration/customers/{customer_id}`, `GET /integration/prices`, `POST /integration/prices/decide`, `POST /integration/prices/quotes/{quote_id}/decide`

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `BACKUP_FROM`, `FILES_DIR`, `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`, `S3_BROWSER_ORIGINS`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `FIRST_ADMIN_COMPANY`, `SESSION_HOURS`, `PLATFORM_PUBLIC_KEY`, `PLATFORM_API_URL`, `PLATFORM_APP_KEY`, `DEFAULT_COMPANY`, `COMPANY`, `TERMS`, `DEV_COMPANIES`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ORG_LETTERHEAD`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`, `EMAIL_ENABLED`, `EMAIL_MODE`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_STARTTLS`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CRM_APP_URL`, `INVENTORY_API_URL`, `INVENTORY_API_KEY`, `INVENTORY_APP_URL`, `FINANCE_API_URL`, `FINANCE_API_KEY`, `ORDERS_API_URL`, `ORDERS_API_KEY`, `PHARMACY_API_URL`, `PHARMACY_API_KEY`, `INTEGRATION_KEYS`

### API endpoints

<details><summary>264 endpoints in 39 files</summary>

- **activities:** `GET /activities`, `GET /activities/summary`, `GET /activities/daily`, `POST /activities`, `PATCH /activities/{activity_id}`, `DELETE /activities/{activity_id}`, `GET /activities/{activity_id}/proof`
- **admin:** `GET /admin/users`, `GET /admin/users/options`, `POST /admin/users`, `GET /admin/users/{user_id}`, `PATCH /admin/users/{user_id}`, `POST /admin/users/{user_id}/password`, `GET /admin/roles`, `GET /admin/permissions`, `POST /admin/roles`, `PATCH /admin/roles/{role_id}`, `DELETE /admin/roles/{role_id}`, `GET /admin/teams`, `GET /admin/teams/managers`, `POST /admin/teams`, `PATCH /admin/teams/{team_id}`, `DELETE /admin/teams/{team_id}`, `GET /admin/audit`
- **assistance:** `GET /assistance`, `POST /assistance`, `PATCH /assistance/{application_id}`, `DELETE /assistance/{application_id}`, `POST /assistance/{application_id}/files`, `GET /assistance/{application_id}/files/{n}`, `DELETE /assistance/{application_id}/files/{n}`
- **associations:** `GET /associations`, `POST /associations`, `DELETE /associations/{association_id}`, `GET /associations/targets`, `GET /admin/association-labels`, `POST /admin/association-labels`, `PATCH /admin/association-labels/{code}`
- **attention:** `GET /attention`, `POST /attention/put-aside`, `GET /admin/attention-rules`, `PUT /admin/attention-rules`, `DELETE /admin/attention-rules/{team_id}`
- **auth:** `POST /auth/login`, `POST /auth/platform`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/account`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/leave`, `GET /auth/company`, `GET /auth/view-as`, `POST /auth/view-as`
- **bulk:** `GET /jobs/{job_id}`, `POST /companies/bulk`, `POST /contacts/bulk`, `POST /activities/bulk`
- **catalogue:** `GET /pricing`, `POST /pricing/price-types`, `PATCH /pricing/price-types/{code}`, `POST /pricing/issuers`, `PATCH /pricing/issuers/{code}`, `PATCH /pricing/settings`, `GET /products`, `POST /products/sync`, `GET /stock`, `POST /products`, `GET /products/{product_id}`, `PATCH /products/{product_id}`, `PUT /products/{product_id}/prices`, `DELETE /products/{product_id}`, `GET /promos`, `POST /promos`, `PUT /promos/{promo_id}`, `DELETE /promos/{promo_id}`, `GET /bundles`, `POST /bundles`, `PUT /bundles/{bundle_id}`, `DELETE /bundles/{bundle_id}`
- **companies:** `GET /companies`, `GET /companies/link-options`, `GET /companies/lookalikes`, `POST /companies`, `GET /companies/{company_id}`, `GET /companies/{company_id}/trade`, `PATCH /companies/{company_id}`, `GET /companies/{company_id}/transfer`, `POST /companies/{company_id}/transfer`, `DELETE /companies/{company_id}`
- **connections:** `GET /admin/connections`
- **contacts:** `GET /contacts`, `POST /contacts`, `GET /contacts/{contact_id}`, `PATCH /contacts/{contact_id}`, `DELETE /contacts/{contact_id}`
- **customer_types:** `GET /customer-types`, `POST /admin/customer-types`, `PATCH /admin/customer-types/{code}`, `DELETE /admin/customer-types/{code}`
- **deals:** `GET /deal-stages`, `GET /deal-lists`, `POST /admin/deal-stages`, `PATCH /admin/deal-stages/{code}`, `DELETE /admin/deal-stages/{code}`, `PUT /admin/deal-lists`, `GET /deals/likely`, `GET /deals`, `GET /deals-summary`, `GET /deals/{deal_id}`, `POST /deals`, `PATCH /deals/{deal_id}`, `POST /deals/{deal_id}/win`, `POST /deals/{deal_id}/lose`, `POST /deals/{deal_id}/reopen`, `DELETE /deals/{deal_id}`, `GET /deals-board`, `GET /deals-forecast`
- **duplicates:** `GET /duplicates`, `POST /duplicates/merge`, `POST /duplicates/different`, `GET /merged/{record_id}`
- **exports:** `GET /exports/customers`, `GET /exports/products`
- **field:** `GET /visits`, `POST /visits`, `PATCH /visits/{visit_id}`, `GET /field/visit-brief`, `GET /field/detailing`, `DELETE /visits/{visit_id}`, `GET /field/doctors`, `PUT /field/doctors/{company_id}/plan`, `GET /field/coverage`, `GET /field/doctors/{company_id}`, `PUT /field/doctors/{company_id}/location`, `DELETE /field/doctors/{company_id}/location`, `GET /field/performance`, `GET /field/goals`, `PUT /field/goals`, `POST /field/trail`, `GET /field/routes`, `GET /field/routes/days`
- **field_plan:** `GET /field/plan`, `POST /field/plan/stops`, `DELETE /field/plan/stops/{stop_id}`, `POST /field/plan/fill`, `POST /field/plan/send`, `POST /field/plan/review`
- **imports:** `POST /imports/{kind}/read`, `POST /imports/{kind}`
- **insights:** `GET /insights/people`
- **integration:** `GET /integration/customers`, `GET /integration/customers/{customer_id}`
- **integration_prices:** `GET /integration/prices`, `POST /integration/prices/decide`, `POST /integration/prices/quotes/{quote_id}/decide`
- **kpis:** `GET /kpis`, `POST /admin/kpis`, `PATCH /admin/kpis/{kpi_id}`, `DELETE /admin/kpis/{kpi_id}`, `PUT /admin/kpis/order`, `GET /kpi-targets`, `PUT /kpi-targets`, `PUT /kpi-entries`, `GET /kpi-scorecard`, `GET /scorecards`
- **materials:** `GET /material-requests`, `POST /material-requests/{request_id}/decision`
- **media:** `GET /media`, `GET /media/{item_id}/link`, `GET /media/{item_id}/file`, `POST /admin/media`, `PATCH /admin/media/{item_id}`, `PUT /admin/media/{item_id}/file`, `DELETE /admin/media/{item_id}`
- **people:** `GET /people/assignable`
- **price_rules:** `GET /pricing/rules`, `PUT /pricing/procedure`, `POST /pricing/groups`, `PATCH /pricing/groups/{code}`, `DELETE /pricing/groups/{code}`, `POST /pricing/conditions`, `PUT /pricing/conditions/{condition_id}`, `DELETE /pricing/conditions/{condition_id}`
- **prices:** `GET /prices/teams`, `GET /prices/pending-approvals`, `POST /prices/approvals/decide`, `GET /prices`, `PUT /prices/types`, `PUT /prices`
- **profile:** `GET /auth/profile`, `PUT /auth/profile`, `POST /auth/password`
- **quote_links:** `GET /companies/{company_id}/quote-links`, `GET /quote-links`, `POST /companies/{company_id}/quote-links`, `POST /quote-links`, `GET /quote-links/{link_id}/token`, `PATCH /quote-links/{link_id}`, `DELETE /quote-links/{link_id}`, `GET /public/quote-links/{token}`, `POST /public/quote-links/{token}/uploads`, `POST /public/quote-links/{token}`, `GET /public/quote-links/{token}/quotation`, `POST /public/quote-links/{token}/place`
- **quote_templates:** `GET /admin/quote-templates`, `GET /admin/quote-templates/{template_id}`, `POST /admin/quote-templates`, `PATCH /admin/quote-templates/{template_id}`, `DELETE /admin/quote-templates/{template_id}`, `POST /admin/quote-templates/{template_id}/images/{which}`, `DELETE /admin/quote-templates/{template_id}/images/{which}`, `POST /admin/quote-templates/{template_id}/excel`, `GET /admin/quote-templates/{template_id}/excel`, `GET /quote-templates/{template_id}/images/{which}`, `GET /quotes/{quote_id}/templates`, `GET /quotes/{quote_id}/document`, `GET /admin/quote-template-fields`, `POST /admin/quote-templates/{template_id}/preview`, `GET /quotes/{quote_id}/document.xlsx`
- **quotes:** `GET /{kind}/{record_id}/price-list`, `POST /{kind}/{record_id}/quotes/preview`, `POST /{kind}/{record_id}/quotes`, `GET /quotes`, `GET /quotes/{quote_id}`, `POST /quotes/{quote_id}/pharmacy-check`, `GET /quotes/{quote_id}/letter`, `GET /quotes/{quote_id}/prescriptions/{n}`, `GET /quotes/{quote_id}/documents/{n}`, `GET /quotes/{quote_id}/order-payload`, `POST /quotes/{quote_id}/order`, `GET /quote-letterhead`, `DELETE /quotes/{quote_id}`, `POST /quotes/{quote_id}/credit`, `POST /quotes/{quote_id}/approval`, `POST /quotes/{quote_id}/letter-check`, `POST /quotes/{quote_id}/payments`
- **reports:** `GET /reports`, `GET /reports/{key}`
- **retention:** `GET /retention`, `GET /retention/export`, `GET /retention/windows`, `PUT /retention/windows/{team_id}`
- **sales:** `GET /sales/targets`, `PUT /sales/targets`, `GET /sales/results`, `GET /sales/results/export`, `GET /sales/trend`
- **search:** `GET /search`
- **settings:** `GET /forms/{entity}`, `GET /team-names`, `POST /admin/forms/{entity}/fields/{key}/options`, `PUT /admin/forms/{entity}`, `GET /admin/company-settings`, `PATCH /admin/company-settings`, `GET /admin/terms`, `PUT /admin/terms`
- **sharing:** `GET /customer-sharing`, `PUT /customer-sharing/{team_id}`
- **unset:** `GET /unset`
- **views:** `GET /views`, `POST /views`, `PATCH /views/{view_id}`, `DELETE /views/{view_id}`

</details>

## Inventory

Code in `backend/modules/inventory`, its API under `/inventory` in the one backend, screens at `/inventory` in the one app.

### Screens (the sidebar)

- **Home:** Home (`/inventory`)
- **Items:** Items (`/inventory/products`), Item registrations (CPR) (`/inventory/products/cpr`)
- **Inventory:** Stock on hand (`/inventory/stock`), Scan (`/inventory/scan`), Transfer orders (`/inventory/transfers`), Inventory adjustments (`/inventory/adjustments`), Inventory counts (`/inventory/counts`)
- **Sales:** Deliveries (`/inventory/orders`), Reservations (`/inventory/reservations`)
- **Purchases:** Vendors (`/inventory/suppliers`), Replenishment (`/inventory/replenishment`), Consignment (`/inventory/consignment`), Purchase orders (`/inventory/purchase-orders`), Purchase receives (`/inventory/receipts`), Quality checks (`/inventory/quality-checks`)
- **Reports:** Reports (`/inventory/reports`)
- **Settings:** Warehouses (`/inventory/warehouses`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbin_roles` | Role |
| `nbin_role_permissions` | RolePermission |
| `nbin_users` | User |
| `nbin_platform_passes` | A pass from the platform already taken: each one works once |
| `nbin_sessions` | One sign-in |
| `nbin_audit_log` | The activity log: who changed what, and when |
| `nbin_sequences` | The next number of each kind of document, per year: PO-2026-00421 |
| `nbin_operation_types` | A kind of stock operation, as the company names it ("Receipts", "Returns from customers"), optionally for one warehouse |
| `nbin_couriers` | A delivery company we hand parcels to (step 12): LBC, J&T and Lalamove for every company; it adds its own |
| `nbin_categories` | Medical Supplies → Syringes |
| `nbin_brands` | Brand |
| `nbin_units` | A unit of measure: pc, box, bottle |
| `nbin_products` | Product |
| `nbin_product_images` | A product's pictures, kept in the database like everything else here |
| `nbin_suppliers` | Supplier |
| `nbin_supplier_products` | What a supplier charges for a product, and their own code for it |
| `nbin_warehouses` | Warehouse |
| `nbin_locations` | A place within a warehouse: a zone, rack or bin |
| `nbin_batches` | A lot of one product: PCM-260821, made 21 Aug 2026, expires 21 Aug 2028 |
| `nbin_stock` | One balance: a product, in a location, of a batch (or none) |
| `nbin_serials` | One serial-numbered unit, and where it is now |
| `nbin_movements` | One change to one balance |
| `nbin_purchase_orders` | PurchaseOrder |
| `nbin_purchase_order_lines` | PurchaseOrderLine |
| `nbin_receipts` | One delivery taken in: against a purchase order, or on its own |
| `nbin_receipt_lines` | ReceiptLine |
| `nbin_sales_orders` | A customer's order (app/sales.py): made from an approved CRM quote, or typed in the Sales app at the price list's prices; waits for approval |
| `nbin_sales_order_lines` | SalesOrderLine |
| `nbin_orders` | Stock going out: a customer order, or an issue to a department or project |
| `nbin_order_lines` | OrderLine |
| `nbin_replenishment_settings` | How refill is worked out (one row): safety days on every lead time, the lead time when the vendor gives none, the days of use the daily aver |
| `nbin_consignment_settlements` | What sold from a vendor's consignment between two moments, priced at its price, sent to Finance as a bill (15d) |
| `nbin_product_documents` | A file kept with an item (certificate of analysis, leaflet, CPR) and whether it goes with every sale (15e) |
| `nbin_product_packagings` | A pack of an item (Box, Strip, Case) and how many of its base unit it holds; stock stays in the base unit |
| `nbin_packages` | One of a delivery's boxes: numbered, with what is in it and its weight |
| `nbin_package_lines` | PackageLine |
| `nbin_quality_checks` | What a receipt into a checking warehouse holds until someone checks it: passed is released for use, failed is put aside as damaged, with why |
| `nbin_quality_check_lines` | QualityCheckLine |
| `nbin_transfers` | Transfer |
| `nbin_transfer_lines` | TransferLine |
| `nbin_adjustments` | A correction to stock, with its reason |
| `nbin_adjustment_lines` | AdjustmentLine |
| `nbin_counts` | A physical count of a warehouse |
| `nbin_count_schedules` | A cycle count that comes round every so many days (step 14b): one warehouse, and one category when set |
| `nbin_count_lines` | CountLine |

### Reports

- **Activity:** Fast-moving products, Product movement, Stock movement *(fixed)*
- **Attention:** Dead stock, Expiring products *(fixed)*, Low stock, Out of stock, Product registrations (CPR) *(fixed)*
- **Control:** Count accuracy, Inventory adjustments *(fixed)*, Inventory variance
- **Orders:** Sales and issuance history
- **Purchasing:** Consignment, Purchase history, Purchases by item, Purchases by vendor, Quality checks by vendor, Supplier performance
- **Sales:** Sales by customer, Sales by item, Sales by salesperson
- **Sales orders:** Fill rate, Order to cash, Sales orders by division, Sales orders by salesperson, Sales orders by status
- **Shipping:** Deliveries by courier, On-time delivery
- **Stock:** Batch details, Committed stock, Current inventory, Inventory summary, Inventory valuation *(fixed)*, Stock aging, Warehouse inventory

### Permissions

| Area | Group | Actions |
|---|---|---|
| Dashboard & alerts (`dashboard`) | Inventory | view |
| Products, categories, brands & units (`products`) | Catalog | view, create, edit, delete |
| Stock levels, movements, batches & serials (`stock`) | Inventory | view |
| Warehouses & locations (`warehouses`) | Inventory | view, manage |
| Stock transfers (`transfers`) | Inventory | view, create, approve, dispatch, receive |
| Stock adjustments (`adjustments`) | Inventory | view, create, approve |
| Inventory counts (`counts`) | Inventory | view, create, approve |
| Suppliers & supplier prices (`suppliers`) | Purchasing | view, create, edit, delete |
| Purchase orders (`purchasing`) | Purchasing | view, create, edit, approve |
| Receiving (`receiving`) | Purchasing | view, receive |
| Sales orders (`sales`) | Sales | view, create, edit, approve |
| Deliveries, reservations & issuance (`orders`) | Orders | view, create, edit, approve, issue |
| Reports (`reports`) | Insight | view, export |
| Administration (`admin`) | Administration | users, roles, audit |

### Links to other apps

- **Calls:** none
- **Offers to other apps:** `GET /integration/products`, `GET /integration/costs`, `GET /integration/stock`, `GET /integration/suppliers`, `GET /integration/suppliers/{supplier_id}`, `GET /integration/suppliers/{supplier_id}/receipts`

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `BACKUP_FROM`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `FIRST_ADMIN_COMPANY`, `SESSION_HOURS`, `PLATFORM_PUBLIC_KEY`, `PLATFORM_API_URL`, `PLATFORM_APP_KEY`, `DEFAULT_COMPANY`, `DEV_COMPANIES`, `COMPANY`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `EXPIRY_WARNING_DAYS`, `DEAD_STOCK_DAYS`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`, `INTEGRATION_KEYS`

### API endpoints

<details><summary>181 endpoints in 22 files</summary>

- **adjustments:** `GET /inventory/adjustments/reasons`, `GET /inventory/adjustments`, `POST /inventory/adjustments`, `GET /inventory/adjustments/{adjustment_id}`, `POST /inventory/adjustments/{adjustment_id}/approve`, `POST /inventory/adjustments/{adjustment_id}/reject`, `GET /inventory/counts`, `POST /inventory/counts`, `GET /inventory/counts/{count_id}`, `PUT /inventory/counts/{count_id}/lines`, `POST /inventory/counts/{count_id}/lines`, `POST /inventory/counts/{count_id}/submit`, `POST /inventory/counts/{count_id}/reopen`, `POST /inventory/counts/{count_id}/approve`, `POST /inventory/counts/{count_id}/cancel`, `DELETE /inventory/adjustments/{adjustment_id}`
- **admin:** `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{user_id}`, `POST /admin/users/{user_id}/password`, `GET /admin/roles`, `POST /admin/roles`, `PATCH /admin/roles/{role_id}`, `DELETE /admin/roles/{role_id}`, `GET /admin/audit`
- **auth:** `POST /auth/login`, `POST /auth/platform`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/leave`, `GET /auth/company`, `GET /auth/view-as`, `POST /auth/view-as`
- **catalog:** `GET /inventory/reference`, `GET /inventory/categories`, `POST /inventory/categories`, `PATCH /inventory/categories/{category_id}`, `DELETE /inventory/categories/{category_id}`, `GET /inventory/brands`, `POST /inventory/brands`, `PATCH /inventory/brands/{brand_id}`, `DELETE /inventory/brands/{brand_id}`, `GET /inventory/units`, `POST /inventory/units`, `PATCH /inventory/units/{code}`, `DELETE /inventory/units/{code}`, `GET /inventory/products`, `POST /inventory/products`, `GET /inventory/products/{product_id}`, `PATCH /inventory/products/{product_id}`, `DELETE /inventory/products/{product_id}`, `POST /inventory/products/cpr`, `GET /inventory/products/cpr/summary`, `POST /inventory/products/{product_id}/images`, `GET /inventory/products/{product_id}/images/{image_id}`, `DELETE /inventory/products/{product_id}/images/{image_id}`, `PUT /inventory/products/{product_id}/suppliers/{supplier_id}`, `DELETE /inventory/products/{product_id}/suppliers/{supplier_id}`
- **count_schedules:** `GET /inventory/count-schedules`, `POST /inventory/count-schedules`, `PATCH /inventory/count-schedules/{schedule_id}`, `DELETE /inventory/count-schedules/{schedule_id}`, `POST /inventory/count-schedules/{schedule_id}/start`
- **insight:** `GET /inventory/alerts`, `GET /inventory/dashboard`, `GET /inventory/reports`, `GET /inventory/reports/{key}`, `GET /inventory/reports/{key}/csv`
- **integration:** `GET /integration/products`, `GET /integration/costs`, `GET /integration/stock`, `GET /integration/suppliers`, `GET /integration/suppliers/{supplier_id}`, `GET /integration/suppliers/{supplier_id}/receipts`
- **orders:** `GET /inventory/orders`, `GET /inventory/order-figures`, `GET /inventory/reservations`, `POST /inventory/orders`, `GET /inventory/orders/{order_id}`, `PUT /inventory/orders/{order_id}`, `DELETE /inventory/orders/{order_id}`, `POST /inventory/orders/{order_id}/confirm`, `POST /inventory/orders/{order_id}/pick`, `POST /inventory/orders/{order_id}/issue`, `POST /inventory/orders/{order_id}/received`, `POST /inventory/orders/{order_id}/cancel`
- **packagings:** `GET /inventory/products/{product_id}/packagings`, `POST /inventory/products/{product_id}/packagings`, `PATCH /inventory/products/{product_id}/packagings/{packaging_id}`, `DELETE /inventory/products/{product_id}/packagings/{packaging_id}`
- **packing:** `GET /inventory/orders/{order_id}/packages`, `POST /inventory/orders/{order_id}/packages`, `DELETE /inventory/orders/{order_id}/packages/{package_id}`
- **product_documents:** `GET /inventory/products/{product_id}/documents`, `POST /inventory/products/{product_id}/documents`, `GET /inventory/products/{product_id}/documents/{document_id}`, `PATCH /inventory/products/{product_id}/documents/{document_id}`, `DELETE /inventory/products/{product_id}/documents/{document_id}`, `GET /inventory/orders/{order_id}/documents`, `GET /inventory/sales-orders/{order_id}/documents`, `POST /inventory/orders/{order_id}/documents/send`, `POST /inventory/sales-orders/{order_id}/documents/send`
- **profile:** `GET /auth/profile`, `PUT /auth/profile`, `POST /auth/password`, `GET /auth/activity`
- **purchasing:** `GET /inventory/suppliers`, `POST /inventory/suppliers`, `GET /inventory/suppliers/{supplier_id}`, `PATCH /inventory/suppliers/{supplier_id}`, `DELETE /inventory/suppliers/{supplier_id}`, `GET /inventory/purchase-orders`, `GET /inventory/purchase-order-figures`, `POST /inventory/purchase-orders`, `GET /inventory/purchase-orders/{po_id}`, `PUT /inventory/purchase-orders/{po_id}`, `PATCH /inventory/purchase-orders/{po_id}`, `POST /inventory/purchase-orders/{po_id}/place`, `POST /inventory/purchase-orders/{po_id}/cancel`, `DELETE /inventory/purchase-orders/{po_id}`, `GET /inventory/backorders`, `GET /inventory/receipts`, `GET /inventory/receipts/{receipt_id}`, `POST /inventory/receipts`
- **quality:** `GET /inventory/quality-checks`, `GET /inventory/quality-checks/{check_id}`, `POST /inventory/quality-checks/{check_id}/done`
- **replenishment:** `GET /inventory/replenishment`, `POST /inventory/replenishment/drafts`, `PUT /inventory/replenishment/settings`, `GET /inventory/consignment`, `POST /inventory/consignment/{supplier_id}/settle`
- **sales:** `GET /inventory/sales-orders`, `GET /inventory/sales-orders/{order_id}`, `POST /inventory/sales-orders`, `PUT /inventory/sales-orders/{order_id}`, `POST /inventory/sales-orders/{order_id}/submit`, `POST /inventory/sales-orders/{order_id}/approve`, `POST /inventory/sales-orders/{order_id}/reject`, `POST /inventory/sales-orders/{order_id}/cancel`
- **scan:** `GET /inventory/scan`, `POST /inventory/counts/{count_id}/scan`
- **shipping:** `GET /inventory/couriers`, `POST /inventory/couriers`, `PATCH /inventory/couriers/{courier_id}`, `PUT /inventory/orders/{order_id}/shipping`, `POST /inventory/orders/{order_id}/delivered`, `POST /inventory/orders/{order_id}/failed`, `POST /inventory/orders/{order_id}/send-again`, `GET /inventory/orders/{order_id}/delivery-photo`
- **stock:** `GET /inventory/stock`, `GET /inventory/movements`, `GET /inventory/batches`, `GET /inventory/serials`
- **transfers:** `GET /inventory/transfers`, `GET /inventory/transfers/map`, `POST /inventory/transfers`, `GET /inventory/transfers/{transfer_id}`, `PUT /inventory/transfers/{transfer_id}`, `DELETE /inventory/transfers/{transfer_id}`, `POST /inventory/transfers/{transfer_id}/request`, `POST /inventory/transfers/{transfer_id}/approve`, `POST /inventory/transfers/{transfer_id}/dispatch`, `POST /inventory/transfers/{transfer_id}/receive`, `POST /inventory/transfers/{transfer_id}/cancel`
- **unset:** `GET /inventory/unset`, `GET /inventory/setup`
- **warehouses:** `GET /inventory/warehouses`, `POST /inventory/warehouses`, `GET /inventory/warehouses/{warehouse_id}`, `PATCH /inventory/warehouses/{warehouse_id}`, `POST /inventory/warehouses/{warehouse_id}/locate`, `DELETE /inventory/warehouses/{warehouse_id}`, `POST /inventory/warehouses/{warehouse_id}/locations`, `PATCH /inventory/warehouses/{warehouse_id}/locations/{location_id}`, `DELETE /inventory/warehouses/{warehouse_id}/locations/{location_id}`, `GET /inventory/operation-types`, `POST /inventory/operation-types`, `PATCH /inventory/operation-types/{type_id}`

</details>

## Finance (Books)

Code in `backend/modules/finance`, its API under `/finance` in the one backend, screens at `/finance` in the one app.

### Screens (the sidebar)

- **Home:** Home (`/finance`)
- **Payables:** Bills (`/finance/bills`), Supplier aging (`/finance/bills/aging`), Payment vouchers (`/finance/vouchers`), Suppliers (`/finance/suppliers`)
- **Petty cash:** Petty cash (`/finance/petty-cash`), Imported expenses (`/finance/petty-cash/imported`)
- **Sales:** Sales orders (`/finance/sales-orders`), Finance invoices (`/finance/invoices`), Receivables (`/finance/invoices/receivables`)
- **Approvals:** Price approvals (`/finance/prices`)
- **Banking:** Bank accounts (`/finance/bank/accounts`), Bank reconciliation (`/finance/bank`)
- **Accountant:** Journal entries (`/finance/ledger`), Chart of accounts (`/finance/ledger/accounts`), Trial balance (`/finance/ledger/trial-balance`), Closing and equity (`/finance/ledger/closing`), Fixed assets (`/finance/ledger/fixed-assets`), Budgets (`/finance/ledger/budgets`)
- **Taxes:** VAT return (`/finance/bir/vat`), Withholding tax (`/finance/bir/withholding`), Summary lists (`/finance/bir/lists`), BIR files (DAT) (`/finance/bir/sales-dat`), BIR readiness (`/finance/bir/readiness`)
- **Calendar:** Calendar (`/finance/calendar`)
- **Reports:** Reports (`/finance/reports`)
- **Settings:** Import review (`/finance/import-review`), Import matching (`/finance/import-matching`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbfi_sales_orders` | SalesOrder |
| `nbfi_zoho_deliveries` | ZohoDelivery |
| `nbfi_petty_cash_events` | ZohoLink |
| `nbfi_zoho_connections` |  |
| `nbfi_zoho_runtime` |  |
| `nbfi_zoho_source_documents` |  |
| `nbfi_zoho_source_runs` |  |
| `nbfi_roles` |  |
| `nbfi_role_permissions` |  |
| `nbfi_users` |  |
| `nbfi_audit_log` |  |
| `nbfi_platform_passes` |  |
| `nbfi_sessions` |  |
| `nbfi_tax_profile` |  |
| `nbfi_tax_rates` |  |
| `nbfi_expense_categories` |  |
| `nbfi_accounts` |  |
| `nbfi_ledger_settings` |  |
| `nbfi_bank_accounts` |  |
| `nbfi_year_closings` |  |
| `nbfi_fixed_assets` |  |
| `nbfi_budgets` |  |
| `nbfi_journal_entries` |  |
| `nbfi_journal_lines` |  |
| `nbfi_fund_requests` |  |
| `nbfi_fund_expenses` |  |
| `nbfi_fund_events` |  |
| `nbfi_stored_files` |  |
| `nbfi_invoice_series` |  |
| `nbfi_invoices` |  |
| `nbfi_invoice_payments` |  |
| `nbfi_notifications` |  |
| `nbfi_calendar_events` |  |
| `nbfi_calendar_shares` |  |
| `nbfi_calendar_done` |  |
| `nbfi_signatures` |  |
| `nbfi_signed_steps` |  |
| `nbfi_suppliers` |  |
| `nbfi_supplier_files` |  |
| `nbfi_bills` |  |
| `nbfi_bill_events` |  |
| `nbfi_bill_files` |  |
| `nbfi_payment_vouchers` |  |
| `nbfi_voucher_lines` |  |
| `nbfi_voucher_events` |  |
| `nbfi_voucher_files` |  |
| `nbfi_bank_reconciliations` |  |
| `nbfi_import_matches` |  |
| `nbfi_import_rules` |  |
| `nbfi_import_runs` |  |
| `nbfi_import_records` |  |
| `nbfi_import_links` |  |
| `nbfi_imported_expenses` |  |
| `nbfi_imported_expense_lines` |  |
| `nbfi_petty_cash_vouchers` |  |
| `nbfi_petty_cash_lines` |  |

### Reports

- **Accounting:** Balance sheet *(fixed)*, Cash flow statement *(fixed)*, Fixed asset register *(fixed)*, General ledger *(fixed)*, Journal entries by source, Profit and loss *(fixed)*, Trial balance *(fixed)*
- **Expenses:** Expenses by category, Marketing requests by status, Outstanding advances
- **Management:** Budget against actual *(fixed)*, Cash forecast *(fixed)*, Gross margin by customer *(fixed)*, Gross margin by product *(fixed)*, Gross margin by salesperson *(fixed)*, Key figures *(fixed)*, Revenue and margin by division *(fixed)*, Revenue and margin by team *(fixed)*, Revenue growth *(fixed)*
- **Purchases:** Bills by supplier, Payables ageing, Payment vouchers released
- **Sales:** Collections, Receivables ageing, Sales by customer, Sales by salesperson, Sales register

### Permissions

| Area | Group | Actions |
|---|---|---|
| Finance connections (`integrations`) | Administration | manage |
| Imports from Zoho exports (`imports`) | Administration | propose, confirm, confirm_tax, run |
| Sales orders (`sales_orders`) | Sales | view, create, submit, approve, cancel |
| Overview (`dashboard`) | Finance | view |
| Marketing requests (`funds`) | Marketing requests | view, release, check, settle, cancel |
| Expense categories (`categories`) | Marketing requests | view, manage |
| Sales invoices and payments (`invoices`) | Invoices | view, create, issue, collect, void, setup |
| Suppliers (`suppliers`) | Payables | view, add, edit, deactivate |
| Supplier bills (`bills`) | Payables | view, create, approve, first, check, void |
| Payment vouchers (`vouchers`) | Payables | view, prepare, release, void |
| Petty cash (`petty_cash`) | Petty cash | view, create, check, void |
| Journal entries and reports (`journal`) | Accounting | view, post, reverse, approve, first |
| Chart of accounts and default accounts (`accounts`) | Accounting | view, manage |
| Tax setup (`tax`) | Tax | view, manage |
| Product prices (`prices`) | Prices | view, approve |
| BIR files and reports (`bir`) | Tax | view, prepare |
| Bank reconciliation (`bank`) | Accounting | view, reconcile |
| Administration (`admin`) | Administration | users, roles, audit |

### Links to other apps

- **Calls:** crm, inventory
- **Offers to other apps:** `GET /integration/tax/setup`, `POST /integration/tax/compute`

### Settings (names only)

`ENVIRONMENT`, `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_ENCRYPTION_KEY`, `ZOHO_REGION`, `ZOHO_REDIRECT_URI`, `ZOHO_DATABASE_ENABLED`, `ZOHO_CONNECTION_ID`, `ZOHO_ENVIRONMENT`, `ZOHO_WORKER_ENABLED`, `ZOHO_DAILY_LIMIT`, `POSTGRES_DRIVER`, `DATA_ENVIRONMENT`, `ZOHO_OUTBOX_CAPTURE_ENABLED`, `ZOHO_OUTBOUND_ENABLED`, `ZOHO_NETWORK_ENABLED`, `DATABASE_URL`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `SESSION_HOURS`, `PLATFORM_PUBLIC_KEY`, `PLATFORM_API_URL`, `PLATFORM_APP_KEY`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`, `INTEGRATION_KEYS`, `LIQUIDATE_WITHIN_DAYS`, `CRM_API_URL`, `CRM_API_KEY`, `CRM_COMPANY`, `INVENTORY_API_URL`, `INVENTORY_API_KEY`

### API endpoints

<details><summary>211 endpoints in 25 files</summary>

- **admin:** `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{user_id}`, `DELETE /admin/users/{user_id}/signature`, `POST /admin/users/{user_id}/password`, `GET /admin/roles`, `POST /admin/roles`, `PATCH /admin/roles/{role_id}`, `DELETE /admin/roles/{role_id}`, `GET /admin/audit`
- **assets:** `GET /finance/fixed-assets`, `POST /finance/fixed-assets`, `POST /finance/fixed-assets/depreciate`, `POST /finance/fixed-assets/{asset_id}/dispose`, `GET /finance/budgets`, `PUT /finance/budgets`, `DELETE /finance/budgets/{budget_id}`
- **auth:** `POST /auth/login`, `POST /auth/platform`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/account`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/leave`, `GET /auth/view-as`, `POST /auth/view-as`
- **bank:** `GET /finance/bank/accounts`, `POST /finance/bank/reconciliations`, `GET /finance/bank/reconciliations/{rec_id}`, `PUT /finance/bank/reconciliations/{rec_id}/cleared`, `POST /finance/bank/reconciliations/{rec_id}/finish`, `DELETE /finance/bank/reconciliations/{rec_id}`
- **banking:** `GET /finance/bank-accounts`, `POST /finance/bank-accounts`, `PATCH /finance/bank-accounts/{bank_id}`, `POST /finance/equity/entries`, `GET /finance/equity/statement`, `GET /finance/closing`, `POST /finance/closing`, `PUT /finance/period-lock`
- **bir:** `GET /finance/bir/books/{book}`, `GET /finance/bir/statements/income`, `GET /finance/bir/statements/balance`, `GET /finance/bir/returns/vat`, `GET /finance/bir/lists/{which}`, `GET /finance/bir/withholding/0619e`, `GET /finance/bir/withholding/1601eq`, `GET /finance/bir/withholding/1604e`, `GET /finance/bir/withholding/2307`, `GET /finance/bir/readiness`, `GET /finance/bir/returns/vat/draft`, `GET /finance/bir/returns/vat/draft.pdf`, `GET /finance/bir/withholding/2307/draft.pdf`, `GET /finance/bir/withholding/{form}/draft.pdf`, `GET /finance/bir/filing-guidance`
- **calendar:** `GET /calendar`, `POST /calendar/events`, `PUT /calendar/events/{event_id}`, `DELETE /calendar/events/{event_id}`, `POST /calendar/events/{event_id}/done`, `DELETE /calendar/events/{event_id}/done`
- **exports:** `GET /finance/exports/journal.csv`, `GET /finance/exports/accounts/{account_id}/statement.csv`, `GET /finance/exports/trial-balance.csv`, `GET /finance/exports/funds.csv`
- **finance:** `GET /finance/dashboard`, `GET /finance/dashboard/payables`, `GET /finance/bir/sales-dat`, `GET /finance/dashboard/waiting-prices`, `GET /finance/notifications`, `POST /finance/notifications/read`, `GET /finance/signatures/{record_type}/{record_id}`
- **funds:** `GET /finance/funds/counts`, `GET /finance/funds`, `GET /finance/funds/categories`, `POST /finance/funds/categories`, `PUT /finance/funds/categories/{category_id}`, `GET /finance/funds/{request_id}`, `GET /finance/funds/{request_id}/expenses/{expense_id}/receipt`, `POST /finance/funds/{request_id}/release`, `POST /finance/funds/{request_id}/cancel`, `PATCH /finance/funds/{request_id}/expenses/{expense_id}`, `POST /finance/funds/{request_id}/send-back`, `POST /finance/funds/{request_id}/finish-check`, `POST /finance/funds/{request_id}/returned`, `POST /finance/funds/{request_id}/reimbursed`
- **imported_expenses:** `GET /imported-expenses`, `GET /imported-expenses/{expense_id}`, `POST /imported-expenses/{expense_id}/void`
- **imports:** `GET /finance/imports/matching`, `POST /finance/imports/matching/load`, `POST /finance/imports/matching/{match_id}/records`, `PUT /finance/imports/matching/{match_id}`, `POST /finance/imports/matching/{match_id}/confirm`, `GET /finance/imports/matching/{match_id}/rules`, `POST /finance/imports/matching/{match_id}/rules`, `POST /finance/imports/rules/{rule_id}/confirm`, `DELETE /finance/imports/rules/{rule_id}`, `POST /finance/imports/bills/preview`, `POST /finance/imports/bills`, `POST /finance/imports/supplier-payments/preview`, `POST /finance/imports/supplier-payments`, `POST /finance/imports/oojeema-sales/preview`, `POST /finance/imports/oojeema-sales`, `POST /finance/imports/expenses/preview`, `POST /finance/imports/expenses`
- **integration:** `GET /integration/tax/setup`, `POST /integration/tax/compute`
- **invoices:** `GET /finance/invoices/series`, `POST /finance/invoices/series`, `PATCH /finance/invoices/series/{series_id}`, `GET /finance/invoices/automatic`, `PUT /finance/invoices/automatic`, `GET /finance/invoices/customers`, `GET /finance/invoices`, `POST /finance/invoices`, `GET /finance/invoices/{invoice_id}`, `PUT /finance/invoices/{invoice_id}`, `DELETE /finance/invoices/{invoice_id}`, `POST /finance/invoices/{invoice_id}/issue`, `POST /finance/invoices/{invoice_id}/void`, `POST /finance/invoices/{invoice_id}/reissue`, `POST /finance/invoices/{invoice_id}/payments`, `DELETE /finance/invoices/{invoice_id}/payments/{payment_id}`
- **ledger:** `GET /finance/ledger/accounts`, `POST /finance/ledger/accounts`, `PUT /finance/ledger/accounts/{account_id}`, `POST /finance/ledger/accounts/import/check`, `POST /finance/ledger/accounts/import`, `GET /finance/ledger/posting`, `PUT /finance/ledger/posting`, `GET /finance/ledger/entries`, `GET /finance/ledger/entries/{entry_id}`, `POST /finance/ledger/entries`, `POST /finance/ledger/entries/{entry_id}/reverse`, `POST /finance/ledger/entries/approve`, `POST /finance/ledger/entries/{entry_id}/approve`, `POST /finance/ledger/entries/{entry_id}/reject`, `GET /finance/ledger/accounts/{account_id}`, `GET /finance/ledger/trial-balance`
- **payables:** `GET /suppliers`, `POST /suppliers`, `POST /suppliers/import/check`, `POST /suppliers/import`, `GET /suppliers/{supplier_id}`, `PUT /suppliers/{supplier_id}`, `POST /suppliers/{supplier_id}/active`, `POST /suppliers/{supplier_id}/files`, `GET /suppliers/{supplier_id}/files/{file_id}`, `DELETE /suppliers/{supplier_id}/files/{file_id}`, `GET /bills/choices`, `GET /bills`, `POST /bills`, `GET /bills/{bill_id}`, `PUT /bills/{bill_id}`, `DELETE /bills/{bill_id}`, `POST /bills/{bill_id}/submit`, `POST /bills/{bill_id}/approve`, `POST /bills/{bill_id}/check`, `POST /bills/{bill_id}/return`, `POST /bills/{bill_id}/void`, `POST /bills/{bill_id}/files`, `GET /bills/{bill_id}/files/{file_id}`, `DELETE /bills/{bill_id}/files/{file_id}`
- **payables_reports:** `GET /payables/aging`
- **petty_cash:** `GET /petty-cash/choices`, `GET /petty-cash`, `GET /petty-cash/{voucher_id}`, `POST /petty-cash`, `PUT /petty-cash/{voucher_id}`, `DELETE /petty-cash/{voucher_id}`, `POST /petty-cash/{voucher_id}/lines/{line_id}/file`, `GET /petty-cash/{voucher_id}/lines/{line_id}/file`, `DELETE /petty-cash/{voucher_id}/lines/{line_id}/file`, `POST /petty-cash/{voucher_id}/submit`, `POST /petty-cash/{voucher_id}/check`, `POST /petty-cash/{voucher_id}/return`, `POST /petty-cash/{voucher_id}/void`
- **prices:** `GET /finance/prices/waiting`, `POST /finance/prices/decide`, `POST /finance/prices/quotes/{quote_id}/decide`
- **profile:** `GET /auth/profile`, `PUT /auth/profile`, `POST /auth/password`, `GET /auth/signature`, `PUT /auth/signature`, `POST /auth/signature/remove`, `GET /auth/activity`
- **receivables:** `GET /finance/receivables`
- **reports:** `GET /finance/reports`, `GET /finance/reports/{key}`
- **tax:** `GET /tax/setup`, `PUT /tax/profile`, `POST /tax/rates`, `POST /tax/compute`
- **unset:** `GET /finance/unset`, `GET /finance/frame`
- **vouchers:** `GET /vouchers`, `GET /vouchers/choices`, `POST /vouchers`, `GET /vouchers/{voucher_id}`, `PUT /vouchers/{voucher_id}`, `POST /vouchers/{voucher_id}/submit`, `POST /vouchers/{voucher_id}/return`, `POST /vouchers/{voucher_id}/release`, `POST /vouchers/{voucher_id}/cancel`, `POST /vouchers/{voucher_id}/void`, `POST /vouchers/{voucher_id}/files`, `GET /vouchers/{voucher_id}/files/{file_id}`, `DELETE /vouchers/{voucher_id}/files/{file_id}`

</details>

## Pharmacy

Code in `backend/modules/pharmacy`, its API under `/pharmacy` in the one backend, screens at `/pharmacy` in the one app.

### Screens (the sidebar)

- **Home:** Home (`/pharmacy`)
- **Dispensing:** Prescriptions (`/pharmacy/prescriptions`), Dispensing (`/pharmacy/dispensing`), Sales (`/pharmacy/sales`)
- **Customers:** Patients and customers (`/pharmacy/patients`)
- **Inventory:** Medicines (`/pharmacy/medicines`), Batches and expiry (`/pharmacy/batches`), Stock (`/pharmacy/stock`), Suppliers (`/pharmacy/suppliers`)
- **Approvals:** Promotional materials (`/pharmacy/material-reviews`)
- **Reports:** Reports (`/pharmacy/reports`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbph_roles` | Role |
| `nbph_role_permissions` | RolePermission |
| `nbph_users` | User |
| `nbph_platform_passes` | A pass from the platform already taken: each one works once |
| `nbph_sessions` | One sign-in |
| `nbph_audit_log` | Who changed what, and when |
| `nbph_counters` | The last number handed out per kind and year: RX-2026-00125 is the 125th prescription of 2026 |
| `nbph_categories` | Category |
| `nbph_brands` | Brand |
| `nbph_medicines` | Medicine |
| `nbph_suppliers` | Supplier |
| `nbph_receivings` | One delivery taken in: which supplier, their invoice, and the batches it brought |
| `nbph_batches` | One lot of one medicine: its expiry, what came in and what is left |
| `nbph_stock_movements` | Every change to a batch's quantity, so what's on hand can always be explained |
| `nbph_patients` | Patient |
| `nbph_prescriptions` | Prescription |
| `nbph_prescription_items` | One medicine on a prescription, as written, and matched to the catalogue when checked |
| `nbph_dispensings` | One hand-over against a verified prescription |
| `nbph_dispensing_lines` | DispensingLine |
| `nbph_sales` | Sale |
| `nbph_sale_lines` | SaleLine |
| `nbph_returns` | Medicines brought back on a sale, and what was paid back for them (a refund may be nothing, as for an exchange) |
| `nbph_material_reviews` | A promotional material's design sent by Admin (routers/material_reviews.py) for the pharmacist's approval before it's produced: approved, re |

### Reports

- **Dispensing:** Dispensing by pharmacist, Dispensing summary
- **Inventory:** Expiring batches *(fixed)*, Medicine usage, Medicines to reorder, Stock summary
- **Prescriptions:** Prescriptions by prescriber, Prescriptions by status, Prescriptions checked by pharmacist, Prescriptions received
- **Sales:** Sales by payment method, Sales by source, Sales returns, Sales summary

### Permissions

| Area | Group | Actions |
|---|---|---|
| Dashboard (`dashboard`) | Pharmacy | view |
| Prescriptions (`prescriptions`) | Pharmacy | view, create, edit, verify |
| Dispensing (`dispensing`) | Pharmacy | view, create |
| Patients & customers (`patients`) | Pharmacy | view, create, edit, delete |
| Sales (`sales`) | Pharmacy | view, create, refund |
| Medicines, categories & brands (`medicines`) | Stock | view, create, edit, delete |
| Batches & expiry (`batches`) | Stock | view, manage |
| Stock (`stock`) | Stock | view, receive, adjust |
| Suppliers (`suppliers`) | Stock | view, create, edit, delete |
| Promotional material reviews (`materials`) | Pharmacy | view, review |
| Reports (`reports`) | Reports | view |
| Administration (`admin`) | Administration | users, roles, audit |

### Links to other apps

- **Calls:** none
- **Offers to other apps:** `POST /integration/checks`, `GET /integration/checks/{source_id}`

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `SESSION_HOURS`, `PLATFORM_PUBLIC_KEY`, `PLATFORM_API_URL`, `PLATFORM_APP_KEY`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `EXPIRY_WARNING_DAYS`, `PRESCRIPTION_VALID_DAYS`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`, `INTEGRATION_KEYS`

### API endpoints

<details><summary>84 endpoints in 15 files</summary>

- **admin:** `GET /admin/users`, `POST /admin/users`, `GET /admin/users/{user_id}`, `PATCH /admin/users/{user_id}`, `POST /admin/users/{user_id}/password`, `GET /admin/roles`, `POST /admin/roles`, `PATCH /admin/roles/{role_id}`, `DELETE /admin/roles/{role_id}`, `GET /admin/audit`
- **auth:** `POST /auth/login`, `POST /auth/platform`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/leave`, `GET /auth/view-as`, `POST /auth/view-as`
- **batches:** `GET /batches`, `GET /batches/{batch_id}`, `POST /batches/{batch_id}/status`
- **dispensing:** `GET /dispensing/queue`, `GET /dispensing/prepare/{prescription_id}`, `POST /dispensing`, `GET /dispensing`, `GET /dispensing/{dispensing_id}`
- **integration:** `POST /integration/checks`, `GET /integration/checks/{source_id}`
- **material_reviews:** `GET /material-reviews`, `GET /material-reviews/{review_id}`, `GET /material-reviews/{review_id}/file`, `POST /material-reviews/{review_id}/decision`
- **medicines:** `GET /medicines/categories`, `POST /medicines/categories`, `PUT /medicines/categories/{category_id}`, `DELETE /medicines/categories/{category_id}`, `GET /medicines/brands`, `POST /medicines/brands`, `PUT /medicines/brands/{brand_id}`, `DELETE /medicines/brands/{brand_id}`, `GET /medicines`, `GET /medicines/reference`, `POST /medicines`, `GET /medicines/{medicine_id}`, `PATCH /medicines/{medicine_id}`, `DELETE /medicines/{medicine_id}`
- **patients:** `GET /patients`, `POST /patients`, `GET /patients/{patient_id}`, `PATCH /patients/{patient_id}`, `DELETE /patients/{patient_id}`
- **prescriptions:** `GET /prescriptions/counts`, `GET /prescriptions`, `POST /prescriptions`, `GET /prescriptions/{prescription_id}`, `PATCH /prescriptions/{prescription_id}`, `POST /prescriptions/{prescription_id}/check`
- **profile:** `GET /auth/account`, `GET /auth/profile`, `PUT /auth/profile`, `POST /auth/password`, `GET /auth/activity`
- **reports:** `GET /reports`, `GET /reports/{key}`, `GET /dashboard`
- **sales:** `GET /sales`, `POST /sales`, `GET /sales/returns`, `GET /sales/{sale_id}`, `POST /sales/{sale_id}/returns`
- **stock:** `GET /stock`, `GET /stock/receivings`, `GET /stock/receivings/{receiving_id}`, `POST /stock/receivings`, `POST /stock/adjustments`, `GET /stock/movements`
- **suppliers:** `GET /suppliers`, `POST /suppliers`, `GET /suppliers/{supplier_id}`, `PATCH /suppliers/{supplier_id}`, `DELETE /suppliers/{supplier_id}`
- **unset:** `GET /unset`, `GET /frame`

</details>

## Executive Admin (Office)

Code in `backend/modules/admin`, its API under `/admin` in the one backend, screens at `/admin` in the one app.

### Screens (the sidebar)

- **Home:** Home (`/admin`)
- **Compliance:** Renewal alerts (`/admin/notifications`), Permits (`/admin/permits`), Documents (`/admin/documents`), Expatriates (`/admin/immigration`), Properties (`/admin/properties`)
- **Fleet and travel:** Vehicles (`/admin/vehicles`), Fuel cards (`/admin/fuel-cards`), Hotel and flights (`/admin/travel`), Devices issued (`/admin/devices`)
- **Service requests:** Office requests (`/admin/tickets`)
- **Marketing:** Promotional materials (`/admin/materials`)
- **Reports:** Reports (`/admin/reports`)

### Records (tables)

| Table | What it is |
|---|---|
| `nbad_roles` | Role |
| `nbad_role_permissions` | RolePermission |
| `nbad_users` | User |
| `nbad_platform_passes` | A pass from the platform already taken: each one works once |
| `nbad_sessions` | One sign-in |
| `nbad_audit_log` | The activity log: who changed what, and when |
| `nbad_compliance_records` | Corporate and regulatory registrations, permits, and accreditations (BOC, SEC, BIR, LGU, FDA) |
| `nbad_immigration_records` | Expatriate, executive visas, Alien Certificate of Registration (ACR I-Card), DOLE AEP, and passports |
| `nbad_corporate_documents` | Commercial contracts, corporate insurance policies (D&O, CGL, property), and board resolutions |
| `nbad_properties` | Corporate facilities, office leases, pharma warehouses, depot facilities, and utilities |
| `nbad_tickets` | Office concerns, administrative service desk requests, facilities, and executive VIP logistics |
| `nbad_ticket_updates` | Updates and comments on office concern tickets |
| `nbad_notifications` | Proactive expiration countdowns, renewal alerts, and milestone warnings |
| `nbad_vehicles` | A company car or motorcycle: its registration, insurance and maintenance falling due |
| `nbad_fleet_cards` | A fuel card given to a salesperson: their allowance, the car it's for, and whether it works |
| `nbad_travel_sponsorships` | A doctor's hotel stay or flight the company pays for, asked for by a rep |
| `nbad_device_issues` | A laptop, phone or SIM handed to someone, and who signed for it |
| `nbad_record_events` | What happened to a vehicle, fuel card, sponsorship or device issue, for its history: added, changed, renewed, PMS done, booked, blocked, a n |
| `nbad_stored_files` | An uploaded file (a promotional material's design), kept in the database itself: a server without a lasting disk (Vercel) keeps it all the s |
| `nbad_promo_materials` | A promotional material (a leaflet, a poster, a giveaway): designed by the marketing assistant, approved by the pharmacist in Pharmacy, produ |
| `nbad_promo_versions` | One design of a material, as sent to the pharmacist |
| `nbad_promo_productions` | A print run or order of a material: ordered, then received into stock (or cancelled) |
| `nbad_promo_distributions` | Some of a material given to a CRM team (or one person in it), once the team's manager approves in the CRM |

### Reports

- **Compliance:** Expired and not renewed, Lease schedule *(fixed)*, Permits by agency *(fixed)*, Renewals due
- **Fleet and travel:** Devices issued, Fuel cards, Hotel and flight requests, Travel requests by requester, Vehicle renewals and maintenance
- **Marketing:** Material distributions, Promotional materials stock
- **Service requests:** Office requests by assignee, Office requests by category, Overdue office requests

### Permissions

| Area | Group | Actions |
|---|---|---|
| Dashboard & countdowns (`dashboard`) | Executive | view |
| Corporate permits & accreditations (`permits`) | Compliance | view, create, edit, delete |
| Expatriate & visa compliance (`immigration`) | Immigration | view, create, edit, delete |
| Corporate documents & insurance (`documents`) | Legal & Corporate | view, create, edit, delete |
| Properties & lease management (`properties`) | Real Estate | view, create, edit, delete |
| Company vehicles and fuel cards (`vehicles`) | Fleet and travel | view, create, edit, delete |
| Hotel and flight sponsorships (`travel`) | Fleet and travel | view, create, edit, delete |
| Laptops, phones and SIMs issued (`devices`) | Fleet and travel | view, create, edit, delete |
| Office concerns & service desk (`tickets`) | Office Services | view, create, edit, assign, resolve, delete |
| Promotional materials (`materials`) | Marketing | view, create, edit, produce, distribute, delete |
| Renewal alerts & countdowns (`notifications`) | Executive | view, acknowledge, resolve |
| Administration (`admin`) | Administration | users, roles, audit |

### Links to other apps

- **Calls:** pharmacy, crm
- **Offers to other apps:** none

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `BACKUP_FROM`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `SESSION_HOURS`, `PLATFORM_API_URL`, `PLATFORM_PUBLIC_KEY`, `PLATFORM_APP_KEY`, `PHARMACY_API_URL`, `PHARMACY_API_KEY`, `CRM_API_URL`, `CRM_API_KEY`, `INTEGRATION_KEYS`, `COMPANY`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`

### API endpoints

<details><summary>75 endpoints in 7 files</summary>

- **admin:** `GET /admin/dashboard`, `GET /admin/permits`, `POST /admin/permits`, `PATCH /admin/permits/{permit_id}`, `DELETE /admin/permits/{permit_id}`, `GET /admin/immigration`, `POST /admin/immigration`, `PATCH /admin/immigration/{record_id}`, `DELETE /admin/immigration/{record_id}`, `GET /admin/documents`, `POST /admin/documents`, `PATCH /admin/documents/{doc_id}`, `DELETE /admin/documents/{doc_id}`, `GET /admin/properties`, `POST /admin/properties`, `PATCH /admin/properties/{property_id}`, `DELETE /admin/properties/{property_id}`, `GET /admin/tickets`, `POST /admin/tickets`, `GET /admin/tickets/{ticket_id}`, `PATCH /admin/tickets/{ticket_id}`, `POST /admin/tickets/{ticket_id}/updates`, `DELETE /admin/tickets/{ticket_id}`, `GET /admin/notifications`, `POST /admin/notifications/sync`, `PATCH /admin/notifications/{notif_id}/acknowledge`, `PATCH /admin/notifications/{notif_id}/resolve`, `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{user_id}`, `POST /admin/users/{user_id}/password`, `GET /admin/roles`, `POST /admin/roles`, `PATCH /admin/roles/{role_id}`, `DELETE /admin/roles/{role_id}`, `GET /admin/audit`
- **auth:** `POST /auth/login`, `POST /auth/platform`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/leave`, `GET /auth/view-as`, `POST /auth/view-as`
- **materials:** `GET /admin/materials`, `POST /admin/materials`, `GET /admin/materials/teams`, `GET /admin/materials/{material_id}`, `POST /admin/materials/{material_id}/refresh`, `PATCH /admin/materials/{material_id}`, `DELETE /admin/materials/{material_id}`, `POST /admin/materials/{material_id}/retire`, `PUT /admin/materials/{material_id}/design`, `GET /admin/materials/{material_id}/versions/{number}/file`, `GET /admin/materials/{material_id}/proofs/{ref}`, `POST /admin/materials/{material_id}/submit`, `POST /admin/materials/{material_id}/productions`, `POST /admin/materials/{material_id}/productions/{production_id}/received`, `POST /admin/materials/{material_id}/productions/{production_id}/cancel`, `POST /admin/materials/{material_id}/distributions`, `POST /admin/materials/{material_id}/distributions/{distribution_id}/distributed`, `POST /admin/materials/{material_id}/distributions/{distribution_id}/cancel`
- **profile:** `GET /auth/account`, `GET /auth/profile`, `PUT /auth/profile`, `POST /auth/password`, `GET /auth/activity`
- **reports:** `GET /admin/reports`
- **sheets:** `GET /admin/reports/overview`, `GET /admin/reports/{kind}`, `GET /admin/imports/{kind}/template`, `POST /admin/imports/{kind}/read`, `POST /admin/imports/{kind}`
- **unset:** `GET /admin/unset`

</details>

## In-Licensing

Code in `backend/modules/in_licensing`, its API under `/in-licensing` in the one backend, screens at `/in-licensing` in the one app.

### Screens (the sidebar)

- None found.

### Records (tables)

| Table | What it is |
|---|---|
| `nbil_users` | User |
| `nbil_sessions` | One sign-in |

### Reports

- None.

### Permissions

- None declared.

### Links to other apps

- **Calls:** none
- **Offers to other apps:** none

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `SESSION_HOURS`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`

### API endpoints

<details><summary>7 endpoints in 1 files</summary>

- **auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/view-as`, `POST /auth/leave`

</details>

## Regulatory

Code in `backend/modules/regulatory`, its API under `/regulatory` in the one backend, screens at `/regulatory` in the one app.

### Screens (the sidebar)

- None found.

### Records (tables)

| Table | What it is |
|---|---|
| `nbrg_users` | User |
| `nbrg_sessions` | One sign-in |

### Reports

- None.

### Permissions

- None declared.

### Links to other apps

- **Calls:** none
- **Offers to other apps:** none

### Settings (names only)

`ENVIRONMENT`, `DATABASE_URL`, `SESSION_HOURS`, `LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `ORG_NAME`, `ORG_CURRENCY`, `ORG_MINOR_UNITS`, `ORG_LOCALE`, `ORG_TIMEZONE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `DISCORD_ENABLED`, `DISCORD_MODE`, `DISCORD_BOT_TOKEN`, `DISCORD_LOGS_WEBHOOK_URL`, `DISCORD_MAX_PER_MINUTE`

### API endpoints

<details><summary>7 endpoints in 1 files</summary>

- **auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-accounts`, `POST /auth/switch-org`, `POST /auth/view-as`, `POST /auth/leave`

</details>
