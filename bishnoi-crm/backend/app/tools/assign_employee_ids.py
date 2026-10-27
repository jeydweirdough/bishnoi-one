"""Assign clean sequential Employee IDs (EMP-0001, EMP-0002, ...) to all users in Bishnoi CRM.
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

def assign_employee_ids_postgres(db_url, db_label):
    print(f"\n--- Assigning Employee IDs in PostgreSQL ({db_label}) ---")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get all users ordered by priority:
            # 1. ai4@getmeds.ph (First Admin)
            # 2. ai2@getmeds.ph (Linus)
            # 3. All others ordered by team_id, email, full_name
            cur.execute("""
                SELECT id, email, full_name 
                FROM nbcm_users 
                ORDER BY 
                    CASE 
                        WHEN email = 'ai4@getmeds.ph' THEN 1 
                        WHEN email = 'ai2@getmeds.ph' THEN 2 
                        ELSE 3 
                    END,
                    email ASC
            """)
            users = cur.fetchall()
            print(f"Total users in {db_label}: {len(users)}")

            # First clear all employee_ids to prevent unique constraint collisions during renumbering
            cur.execute("UPDATE nbcm_users SET employee_id = NULL")

            for idx, (user_id, email, full_name) in enumerate(users, start=1):
                emp_code = f"EMP-{idx:04d}"
                cur.execute("UPDATE nbcm_users SET employee_id = %s WHERE id = %s", (emp_code, user_id))
                if email in ('ai4@getmeds.ph', 'ai2@getmeds.ph', 'sales24@getmeds.ph'):
                    print(f"  {email} ({full_name}) -> {emp_code}")

            conn.commit()

            cur.execute("SELECT count(*), count(employee_id) FROM nbcm_users")
            total, with_emp = cur.fetchone()
            print(f"After update in {db_label}: Total = {total}, With Employee ID = {with_emp}")

def assign_employee_ids_sqlite(db_path, db_name):
    print(f"\n--- Assigning Employee IDs in SQLite ({db_name}: {db_path}) ---")
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} (does not exist)")
        return
    make_backup(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
        SELECT id, email, full_name 
        FROM nbcm_users 
        ORDER BY 
            CASE 
                WHEN email = 'ai4@getmeds.ph' THEN 1 
                WHEN email = 'ai2@getmeds.ph' THEN 2 
                ELSE 3 
            END,
            email ASC
    """)
    users = c.fetchall()
    print(f"Total users in SQLite {db_name}: {len(users)}")

    c.execute("UPDATE nbcm_users SET employee_id = NULL")

    for idx, (user_id, email, full_name) in enumerate(users, start=1):
        emp_code = f"EMP-{idx:04d}"
        c.execute("UPDATE nbcm_users SET employee_id = ? WHERE id = ?", (emp_code, user_id))
        if email in ('ai4@getmeds.ph', 'ai2@getmeds.ph', 'sales24@getmeds.ph'):
            print(f"  {email} ({full_name}) -> {emp_code}")

    conn.commit()

    c.execute("SELECT count(*), count(employee_id) FROM nbcm_users")
    total, with_emp = c.fetchone()
    print(f"After update in SQLite {db_name}: Total = {total}, With Employee ID = {with_emp}")
    conn.close()

def main():
    print("=================================================================")
    print("           ASSIGN EMPLOYEE IDS TO ALL CRM USERS                  ")
    print("=================================================================")

    # 1. PostgreSQL
    assign_employee_ids_postgres(CRM_GETMEDS_URL, "neondb_getmeds")
    assign_employee_ids_postgres(CRM_BASE_URL, "neondb")

    # 2. SQLite
    assign_employee_ids_sqlite(CRM_GETMEDS_SQLITE, "crm-getmeds.db")
    assign_employee_ids_sqlite(CRM_BASE_SQLITE, "crm.db")

    print("\n=================================================================")
    print("           EMPLOYEE IDS ASSIGNED SUCCESSFULLY                    ")
    print("=================================================================")

if __name__ == '__main__':
    main()
