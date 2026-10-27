"""Today's supplier balances, aged by due date. No historical balance claim."""

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
                  bucket: str | None = Query(None, max_length=12), format: Literal["json", "csv"] = "json"):
    if bucket and bucket not in {k for k, _, _ in BUCKETS}:
        raise field_error("bucket", "Pick a listed aging bucket.")
    found = aging(db, today(settings), supplier_id, bucket)
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
