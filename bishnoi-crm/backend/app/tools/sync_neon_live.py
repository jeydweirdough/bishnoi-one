"""Live Neon PostgreSQL & SQLite Database Synchronization Pipeline
Purges all test accounts (@pharmacrm.test, @getmeds.test).
Populates real Getmeds commercial staff (67 accounts across 10 teams) and master employee directory (122 employees).
Sets initial password to "2.4Billion".
"""

import io
import json
import os
import sys
import uuid
from datetime import datetime, UTC
import openpyxl
import psycopg

# Set console output encoding to utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Paths
STRUCTURE_XLSX = r"C:\Users\Getmeds Backend\Downloads\STRUCTURE UPDATED.xlsx"
EMPLOYEES_XLSX = r"C:\Users\Getmeds Backend\Downloads\employees_2026-10-10.xlsx"

CRM_NEON_GETMEDS_URL = "postgresql://neondb_owner:npg_K4FmOfRkalv9@ep-jolly-sun-b3r8zkb6-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb_getmeds?sslmode=require"
CRM_NEON_BASE_URL = "postgresql://neondb_owner:npg_K4FmOfRkalv9@ep-jolly-sun-b3r8zkb6-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
PLATFORM_NEON_URL = "postgresql://neondb_owner:npg_6EzWjIiafN8H@ep-bold-scene-b3exva3n-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

GETMEDS_COMPANY_ID = "724d4179-c200-4be9-9567-07f7c7b811f4"
DEFAULT_PASSWORD = "2.4Billion"

NAME_MAP = {
    # Heads
    "JAVED": "sales1@getmeds.ph",
    "SUBIR": "sales5@getmeds.ph",
    "VANESSA": "sales3@getmeds.ph",
    "MHALOU": "finance@getmeds.ph",
    
    # Team Leads / Supervisors
    "HONEY": "sales9@getmeds.ph",
    "SHIELA": "care20@getmeds.ph",
    "KZ": "msr3@getmeds.ph",
    "MITZY": "care21@getmeds.ph",
    "KHALY": "care22@getmeds.ph",
    "JESSA DOMINO": "sales5@2mginc.com",
    "JIMLORD": "sales15@getmeds.ph",
    "DANIEL": "sales4@getmeds.ph",
    "SAURAV": "saurav@getmeds.ph",
    "JULIUS": "sales10@getmeds.ph",
    "KEN": "sales3@2mginc.com",
    
    # Sales Reps
    "MARWIN DY": "taftbnb@getmeds.ph",
    "JERICHO ART DAHILIG": "pgh2@getmeds.ph",
    "ANGELICA SALUDES": "uro.pgh@getmeds.ph",
    "MERYANIE ARCANGEL": "davao@getmeds.ph",
    "ANTONNETE LAWAS": "cebustc@getmeds.ph",
    "JICE JOY FAJARDO": "urocebu@getmeds.ph",
    "KEVIN SEAN APID": "cavite2@getmeds.ph",
    "ALYSSA MADERA": "urosl@getmeds.ph",
    "GIENEL CARLOS": "pabaza2@getmeds.ph",
    "ELOISA VILLANDA": "stc.qc@getmeds.ph",
    "MARY JOYCE SEBASTIAN": "qc2@getmeds.ph",
    "CJ": "care23@getmeds.ph",
    "CJ GUTIERREZ": "care23@getmeds.ph",
    "CJ Gutierrez": "care23@getmeds.ph",
    "JANE": "care16@getmeds.ph",
    "MARY JANE VINAS": "care16@getmeds.ph",
    "Mary Jane Vinas": "care16@getmeds.ph",
    "DHON": "sales19@getmeds.ph",
    "FLOREMEL TAN MEDINA": "sales21@getmeds.ph",
    "FRITZIE ROSANN MIER": "sales1@2mginc.com",
    "CLAIRE": "sales14@getmeds.ph",
    "LONIE": "sales20@getmeds.ph",
    "PILLOW": "care1@getmeds.ph",
    "CHARLE": "sales17@getmeds.ph",
    "MANI MISHRA": "manimishra@getmeds.ph",
    "HAZEL": "gov4@getmeds.ph",
    "ANGEL": "gov3@getmeds.ph",
    "JIMMY": "gov1@getmeds.ph",
    "ANNIE MAGLATANG": "sales2@getmeds.ph",
    "Annie Maglatang": "sales2@getmeds.ph",
    "NICKA": "sales6@getmeds.ph",
    "MICAH": "care24@getmeds.ph",
    "Micah": "care24@getmeds.ph",
    "SHEENA": "sales27@getmeds.ph",
    "Sheena": "sales27@getmeds.ph",
    "AYLA": "sales24@getmeds.ph",
    "PRINCESS": "qc4@getmeds.ph",
    "JACOB": "marikina@getmeds.ph",
    "DEN JANE": "getmeds.camanava@gmail.com",
    "RYAN": "pgh@getmeds.ph",
    "LJ": "luisjasper948@gmail.com",
    "PATTRICK": "palawan@getmeds.ph",
    "ANA": "sales18@getmeds.ph",
    "ANDY": "cebusouth@getmeds.ph",
    "KRIS": "cebunorth@getmeds.ph",
    "JESSA": "iloilo@getmeds.ph",
    "GABBY": "baguio@getmeds.ph",
    "NICOLE": "nl2@getmeds.ph",
    "MEL": "cdo2@getmeds.ph",
    "RUBY": "davaonorth@getmeds.ph",
    "WELMAR": "davaosouth@getmeds.ph",
    "GENSAN CITY QUEEN": "gensan@getmeds.ph",
    "PAOLO": "cl@getmeds.ph",
    "CLARISSE": "laguna@getmeds.ph",
    "LALIEN": "bicol@getmeds.ph",
    "MICHAEL": "qc5@getmeds.ph",
    "GLENN": "cavite@getmeds.ph",
    "ARLENE": "sales16@getmeds.ph",
    "JASPER": "sales23@getmeds.ph",
}

TEAMS_CONFIG = {
    "B&B": ("sales1@getmeds.ph", "Rx Business - B&B Division", ["TAFT", "DAVAO", "CEBU", "SOUTH LUZON", "NCL", "EAST AVE", "E. RODRIGUEZ"]),
    "STC": ("sales1@getmeds.ph", "Rx Business - STC Division", ["TMC ORTIGAS", "KALAW", "DAVAO", "CEBU", "SOUTH LUZON", "NCL", "COMMONWEALTH"]),
    "URO": ("sales1@getmeds.ph", "Rx Business - URO Division", ["COMMONWEALTH", "TMC ORTIGAS", "KALAW", "DAVAO", "CEBU", "SOUTH LUZON", "NCL"]),
    "B2C": ("sales1@getmeds.ph", "MD Telesales / B2C", ["ON SITE"]),
    "B2B": ("sales5@getmeds.ph", "B2B Commercial Division", ["ON SITE", "BAMBANG"]),
    "BID": ("sales5@getmeds.ph", "Government Bidding Division", ["ON SITE"]),
    "CLIDP": ("sales5@getmeds.ph", "CLIDP Institutional Division", ["FIELD SALES"]),
    "TeleSales": ("sales3@getmeds.ph", "Hospital Telesales Division", ["ON SITE"]),
    "HOS": ("sales3@getmeds.ph", "Hospital Field Sales Division", [
        "COMMONWEALTH", "MARIKINA", "CAMANAVA", "PASAY", "LAS PINAS", "PALAWAN",
        "PARANAQUE", "SOUTH CEBU", "NORTH CEBU", "ILOILO", "BAGUIO", "TUGUEGARAO",
        "TACLOBAN", "CDO", "ZAMBOANGA", "DAVAO NORTH", "DAVAO SOUTH", "GENSAN",
        "PAMPANGA", "CABANATUAN", "LAGUNA", "BICOL", "QC", "CAVITE"
    ]),
    "Modern Trade": ("finance@getmeds.ph", "Modern Trade / Drugstore Channel", ["ON SITE"]),
}

def get_password_hash():
    from app.security import hash_password
    return hash_password(DEFAULT_PASSWORD)

def load_data():
    wb_emp = openpyxl.load_workbook(EMPLOYEES_XLSX, data_only=True)
    sheet_emp = wb_emp.active
    employees_by_email = {}
    all_employees = []

    for idx, r in enumerate(list(sheet_emp.iter_rows(values_only=True))[1:], 1):
        first = str(r[0] or "").strip()
        middle = str(r[1] or "").strip()
        last = str(r[2] or "").strip()
        dept = str(r[3] or "").strip()
        pos = str(r[4] or "").strip()
        email = str(r[5] or "").strip().lower()
        zoho_email = str(r[6] or "").strip().lower()
        work_email = str(r[7] or "").strip().lower()
        personal_email = str(r[8] or "").strip().lower()
        phone = str(r[9] or "").strip()
        if phone.endswith('.0'): phone = phone[:-2]

        p_email = email or zoho_email or work_email or personal_email
        full_name = f"{first} {middle} {last}".replace("  ", " ").strip()

        if not p_email:
            clean_first = "".join(c for c in first.lower() if c.isalnum())
            clean_last = "".join(c for c in last.lower() if c.isalnum())
            p_email = f"{clean_first}.{clean_last}@getmeds.ph"
        elif p_email in employees_by_email:
            if personal_email and personal_email not in employees_by_email:
                p_email = personal_email
            else:
                clean_first = "".join(c for c in first.lower() if c.isalnum())
                clean_last = "".join(c for c in last.lower() if c.isalnum())
                p_email = f"{clean_first}.{clean_last}.{idx}@getmeds.ph"

        emp_obj = {
            'idx': idx,
            'first': first,
            'middle': middle,
            'last': last,
            'full_name': full_name,
            'dept': dept,
            'pos': pos,
            'email': p_email,
            'phone': phone
        }
        all_employees.append(emp_obj)
        employees_by_email[p_email] = emp_obj

    wb_struct = openpyxl.load_workbook(STRUCTURE_XLSX, data_only=True)
    sheet_struct = wb_struct.active
    rows_struct = list(sheet_struct.iter_rows(values_only=True))[1:]

    commercial_accounts = {}

    def add_comm(email, full_name, role_name, team_name, title="", phone=""):
        email = email.lower().strip()
        if email in commercial_accounts:
            existing = commercial_accounts[email]
            ranks = {"Administrator": 4, "Manager": 3, "Team Lead": 2, "Salesperson": 1}
            if ranks.get(role_name, 1) > ranks.get(existing['role'], 1):
                existing['role'] = role_name
            if not existing['team'] and team_name:
                existing['team'] = team_name
            return
        commercial_accounts[email] = {
            'email': email,
            'full_name': full_name,
            'role': role_name,
            'team': team_name,
            'title': title,
            'phone': phone
        }

    heads = [
        ("JAVED", "sales1@getmeds.ph", "STC", "Country Head"),
        ("SUBIR", "sales5@getmeds.ph", "B2B", "Sales & Marketing Manager"),
        ("VANESSA", "sales3@getmeds.ph", "HOS", "Business Unit Mentor"),
        ("MHALOU", "finance@getmeds.ph", "Modern Trade", "Finance Manager"),
    ]
    for code, email, team, title in heads:
        emp = employees_by_email.get(email, {})
        fn = emp.get('full_name', code.title())
        ph = emp.get('phone', '')
        add_comm(email, fn, "Manager", team, title, ph)

    leads = [
        ("HONEY", "sales9@getmeds.ph", "B2C", "Sales Manager"),
        ("SHIELA", "care20@getmeds.ph", "B&B", "Sales Admin Assistant"),
        ("KZ", "msr3@getmeds.ph", "URO", "Sales Admin Assistant"),
        ("MITZY", "care21@getmeds.ph", "STC", "Telemarketer"),
        ("KHALY", "care22@getmeds.ph", "B&B", "Telemarketer"),
        ("JESSA DOMINO", "sales5@2mginc.com", "B2B", "B2B Team Lead"),
        ("JIMLORD", "sales15@getmeds.ph", "HOS", "District Sales Manager"),
        ("DANIEL", "sales4@getmeds.ph", "HOS", "District Sales Manager - Hospital"),
        ("SAURAV", "saurav@getmeds.ph", "HOS", "District Sales Manager - Mindanao"),
        ("JULIUS", "sales10@getmeds.ph", "HOS", "District Sales Manager - Interim"),
        ("KEN", "sales3@2mginc.com", "HOS", "District Sales Manager - South Luzon"),
    ]
    for code, email, team, title in leads:
        emp = employees_by_email.get(email, {})
        fn = emp.get('full_name', code.title())
        ph = emp.get('phone', '')
        add_comm(email, fn, "Team Lead", team, title, ph)

    current_head = None
    current_channel = None
    for idx, r in enumerate(rows_struct, 1):
        head = r[0]
        channel = r[1]
        territory = str(r[4] or "").strip()
        sales_person = str(r[5] or "").strip()
        zoho_name = str(r[6] or "").strip()
        division = str(r[7] or "").strip()

        if head: current_head = str(head).strip()
        if channel: current_channel = str(channel).strip()

        comb = f"{territory} {sales_person} {zoho_name}".upper()
        if any(k in comb for k in ["TOTAL", "GRAND TOTAL"]) or not comb.strip():
            continue
        if sales_person.upper() == "VACANT":
            continue

        email = NAME_MAP.get(sales_person) or NAME_MAP.get(sales_person.upper())
        if not email:
            continue

        team = "HOS"
        div_upper = division.upper().strip()
        ch_upper = (current_channel or "").upper().strip()

        if "RX BUSINESS" in ch_upper or div_upper in ["B&B", "STC", "URO"]:
            if "B&B" in div_upper or "B&B" in territory.upper(): team = "B&B"
            elif "STC" in div_upper or "STC" in territory.upper(): team = "STC"
            elif "URO" in div_upper or "URO" in territory.upper(): team = "URO"
            else: team = "STC"
        elif "MD TELESALES" in ch_upper or "B2C" in div_upper or "B2C" in territory.upper():
            team = "B2C"
        elif "B2B" in ch_upper or "B2B" in div_upper:
            team = "B2B"
        elif "BID" in ch_upper or "BID" in div_upper:
            team = "BID"
        elif "CLIDP" in ch_upper or "CLIDP" in div_upper:
            team = "CLIDP"
        elif "TELESALES" in ch_upper or "TELESALES" in div_upper:
            team = "TeleSales"
        elif "HOS" in ch_upper or "HOSP" in div_upper or "HOS" in div_upper:
            team = "HOS"
        elif "MT" in ch_upper or "MODERN TRADE" in div_upper or "MT" in div_upper:
            team = "Modern Trade"

        emp = employees_by_email.get(email, {})
        fn = emp.get('full_name', sales_person.title())
        pos = emp.get('pos', 'Product Specialist')
        ph = emp.get('phone', '')

        add_comm(email, fn, "Salesperson", team, pos, ph)

    return all_employees, employees_by_email, commercial_accounts

def sync_platform_neon(all_employees, commercial_accounts, pwd_hash):
    print("\n--- Synchronizing Platform Neon PostgreSQL ---")
    now = datetime.now(UTC)
    email_to_id = {}

    with psycopg.connect(PLATFORM_NEON_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, id FROM nbpl_applications")
            apps = dict(cur.fetchall())
            crm_app_id = apps.get("crm")

            cur.execute("SELECT LOWER(email), id FROM nbpl_identities WHERE company_id = %s", (GETMEDS_COMPANY_ID,))
            existing = dict(cur.fetchall())

            created = 0
            updated = 0

            for emp in all_employees:
                email = emp['email'].lower().strip()
                if not email:
                    continue
                fn = emp['full_name']
                title = emp['pos']
                is_admin = (email in ["naresh@getmeds.ph", "ai4@getmeds.ph"])

                if email in existing:
                    ident_id = existing[email]
                    cur.execute("""
                        UPDATE nbpl_identities
                        SET full_name = %s, title = %s, status = 'active', password_hash = %s, password_changed_at = %s, is_company_admin = %s
                        WHERE id = %s
                    """, (fn, title, pwd_hash, now, is_admin, ident_id))
                    updated += 1
                elif email in email_to_id:
                    ident_id = email_to_id[email]
                else:
                    ident_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO nbpl_identities (id, company_id, full_name, email, title, is_company_admin, status, created_at, password_hash, password_changed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s)
                    """, (ident_id, GETMEDS_COMPANY_ID, fn, email, title, is_admin, now, pwd_hash, now))
                    created += 1
                    existing[email] = ident_id

                email_to_id[email] = ident_id

            # Grant CRM app access to commercial accounts
            for email, comm in commercial_accounts.items():
                ident_id = email_to_id.get(email)
                if not ident_id:
                    continue
                role = comm['role']
                is_app_admin = (role == "Administrator" or email in ["naresh@getmeds.ph", "ai4@getmeds.ph"])
                cur.execute("SELECT 1 FROM nbpl_identity_apps WHERE identity_id = %s AND application_id = %s", (ident_id, crm_app_id))
                if cur.fetchone():
                    cur.execute("""
                        UPDATE nbpl_identity_apps
                        SET role = %s, is_app_admin = %s
                        WHERE identity_id = %s AND application_id = %s
                    """, (role, is_app_admin, ident_id, crm_app_id))
                else:
                    cur.execute("""
                        INSERT INTO nbpl_identity_apps (identity_id, application_id, role, is_app_admin, granted_at, granted_by)
                        VALUES (%s, %s, %s, %s, %s, 'Excel Structure Import')
                    """, (ident_id, crm_app_id, role, is_app_admin, now))

            # Department app grants
            dept_map = {
                "operations - pharmacy": ("pharmacy", "Pharmacist"),
                "operation pharmacy": ("pharmacy", "Pharmacist"),
                "finance": ("finance", "Member"),
                "in-licensing": ("inlicensing", "Member"),
                "regulatory affairs": ("regulatory", "Member"),
                "executive management": ("exec", "Executive Assistant"),
            }
            for emp in all_employees:
                email = emp['email']
                ident_id = email_to_id.get(email)
                if not ident_id:
                    continue
                dept_lower = emp['dept'].lower().strip()
                if dept_lower in dept_map:
                    app_key, default_role = dept_map[dept_lower]
                    t_app_id = apps.get(app_key)
                    if t_app_id:
                        cur.execute("SELECT 1 FROM nbpl_identity_apps WHERE identity_id = %s AND application_id = %s", (ident_id, t_app_id))
                        if not cur.fetchone():
                            cur.execute("""
                                INSERT INTO nbpl_identity_apps (identity_id, application_id, role, is_app_admin, granted_at, granted_by)
                                VALUES (%s, %s, %s, false, %s, 'Excel Employee Import')
                            """, (ident_id, t_app_id, default_role, now))

            conn.commit()
            print(f"Platform Neon: {created} created, {updated} updated (Total: {len(email_to_id)})")

    return email_to_id

def sync_crm_neon_db(db_url, db_label, commercial_accounts, email_to_identity_id, pwd_hash):
    print(f"\n--- Synchronizing CRM Neon PostgreSQL ({db_label}) ---")
    now = datetime.now(UTC)

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Fetch CRM roles
            cur.execute("SELECT name, id FROM nbcm_roles")
            roles = dict(cur.fetchall())
            print(f"CRM Roles in {db_label}: {roles}")

            admin_role_id = roles.get("Administrator")
            mgr_role_id = roles.get("Manager")
            lead_role_id = roles.get("Team Lead")
            rep_role_id = roles.get("Salesperson")

            # 2. Ensure ai4@getmeds.ph exists as primary Admin anchor
            cur.execute("SELECT id FROM nbcm_users WHERE LOWER(email) = 'ai4@getmeds.ph'")
            row_ai4 = cur.fetchone()
            if row_ai4:
                ai4_user_id = row_ai4[0]
                cur.execute("""
                    UPDATE nbcm_users
                    SET role_id = %s, password_hash = %s, password_changed_at = %s, is_active = true
                    WHERE id = %s
                """, (admin_role_id, pwd_hash, now, ai4_user_id))
            else:
                ai4_user_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO nbcm_users (id, email, full_name, password_hash, is_active, created_at, password_changed_at, role_id)
                    VALUES (%s, 'ai4@getmeds.ph', 'Jade Atyla Madigal', %s, true, %s, %s, %s)
                """, (ai4_user_id, pwd_hash, now, now, admin_role_id))

            # 3. Find all test accounts
            cur.execute("SELECT id, email, full_name FROM nbcm_users WHERE email LIKE '%@pharmacrm.test' OR email LIKE '%@getmeds.test'")
            test_users = cur.fetchall()
            test_user_ids = [u[0] for u in test_users]
            print(f"Identified {len(test_users)} test users to purge in {db_label}: {[u[1] for u in test_users]}")

            if test_user_ids:
                # Reassign foreign keys to ai4_user_id so we do NOT lose records or trigger FK constraint failures
                cur.execute("UPDATE nbcm_companies SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_companies SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_companies SET pinned_by_id = NULL WHERE pinned_by_id = ANY(%s)", (test_user_ids,))

                cur.execute("UPDATE nbcm_contacts SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_contacts SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))

                cur.execute("UPDATE nbcm_quotes SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_quotes SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))

                cur.execute("UPDATE nbcm_deals SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_deals SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))

                cur.execute("UPDATE nbcm_activities SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_activities SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))

                cur.execute("UPDATE nbcm_fund_requests SET owner_id = %s WHERE owner_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_fund_requests SET created_by_id = %s WHERE created_by_id = ANY(%s)", (ai4_user_id, test_user_ids))
                cur.execute("UPDATE nbcm_fund_requests SET decided_by_id = %s WHERE decided_by_id = ANY(%s)", (ai4_user_id, test_user_ids))

                # Delete test user sessions and personal tracking logs
                cur.execute("DELETE FROM nbcm_sessions WHERE user_id = ANY(%s)", (test_user_ids,))
                cur.execute("DELETE FROM nbcm_trail_batches WHERE user_id = ANY(%s)", (test_user_ids,))
                cur.execute("DELETE FROM nbcm_route_days WHERE user_id = ANY(%s)", (test_user_ids,))
                cur.execute("DELETE FROM nbcm_kpi_targets WHERE user_id = ANY(%s)", (test_user_ids,))
                cur.execute("DELETE FROM nbcm_attention_dismissals WHERE user_id = ANY(%s)", (test_user_ids,))

                # Clear manager_id on teams if it points to a test user
                cur.execute("UPDATE nbcm_teams SET manager_id = NULL WHERE manager_id = ANY(%s)", (test_user_ids,))

                # Finally delete test users
                cur.execute("DELETE FROM nbcm_users WHERE id = ANY(%s)", (test_user_ids,))
                print(f"Successfully deleted {len(test_user_ids)} test users from {db_label}.")

            # 4. Synchronize teams
            cur.execute("SELECT name, id FROM nbcm_teams")
            teams = dict(cur.fetchall())

            def has_column(table, col):
                cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s", (table, col))
                return cur.fetchone() is not None

            has_share_customers = has_column("nbcm_teams", "share_customers")

            for team_name, (mgr_email, desc, hq_list) in TEAMS_CONFIG.items():
                hq_json = json.dumps(hq_list)
                if team_name in teams:
                    t_id = teams[team_name]
                    cur.execute("""
                        UPDATE nbcm_teams
                        SET description = %s, headquarters = %s, is_active = true
                        WHERE id = %s
                    """, (desc, hq_json, t_id))
                else:
                    t_id = str(uuid.uuid4())
                    if has_share_customers:
                        cur.execute("""
                            INSERT INTO nbcm_teams (id, name, description, headquarters, is_active, created_at, share_customers)
                            VALUES (%s, %s, %s, %s, true, %s, true)
                        """, (t_id, team_name, desc, hq_json, now))
                    else:
                        cur.execute("""
                            INSERT INTO nbcm_teams (id, name, description, headquarters, is_active, created_at)
                            VALUES (%s, %s, %s, %s, true, %s)
                        """, (t_id, team_name, desc, hq_json, now))
                    teams[team_name] = t_id
                    print(f"Created CRM Team in {db_label}: {team_name}")

            # 5. Synchronize Admin Naresh
            cur.execute("SELECT id FROM nbcm_users WHERE LOWER(email) = 'naresh@getmeds.ph'")
            row_naresh = cur.fetchone()
            naresh_ident_id = email_to_identity_id.get("naresh@getmeds.ph")
            if row_naresh:
                cur.execute("""
                    UPDATE nbcm_users
                    SET full_name = 'Naresh Kumar Bishnoi', role_id = %s, password_hash = %s, password_changed_at = %s, is_active = true, platform_identity_id = COALESCE(%s, platform_identity_id)
                    WHERE id = %s
                """, (admin_role_id, pwd_hash, now, naresh_ident_id, row_naresh[0]))
            else:
                cur.execute("""
                    INSERT INTO nbcm_users (id, email, full_name, password_hash, is_active, created_at, password_changed_at, role_id, platform_identity_id)
                    VALUES (%s, 'naresh@getmeds.ph', 'Naresh Kumar Bishnoi', %s, true, %s, %s, %s, %s)
                """, (str(uuid.uuid4()), pwd_hash, now, now, admin_role_id, naresh_ident_id))

            # 6. Synchronize all commercial accounts
            cur.execute("SELECT LOWER(email), id FROM nbcm_users")
            existing_crm_users = dict(cur.fetchall())

            created_crm = 0
            updated_crm = 0
            user_email_to_id = {}

            for email, comm in commercial_accounts.items():
                fn = comm['full_name']
                r_name = comm['role']
                r_id = roles.get(r_name, rep_role_id)
                t_name = comm['team']
                t_id = teams.get(t_name)
                p_ident_id = email_to_identity_id.get(email)

                if email in existing_crm_users:
                    u_id = existing_crm_users[email]
                    cur.execute("""
                        UPDATE nbcm_users
                        SET full_name = %s, role_id = %s, team_id = %s, platform_identity_id = COALESCE(%s, platform_identity_id), password_hash = %s, password_changed_at = %s, is_active = true
                        WHERE id = %s
                    """, (fn, r_id, t_id, p_ident_id, pwd_hash, now, u_id))
                    updated_crm += 1
                    user_email_to_id[email] = u_id
                else:
                    u_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO nbcm_users (id, email, full_name, password_hash, is_active, created_at, password_changed_at, role_id, team_id, platform_identity_id)
                        VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, %s)
                    """, (u_id, email, fn, pwd_hash, now, now, r_id, t_id, p_ident_id))
                    created_crm += 1
                    user_email_to_id[email] = u_id

            # 7. Update team manager_ids
            for t_name, (mgr_email, _, _) in TEAMS_CONFIG.items():
                m_id = user_email_to_id.get(mgr_email)
                t_id = teams.get(t_name)
                if t_id and m_id:
                    cur.execute("UPDATE nbcm_teams SET manager_id = %s WHERE id = %s", (m_id, t_id))

            conn.commit()

            cur.execute("SELECT count(*), count(CASE WHEN email LIKE '%test' THEN 1 END) FROM nbcm_users")
            total_users, test_cnt = cur.fetchone()
            print(f"Summary for {db_label}: Total users = {total_users}, Test users = {test_cnt} (Created: {created_crm}, Updated: {updated_crm})")

def main():
    print("=================================================================")
    print("   BISHNOI ONE COMMERCIAL HIERARCHY & REAL NEON DB SYNC PIPELINE ")
    print("=================================================================")

    all_employees, employees_by_email, commercial_accounts = load_data()
    print(f"\nLoaded {len(all_employees)} employees from {os.path.basename(EMPLOYEES_XLSX)}")
    print(f"Resolved {len(commercial_accounts)} commercial hierarchy accounts from {os.path.basename(STRUCTURE_XLSX)}")

    pwd_hash = get_password_hash()
    print(f"Computed password hash for '{DEFAULT_PASSWORD}'.")

    # 1. Synchronize Platform Neon
    email_to_identity_id = sync_platform_neon(all_employees, commercial_accounts, pwd_hash)

    # 2. Synchronize CRM Tenant Neon DB (neondb_getmeds)
    sync_crm_neon_db(CRM_NEON_GETMEDS_URL, "neondb_getmeds", commercial_accounts, email_to_identity_id, pwd_hash)

    # 3. Synchronize CRM Base Neon DB (neondb)
    sync_crm_neon_db(CRM_NEON_BASE_URL, "neondb", commercial_accounts, email_to_identity_id, pwd_hash)

    print("\n=================================================================")
    print("                 NEON SYNC COMPLETED SUCCESSFULLY                ")
    print("=================================================================")

if __name__ == '__main__':
    main()
