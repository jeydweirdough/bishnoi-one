"""Import a useful directory without pretending imported tax hints are confirmed."""
import json
import re
from app.supplier_import import Review, clean_supplier_row


def directory_value(row):
    row = row.model_copy(update={"review": Review()})
    value, notes, errors, reviews = clean_supplier_row(row)
    unresolved = {}
    hints = {k: getattr(row, k) for k in ("tax_name", "tax_percentage", "tax_type", "taxable", "track_tds", "terms_label", "accounts_payable", "shipping_address") if getattr(row, k)}
    candidates = [v.value for v in row.tin_sources] or ([row.tin] if row.tin else [])
    numbers = {re.sub(r"[\s-]", "", v) for v in candidates}
    if len(numbers) > 1 or any("Invalid TIN" in e for e in errors):
        value["tin"] = value["branchCode"] = None
        unresolved["tinCandidates"] = [v.model_dump(by_alias=True) for v in row.tin_sources] or candidates
    # Ignore incoming review defaults: this operation imports directory facts only.
    value["vatRegistered"] = None
    value["withholding"] = value["payablesAccountId"] = None
    value["name"] = (row.name or row.company_name or "").strip()
    if not value["name"] or len(value["name"]) > 200:
        return value, {}, ["No usable supplier name (1 to 200 characters)."]
    for field, limit in {"companyName": 200, "salutation": 10, "firstName": 80, "lastName": 80, "email": 254, "phone": 40, "mobile": 40, "address": 300, "notes": 500}.items():
        if value[field] and len(value[field]) > limit:
            unresolved[field] = value[field]
            value[field] = None
    contacts = []
    for contact in value["contacts"]:
        if len(contact.get("phone", "")) > 40:
            unresolved.setdefault("additionalNumbers", []).append(contact)
        else:
            contacts.append(contact)
    value["contacts"] = contacts
    if not 0 <= value["termsDays"] <= 365:
        unresolved["paymentTerms"] = row.terms
        value["termsDays"] = 30
    details = {"hints": hints, "unresolved": unresolved}
    if row.terms_label:
        details["sourceTerms"] = {"days": row.terms, "label": row.terms_label}
    if not value["tin"]:
        details["missingTin"] = True
    # Bounded, allowlisted values only. Never archive arbitrary file columns.
    if len(json.dumps(details).encode()) > 32768:
        return value, {}, ["Source details exceed the per-supplier retention limit."]
    return value, details, []


def classify_directory(rows, existing):
    candidates = [directory_value(row) for row in rows]
    by_name = {}
    by_tin = {}
    for index, (value, _, errors) in enumerate(candidates):
        if errors:
            continue
        by_name.setdefault(value["name"].casefold(), []).append(index)
        if value["tin"]:
            by_tin.setdefault((value["tin"], value["branchCode"]), []).append(index)
    conflicts, duplicates = set(), set()
    for groups, field in ((by_name.values(), "tin"), (by_tin.values(), "name")):
        for group in groups:
            identities = {(candidates[i][0]["tin"], candidates[i][0]["branchCode"]) for i in group if candidates[i][0]["tin"]} if field == "tin" else {candidates[i][0]["name"].casefold() for i in group}
            if len(identities) > 1:
                conflicts.update(group)
            else:
                best = max(group, key=lambda i: (bool(candidates[i][0]["tin"]), sum(bool(v) for v in candidates[i][0].values()), -i))
                duplicates.update(i for i in group if i != best)
    out = []
    for index, (value, details, errors) in enumerate(candidates):
        matched = next((s for s in existing if s.name.strip().casefold() == value["name"].casefold() or (value["tin"] and (s.tin, s.branch_code) == (value["tin"], value["branchCode"]))), None)
        existing_conflict = matched and matched.tin and value["tin"] and (matched.tin, matched.branch_code) != (value["tin"], value["branchCode"])
        status = "problem" if errors else "conflict" if index in conflicts or existing_conflict else "here" if matched else "duplicate" if index in duplicates else "new"
        note = " ".join(errors) if errors else "Conflicting identities excluded; no automatic merge." if status == "conflict" else "Already here; left unchanged." if status == "here" else "Repeated supplier excluded." if status == "duplicate" else "Directory only; tax defaults not confirmed."
        out.append({"line": index + 1, "record": rows[index].record or index + 1, "status": status, "note": note, "supplier": value, "importDetails": details, "errors": errors, "reviews": [], "warnings": [], "accountMatches": []})
    return {"rows": out, "counts": {state: sum(r["status"] == state for r in out) for state in ("new", "here", "duplicate", "conflict", "problem")}, "payablesAccounts": [], "withholding": []}
