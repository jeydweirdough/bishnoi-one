"""Supplier balances, aged by due date: today's, or as of an earlier day (rebuilt from dated bills,
payments and voids, app/payables_asof.py; 2026-10-29)."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query

from app.access import permitted
from app.deps import DB, SettingsDep
from app.payables_work import aging
from app.routers.bir import as_csv, pesos
from app.routers.funds import today
from app.routers.receivables import BUCKETS
from app.routers.tax import field_error

router = APIRouter(prefix="/payables", tags=["payables"])


@router.get("/aging")
def current_aging(_: permitted("bills.view"), db: DB, settings: SettingsDep,
                  supplier_id: str | None = Query(None, alias="supplierId", max_length=36),
                  bucket: str | None = Query(None, max_length=12), format: Literal["json", "csv"] = "json",
                  on: date | None = Query(None, alias="asOf")):
    if bucket and bucket not in {k for k, _, _ in BUCKETS}:
        raise field_error("bucket", "Pick a listed aging bucket.")
    now = today(settings)
    if on is not None and on > now:
        raise field_error("asOf", "Pick today or an earlier day.")
    found = aging(db, on or now, supplier_id, bucket, current=on is None or on == now)
    if format == "json":
        return found
    fields = [k for k, _, _ in BUCKETS]
    rows = [[found["on"], ("'" + s["name"] if s["name"].lstrip().startswith(("=", "+", "-", "@")) else s["name"]), len(s["bills"]), *[pesos(s["buckets"][k]) for k in fields],
             pesos(s["owedCentavos"]), pesos(s["reservedCentavos"]), pesos(s["availableCentavos"]), s["oldestDaysLate"]]
            for s in found["suppliers"]]
    rows.append([found["on"], "Total", found["billCount"], *[pesos(b["amountCentavos"]) for b in found["buckets"]],
                 *[pesos(found["totals"][k]) for k in ("owedCentavos", "reservedCentavos", "availableCentavos")], ""])
    return as_csv(f"Payables aging {found['on']}", ["Balance date", "Supplier", "Bills", *[label for _, label, _ in BUCKETS],
                                                    "Owed", "In unreleased vouchers", "Available to prepare", "Oldest days late"], rows)
