"""What an administrator can clean up in Executive Admin (app/recycle_bin.py, 2026-10-30). People and roles
aren't here: they're kept on the Platform (Admin Console → People)."""

from app.recycle_bin import Kind

P = "nbad_"

KINDS: list[Kind] = [
    Kind("tickets", "Tickets", P + "tickets", "title", owns=(P + "ticket_updates",), search=("title", "ticket_number", "requester_name"), sub="status"),
    Kind("vehicles", "Vehicles", P + "vehicles", "name", search=("name", "plate"), sub="plate"),
    Kind("fleet-cards", "Fleet cards", P + "fleet_cards", lambda r: f"{r.get('holder_name') or 'Fleet card'} ({r.get('plate') or r.get('no')})", search=("holder_name", "plate"), sub="status"),
    Kind("devices", "Device issues", P + "device_issues", lambda r: f"{r.get('issued_to') or 'Device'} {r.get('issued_on') or ''}".strip(), search=("issued_to", "laptop", "phone")),
    Kind("travel", "Travel sponsorships", P + "travel_sponsorships", lambda r: f"{r.get('doctor_name') or r.get('rep_name') or 'Travel'} ({r.get('kind') or ''})",
         search=("doctor_name", "rep_name"), sub="status"),
    Kind("properties", "Properties", P + "properties", "name", search=("name", "address"), sub="property_type"),
    Kind("immigration", "Immigration records", P + "immigration_records", lambda r: f"{r.get('individual_name')} · {r.get('document_type')}",
         search=("individual_name", "document_number"), sub="status"),
    Kind("documents", "Corporate documents", P + "corporate_documents", "title", search=("title", "counterparty", "reference_number"), sub="status"),
    Kind("permits", "Compliance records", P + "compliance_records", "title", search=("title", "agency", "reference_number"), sub="status"),
    Kind("materials", "Promo materials", P + "promo_materials", "title", owns=(P + "promo_versions", P + "promo_productions", P + "promo_distributions"),
         search=("title", "product"), sub="status"),
]
