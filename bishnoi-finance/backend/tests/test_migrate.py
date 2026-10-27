"""A database from before migrations (plain users and sessions, made by
create_all) keeps its accounts, under the nbfi_ names."""

from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.migrate import _config

OLD_USERS = (
    "CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) UNIQUE, full_name VARCHAR(120), password_hash VARCHAR(255), "
    "role VARCHAR(16), is_active BOOLEAN, created_at DATETIME, password_changed_at DATETIME)"
)
OLD_SESSIONS = (
    "CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) UNIQUE, "
    "user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE, created_at DATETIME, expires_at DATETIME, revoked_at DATETIME)"
)


def test_an_old_database_keeps_its_accounts(tmp_path):
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text(OLD_USERS))
        c.execute(text(OLD_SESSIONS))
        c.execute(text("INSERT INTO users VALUES ('u1', 'old@example.com', 'Old Admin', 'x', 'admin', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"))
    engine.dispose()
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = app.state.sessions.kw["bind"]
    with engine.connect() as c:
        assert c.execute(text("SELECT email FROM nbfi_users")).scalars().all() == ["old@example.com"]
    tables = set(inspect(engine).get_table_names())
    # The old names are gone, and every table is Finance's.
    assert {"nbfi_users", "nbfi_sessions", "nbfi_alembic_version"} <= tables
    assert all(t.startswith("nbfi_") for t in tables), tables
    engine.dispose()


def test_upgrading_a_database_with_entries_and_invoices_keeps_every_row(tmp_path):
    """Found 2026-10-23: on SQLite, a migration that rebuilds a table drops the old one, and
    whatever points at it with ON DELETE CASCADE or SET NULL went with it (journal lines,
    invoice payments, the default accounts). Our migrations from 0013 on add in place."""
    url = f"sqlite:///{(tmp_path / 'kept.db').as_posix()}"
    engine = make_engine(url)
    command.upgrade(_config(engine), "0012")
    with engine.begin() as c:
        cash, sales = (c.execute(text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar() for code in ("1000", "4000"))
        c.execute(text("INSERT INTO nbfi_journal_entries (id, number, entry_date, memo, source, posted_by, created_at) "
                       "VALUES ('e1', 'JE-202610-0001', '2026-10-01', 'Kept', 'invoice', 'Ana', '2026-10-01 00:00:00')"))
        c.execute(text("INSERT INTO nbfi_journal_lines (entry_id, position, account_id, debit_centavos, credit_centavos) VALUES "
                       "('e1', 0, :cash, 100, 0), ('e1', 1, :sales, 0, 100)"), {"cash": cash, "sales": sales})
        c.execute(text("INSERT INTO nbfi_invoices (id, status, customer_name, treatment, invoice_date, terms_days, lines, total_centavos, tax_centavos, "
                       "paid_centavos, entry_id, created_at, created_by) VALUES ('i1', 'issued', 'Kept Drug', 'regular', '2026-10-01', 30, '[]', 100, 0, 100, 'e1', "
                       "'2026-10-01 00:00:00', 'Ana')"))
        c.execute(text("INSERT INTO nbfi_invoice_payments (id, invoice_id, paid_on, amount_centavos, method, entry_id, recorded_by, recorded_at) "
                       "VALUES ('p1', 'i1', '2026-10-02', 100, 'cash', 'e1', 'Ana', '2026-10-02 00:00:00')"))
        before = c.execute(text("SELECT * FROM nbfi_ledger_settings")).mappings().one()
    engine.dispose()
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = app.state.sessions.kw["bind"]
    with engine.connect() as c:
        count = lambda table: c.execute(text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: E731
        assert (count("nbfi_journal_lines"), count("nbfi_invoice_payments")) == (2, 1)
        assert c.execute(text("SELECT entry_id FROM nbfi_invoices WHERE id = 'i1'")).scalar() == "e1"
        after = c.execute(text("SELECT * FROM nbfi_ledger_settings")).mappings().one()
        assert {k: after[k] for k in before} == dict(before)  # every default account kept
        assert c.execute(text("SELECT count(*) FROM nbfi_expense_categories WHERE account_id IS NOT NULL")).scalar() > 0
        assert c.execute(text("SELECT version_num FROM nbfi_alembic_version")).scalar() == "0025"
    engine.dispose()


def test_the_old_supplier_tick_becomes_add_edit_and_switch_off(tmp_path):
    """0018 split suppliers.manage (2026-10-23): whoever had it keeps all of it, and whoever
    recorded bills (which included making them) can still make them (and 0020 retires recording)."""
    url = f"sqlite:///{(tmp_path / 'ticks.db').as_posix()}"
    engine = make_engine(url)
    command.upgrade(_config(engine), "0017")
    with engine.begin() as c:
        c.execute(text("INSERT INTO nbfi_roles (id, name, description, is_system) VALUES ('r1', 'Accounts Payable', '', 0)"))
        c.execute(text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES ('r1', 'suppliers.manage'), ('r1', 'bills.record')"))
    engine.dispose()
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = app.state.sessions.kw["bind"]
    with engine.connect() as c:
        ticks = set(c.execute(text("SELECT permission FROM nbfi_role_permissions WHERE role_id = 'r1'")).scalars())
    assert ticks == {"suppliers.add", "suppliers.edit", "suppliers.deactivate", "bills.create"}
    engine.dispose()


def test_bills_get_their_approval_and_half_checked_vouchers_are_ready_to_release(tmp_path):
    """0020 (Aubrey's flow, 2026-10-23): the checks move from the voucher to the bill. Whoever
    recorded bills keeps making them; the voucher's check, approve and told-first ticks go; a
    voucher waiting to be checked is ready to release, its notification done; bills are kept."""
    url = f"sqlite:///{(tmp_path / 'flow.db').as_posix()}"
    engine = make_engine(url)
    command.upgrade(_config(engine), "0019")
    with engine.begin() as c:
        c.execute(text("INSERT INTO nbfi_roles (id, name, description, is_system) VALUES ('r1', 'Finance Deputy', '', 0)"))
        c.execute(text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES ('r1', 'bills.record'), ('r1', 'vouchers.check'), "
                       "('r1', 'vouchers.approve'), ('r1', 'vouchers.first'), ('r1', 'vouchers.release')"))
        c.execute(text("INSERT INTO nbfi_users (id, email, full_name, password_hash, role, role_id, is_active, created_at, password_changed_at) "
                       "VALUES ('u1', 'c@example.com', 'Cristal', 'x', 'member', 'r1', 1, '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))
        c.execute(text("INSERT INTO nbfi_suppliers (id, name, vat_registered, terms_days, is_active, created_at, created_by) "
                       "VALUES ('s1', 'Sample Supplier', 1, 30, 1, '2026-10-01 00:00:00', 'Ana')"))
        c.execute(text("INSERT INTO nbfi_bills (id, status, supplier_id, bill_number, bill_date, due_date, checked_po, checked_dr, amounts_include_vat, lines, "
                       "net_centavos, vat_centavos, withheld_centavos, total_centavos, payable_centavos, paid_centavos, created_at, created_by) "
                       "VALUES ('b1', 'recorded', 's1', 'SI-1', '2026-10-01', '2026-10-31', 0, 0, 1, '[]', 100, 0, 0, 100, 100, 0, '2026-10-01 00:00:00', 'Ana')"))
        c.execute(text("INSERT INTO nbfi_payment_vouchers (id, number, status, supplier_id, method, total_centavos, prepared_by, created_at, updated_at) "
                       "VALUES ('v1', 'PV-202610-0001', 'to_check', 's1', 'bank', 100, 'Ana', '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))
        c.execute(text("INSERT INTO nbfi_notifications (id, user_id, kind, text, link, created_at) "
                       "VALUES ('n1', 'u1', 'voucher.to_check', 'Waiting', '/vouchers/v1', '2026-10-01 00:00:00')"))
    engine.dispose()
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = app.state.sessions.kw["bind"]
    with engine.connect() as c:
        ticks = set(c.execute(text("SELECT permission FROM nbfi_role_permissions WHERE role_id = 'r1'")).scalars())
        assert ticks == {"bills.create", "vouchers.release"}
        assert c.execute(text("SELECT status FROM nbfi_payment_vouchers WHERE id = 'v1'")).scalar() == "to_release"
        assert c.execute(text("SELECT read_at FROM nbfi_notifications WHERE id = 'n1'")).scalar() is not None
        assert c.execute(text("SELECT status, stage FROM nbfi_bills WHERE id = 'b1'")).one() == ("recorded", None)
        assert "nbfi_bill_events" in inspect(engine).get_table_names()
    engine.dispose()
