"""Finance's suppliers are Inventory's vendors: linked once, kept in step, never typed twice (2026-11-24)."""
from sqlalchemy import func, select

from modules.finance.models import CompanyScopeReview, Supplier
from modules.finance.vendors import saved
from .test_tax_api import app, client, ana  # noqa: F401
from .test_payables import supplier


def vendor(**more):
    return {"id": "TEST-INV-V1", "code": "GC045604", "name": "TEST Gloria Diaz Branch", "tin": "123-456-789-00000",
            "email": "orders@gloria.test", "phone": "0917 000 0000", "address": "Quezon City", "paymentTerms": "30 days",
            "vatStatus": "vat", "currency": "PHP", "isActive": True, **more}


def test_a_vendor_becomes_finances_supplier_once_and_follows_its_changes(app):
    with app.state.sessions() as db:
        first = saved(db, vendor()); db.commit()
        assert first.name == "TEST Gloria Diaz Branch" and first.tin == "123-456-789" and first.branch_code == "00000"
        assert first.terms_days == 30 and first.vat_registered and first.is_active
        again = saved(db, vendor(name="TEST Gloria Diaz Branch Inc.", paymentTerms="COD", isActive=False)); db.commit()
        assert again.id == first.id and again.name == "TEST Gloria Diaz Branch Inc." and again.terms_days == 0 and not again.is_active
        assert db.scalar(select(func.count()).select_from(Supplier).where(Supplier.tin == "123-456-789")) == 1


def test_a_supplier_finance_already_has_is_linked_not_copied(app, client, ana):
    have = supplier(client, ana, name="TEST Existing Supplier")
    with app.state.sessions() as db:
        got = saved(db, vendor(id="TEST-INV-V2", name="test existing supplier", tin=None)); db.commit()
        assert got.id == have["id"]


def test_books_that_review_suppliers_wait_for_a_person(app):
    with app.state.sessions() as db:
        db.add(CompanyScopeReview(subject_kind="supplier", subject_id="TEST-reviewed", scope="2mg", evidence={"source": "fictional test"}, reviewed_by="TEST"))
        db.commit()
        assert saved(db, vendor(id="TEST-INV-V3", name="TEST Unreviewed Vendor", tin=None)) is None
        assert db.scalar(select(Supplier).where(Supplier.name == "TEST Unreviewed Vendor")) is None
