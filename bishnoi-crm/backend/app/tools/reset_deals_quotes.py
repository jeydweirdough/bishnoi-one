"""Reset all Deals and Quotes to 0 in Bishnoi CRM.
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

CRM_GETMEDS_URL = "postgresql://neondb_owner:npg_K4FmOfRkalv9@ep-jolly-sun-b3r8zkb6-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb_getmeds?sslmode=require"
CRM_BASE_URL = "postgresql://neondb_owner:npg_K4FmOfRkalv9@ep-jolly-sun-b3r8zkb6-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

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

def reset_crm_postgres(db_url, db_label):
    print(f"\n--- Resetting Deals & Quotes in PostgreSQL ({db_label}) ---")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            deal_count = 0
            quote_count = 0
            if table_exists_pg(cur, "nbcm_deals"):
                cur.execute("SELECT count(*) FROM nbcm_deals")
                deal_count = cur.fetchone()[0]
            if table_exists_pg(cur, "nbcm_quotes"):
                cur.execute("SELECT count(*) FROM nbcm_quotes")
                quote_count = cur.fetchone()[0]
            print(f"Current count in {db_label}: {deal_count} deals, {quote_count} quotes.")

            # 1. Clean quote controls
            if table_exists_pg(cur, "nbcm_quote_controls"):
                cur.execute("DELETE FROM nbcm_quote_controls")
            # 2. Clean quote links
            if table_exists_pg(cur, "nbcm_quote_links"):
                cur.execute("DELETE FROM nbcm_quote_links")
            # 3. Clean associations with deal or quote
            if table_exists_pg(cur, "nbcm_associations"):
                cur.execute("DELETE FROM nbcm_associations WHERE from_type IN ('deal', 'quote') OR to_type IN ('deal', 'quote')")
            # 4. Clean quotes
            if table_exists_pg(cur, "nbcm_quotes"):
                cur.execute("DELETE FROM nbcm_quotes")
            # 5. Clean deals
            if table_exists_pg(cur, "nbcm_deals"):
                cur.execute("DELETE FROM nbcm_deals")

            conn.commit()

            remaining_deals = 0
            remaining_quotes = 0
            if table_exists_pg(cur, "nbcm_deals"):
                cur.execute("SELECT count(*) FROM nbcm_deals")
                remaining_deals = cur.fetchone()[0]
            if table_exists_pg(cur, "nbcm_quotes"):
                cur.execute("SELECT count(*) FROM nbcm_quotes")
                remaining_quotes = cur.fetchone()[0]
            print(f"After reset in {db_label}: Deals = {remaining_deals}, Quotes = {remaining_quotes}")

def reset_crm_sqlite(db_path, db_name):
    print(f"\n--- Resetting Deals & Quotes in SQLite ({db_name}: {db_path}) ---")
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} (does not exist)")
        return
    make_backup(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    deal_count = 0
    quote_count = 0
    if table_exists_sqlite(c, "nbcm_deals"):
        c.execute("SELECT count(*) FROM nbcm_deals")
        deal_count = c.fetchone()[0]
    if table_exists_sqlite(c, "nbcm_quotes"):
        c.execute("SELECT count(*) FROM nbcm_quotes")
        quote_count = c.fetchone()[0]
    print(f"Current count in SQLite {db_name}: {deal_count} deals, {quote_count} quotes.")

    if table_exists_sqlite(c, "nbcm_quote_controls"):
        c.execute("DELETE FROM nbcm_quote_controls")
    if table_exists_sqlite(c, "nbcm_quote_links"):
        c.execute("DELETE FROM nbcm_quote_links")
    if table_exists_sqlite(c, "nbcm_associations"):
        c.execute("DELETE FROM nbcm_associations WHERE from_type IN ('deal', 'quote') OR to_type IN ('deal', 'quote')")
    if table_exists_sqlite(c, "nbcm_quotes"):
        c.execute("DELETE FROM nbcm_quotes")
    if table_exists_sqlite(c, "nbcm_deals"):
        c.execute("DELETE FROM nbcm_deals")

    conn.commit()

    rem_deals = 0
    rem_quotes = 0
    if table_exists_sqlite(c, "nbcm_deals"):
        c.execute("SELECT count(*) FROM nbcm_deals")
        rem_deals = c.fetchone()[0]
    if table_exists_sqlite(c, "nbcm_quotes"):
        c.execute("SELECT count(*) FROM nbcm_quotes")
        rem_quotes = c.fetchone()[0]
    conn.close()

    print(f"After reset in SQLite {db_name}: Deals = {rem_deals}, Quotes = {rem_quotes}")

def main():
    print("=================================================================")
    print("           RESET ALL CRM DEALS & QUOTES TO ZERO (0)              ")
    print("=================================================================")

    # 1. Reset in PostgreSQL (Production Neon)
    reset_crm_postgres(CRM_GETMEDS_URL, "neondb_getmeds")
    reset_crm_postgres(CRM_BASE_URL, "neondb")

    # 2. Reset in SQLite
    reset_crm_sqlite(CRM_GETMEDS_SQLITE, "crm-getmeds.db")
    reset_crm_sqlite(CRM_BASE_SQLITE, "crm.db")

    print("\n=================================================================")
    print("            ALL DEALS & QUOTES CLEARED TO 0 SUCCESSFULLY         ")
    print("=================================================================")

if __name__ == '__main__':
    main()
