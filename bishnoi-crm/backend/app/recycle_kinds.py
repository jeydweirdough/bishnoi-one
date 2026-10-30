"""What an administrator can clean up in the CRM (app/recycle_bin.py, 2026-10-30). People, roles and teams
aren't here: they're kept on the Platform (Admin Console → People)."""

from app.recycle_bin import Kind

P = "nbcm_"

KINDS: list[Kind] = [
    # Records
    Kind("customers", "Customers", P + "companies", "name", owns=(P + "visits", P + "plan_stops", P + "activity_links", P + "balances", P + "assistance", P + "deals"),
         search=("name", "code"), sub="code", tables_named={P + "deals": "deals"}),
    Kind("contacts", "Contacts", P + "contacts", lambda r: " ".join(x for x in (r.get("first_name"), r.get("last_name")) if x) or r.get("email") or r.get("id"),
         search=("first_name", "last_name", "email", "phone"), sub="email"),
    Kind("deals", "Deals", P + "deals", "name", search=("name",)),
    Kind("quotes", "Quotes", P + "quotes", lambda r: r.get("number") or r.get("id"), owns=(P + "quote_controls", P + "quote_links"), search=("number", "customer_name"), sub="customer_name"),
    Kind("activities", "Activities", P + "activities", lambda r: r.get("subject") or r.get("kind"), owns=(P + "activity_links",), search=("subject",), sub="kind"),
    Kind("visits", "Visits", P + "visits", lambda r: f"Visit {str(r.get('visited_at') or r.get('created_at') or '')[:16]}", sub="outcome"),
    Kind("leads", "Inbox leads", P + "inbox_leads", "name", search=("name",), sub="status"),
    Kind("media", "Media", P + "media", "title", owns=(P + "media_views",), search=("title",)),
    Kind("saved-views", "Saved views", P + "saved_views", "name", search=("name",)),
    # Set-up lists
    Kind("customer-types", "Customer types", P + "customer_types", "name", group="Set-up", search=("name", "code"), sub="code"),
    Kind("products", "Products", P + "products", "name", group="Set-up", owns=(P + "product_prices", P + "team_prices"), search=("name", "code"), sub="code"),
    Kind("price-types", "Price types", P + "price_types", "name", group="Set-up", owns=(P + "product_prices", P + "team_price_types", P + "team_prices"),
         search=("name", "code"), sub="code"),
    Kind("price-groups", "Price groups", P + "price_groups", "name", group="Set-up", search=("name", "code")),
    Kind("price-conditions", "Price conditions", P + "price_conditions", "name", group="Set-up", search=("name",)),
    Kind("promos", "Promos", P + "promos", "name", group="Set-up", search=("name",), sub="kind"),
    Kind("bundles", "Bundles", P + "bundles", "name", group="Set-up", search=("name", "code"), sub="code"),
    Kind("kpis", "KPIs", P + "kpis", "name", group="Set-up", owns=(P + "kpi_targets", P + "kpi_entries"), search=("name", "code"), sub="code"),
    Kind("scorecards", "Scorecards", P + "scorecards", "name", group="Set-up", search=("name", "code")),
    Kind("issuers", "Issuers", P + "issuers", "name", group="Set-up", search=("name", "code")),
    Kind("quote-templates", "Quote templates", P + "quote_templates", "name", group="Set-up", search=("name",)),
    Kind("deal-stages", "Deal stages", P + "deal_stages", "name", group="Set-up", search=("name", "code")),
    Kind("association-labels", "Association labels", P + "association_labels", "name", group="Set-up", owns=(P + "associations",), search=("name", "code")),
    Kind("form-sections", "Customer form sections", P + "form_sections", "title", group="Set-up", search=("title",)),
    Kind("form-fields", "Customer form fields", P + "form_fields", "label", group="Set-up", search=("label",)),
    Kind("email-templates", "Email templates", P + "email_templates", "name", group="Set-up", search=("name", "subject")),
    Kind("attention-rules", "Attention rules", P + "attention_rules", lambda r: f"Attention rule ({r.get('quiet_days')} quiet days)", group="Set-up"),
]
