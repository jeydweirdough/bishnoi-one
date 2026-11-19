"""Wipe all Customers (Companies and Contacts) in Bishnoi CRM.
Targets:
1. Neon PostgreSQL: neondb_getmeds and neondb
2. SQLite: crm-getmeds.db and crm.db
"""

import io
import os
import shutil
import sqlite3
import sys
import psycopg

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def _neon(setting: str, database: str) -> str:
    """A Neon database's address, from a setting (never written here: decided 2026-10-27,
    when the passwords were found in these files). The setting is the project's base
    address (…/neondb?sslmode=require); the company's database is beside it."""
    import os

    base = os.environ.get(setting)
    if not base:
        raise SystemExit(f"Set {setting} to the Neon project's address (…/neondb?sslmode=require), e.g. in this shell only.")
    return base.replace("/neondb?", f"/{database}?")


CRM_GETMEDS_URL = _neon("CRM_NEON_URL", "neondb_getmeds")
CRM_BASE_URL = _neon("CRM_NEON_URL", "neondb")
CRM_GETMEDS_SQLITE = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-crm\backend\.data\crm-getmeds.db"
CRM_BASE_SQLITE = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-crm\backend\.data\crm.db"

def make_backup(file_path):
    if not os.path.exists(file_path):
        return
    backup_dir = os.path.join(os.path.dirname(file_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{base_name}_{ts}.bak")
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")

def table_exists_pg(cur, table_name):
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table_name,))
    return cur.fetchone()[0]

def table_exists_sqlite(cur, table_name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cur.fetchone() is not None

def wipe_customers_postgres(db_url, db_label):
    print(f"\n--- Wiping Customers in PostgreSQL ({db_label}) ---")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            comp_count = 0
            cont_count = 0
            if table_exists_pg(cur, "nbcm_companies"):
                cur.execute("SELECT count(*) FROM nbcm_companies")
                comp_count = cur.fetchone()[0]
            if table_exists_pg(cur, "nbcm_contacts"):
                cur.execute("SELECT count(*) FROM nbcm_contacts")
                cont_count = cur.fetchone()[0]
            print(f"Current count in {db_label}: {comp_count} companies, {cont_count} contacts.")

            # 1. Nullify company references in fund requests
            if table_exists_pg(cur, "nbcm_fund_requests"):
                cur.execute("UPDATE nbcm_fund_requests SET company_id = NULL WHERE company_id IS NOT NULL")

            # 2. Clean activities and activity links
            if table_exists_pg(cur, "nbcm_activity_links"):
                cur.execute("DELETE FROM nbcm_activity_links")
            if table_exists_pg(cur, "nbcm_activities"):
                cur.execute("DELETE FROM nbcm_activities")

            # 3. Clean visits, balances, media views
            if table_exists_pg(cur, "nbcm_visits"):
                cur.execute("DELETE FROM nbcm_visits")
            if table_exists_pg(cur, "nbcm_balances"):
                cur.execute("DELETE FROM nbcm_balances")
            if table_exists_pg(cur, "nbcm_media_views"):
                cur.execute("DELETE FROM nbcm_media_views")

            # 4. Clean associations involving companies or contacts
            if table_exists_pg(cur, "nbcm_associations"):
                cur.execute("DELETE FROM nbcm_associations WHERE from_type IN ('company', 'contact') OR to_type IN ('company', 'contact')")

            # 5. Clean duplicate tracking
            if table_exists_pg(cur, "nbcm_not_duplicates"):
                cur.execute("DELETE FROM nbcm_not_duplicates")
            if table_exists_pg(cur, "nbcm_merged_records"):
                cur.execute("DELETE FROM nbcm_merged_records")
            if table_exists_pg(cur, "nbcm_attention_dismissals"):
                cur.execute("DELETE FROM nbcm_attention_dismissals")

            # 6. Wipe contacts
            if table_exists_pg(cur, "nbcm_contacts"):
                cur.execute("DELETE FROM nbcm_contacts")

            # 7. Wipe companies (customers)
            if table_exists_pg(cur, "nbcm_companies"):
                cur.execute("DELETE FROM nbcm_companies")

            conn.commit()

            cur.execute("SELECT count(*) FROM nbcm_companies")
            rem_comp = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM nbcm_contacts")
            rem_cont = cur.fetchone()[0]
            print(f"After wipe in {db_label}: Companies = {rem_comp}, Contacts = {rem_cont}")

def wipe_customers_sqlite(db_path, db_name):
    print(f"\n--- Wiping Customers in SQLite ({db_name}: {db_path}) ---")
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} (does not exist)")
        return
    make_backup(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    comp_count = 0
    cont_count = 0
    if table_exists_sqlite(c, "nbcm_companies"):
        c.execute("SELECT count(*) FROM nbcm_companies")
        comp_count = c.fetchone()[0]
    if table_exists_sqlite(c, "nbcm_contacts"):
        c.execute("SELECT count(*) FROM nbcm_contacts")
        cont_count = c.fetchone()[0]
    print(f"Current count in SQLite {db_name}: {comp_count} companies, {cont_count} contacts.")

    if table_exists_sqlite(c, "nbcm_fund_requests"):
        c.execute("UPDATE nbcm_fund_requests SET company_id = NULL WHERE company_id IS NOT NULL")
    if table_exists_sqlite(c, "nbcm_activity_links"):
        c.execute("DELETE FROM nbcm_activity_links")
    if table_exists_sqlite(c, "nbcm_activities"):
        c.execute("DELETE FROM nbcm_activities")
    if table_exists_sqlite(c, "nbcm_visits"):
        c.execute("DELETE FROM nbcm_visits")
    if table_exists_sqlite(c, "nbcm_balances"):
        c.execute("DELETE FROM nbcm_balances")
    if table_exists_sqlite(c, "nbcm_media_views"):
        c.execute("DELETE FROM nbcm_media_views")
    if table_exists_sqlite(c, "nbcm_associations"):
        c.execute("DELETE FROM nbcm_associations WHERE from_type IN ('company', 'contact') OR to_type IN ('company', 'contact')")
    if table_exists_sqlite(c, "nbcm_not_duplicates"):
        c.execute("DELETE FROM nbcm_not_duplicates")
    if table_exists_sqlite(c, "nbcm_merged_records"):
        c.execute("DELETE FROM nbcm_merged_records")
    if table_exists_sqlite(c, "nbcm_attention_dismissals"):
        c.execute("DELETE FROM nbcm_attention_dismissals")

    if table_exists_sqlite(c, "nbcm_contacts"):
        c.execute("DELETE FROM nbcm_contacts")
    if table_exists_sqlite(c, "nbcm_companies"):
        c.execute("DELETE FROM nbcm_companies")

    conn.commit()

    c.execute("SELECT count(*) FROM nbcm_companies")
    rem_comp = c.fetchone()[0]
    c.execute("SELECT count(*) FROM nbcm_contacts")
    rem_cont = c.fetchone()[0]
    conn.close()

    print(f"After wipe in SQLite {db_name}: Companies = {rem_comp}, Contacts = {rem_cont}")

def main():
    print("=================================================================")
    print("           WIPE ALL CRM CUSTOMERS (COMPANIES & CONTACTS)         ")
    print("=================================================================")

    # 1. Reset in PostgreSQL (Production Neon)
    wipe_customers_postgres(CRM_GETMEDS_URL, "neondb_getmeds")
    wipe_customers_postgres(CRM_BASE_URL, "neondb")

    # 2. Reset in SQLite
    wipe_customers_sqlite(CRM_GETMEDS_SQLITE, "crm-getmeds.db")
    wipe_customers_sqlite(CRM_BASE_SQLITE, "crm.db")

    print("\n=================================================================")
    print("       ALL CUSTOMERS & CONTACTS WIPED TO 0 SUCCESSFULLY         ")
    print("=================================================================")

if __name__ == '__main__':
    main()
