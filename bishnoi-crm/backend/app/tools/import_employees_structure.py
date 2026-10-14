"""Import employee accounts and commercial hierarchy from Excel workbooks into:
1. Bishnoi CRM tenant database: crm-getmeds.db (and crm.db)
2. Bishnoi One Platform SSO database: platform.db
3. Bishnoi Executive Admin database: admin.db

Sources:
- STRUCTURE UPDATED.xlsx (Commercial sales hierarchy, territories, and headquarters)
- employees_2026-10-10.xlsx (Employee master directory, emails, phone numbers, and job titles)
"""

import io
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, UTC
import openpyxl

# Set console output encoding to utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

STRUCTURE_XLSX = r"C:\Users\Getmeds Backend\Downloads\STRUCTURE UPDATED.xlsx"
EMPLOYEES_XLSX = r"C:\Users\Getmeds Backend\Downloads\employees_2026-10-10.xlsx"

CRM_GETMEDS_DB = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-crm\backend\.data\crm-getmeds.db"
CRM_DB = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-crm\backend\.data\crm.db"
PLATFORM_DB = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-platform\backend\.data\platform.db"
ADMIN_DB = r"C:\Users\Getmeds Backend\Desktop\bishnoi-one\bishnoi-admin\backend\.data\admin.db"

GETMEDS_COMPANY_ID = "724d4179-c200-4be9-9567-07f7c7b811f4"

# Default password for imported accounts (can be changed upon sign-in)
DEFAULT_PASSWORD = "2.4Billion"

def make_backup(file_path):
    if not os.path.exists(file_path):
        return
    backup_dir = os.path.join(os.path.dirname(file_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{base_name}_{ts}.bak")
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")

def get_password_hash():
    # Precomputed scrypt hash for 'demo1234' compatible with app.security
    from app.security import hash_password
    return hash_password(DEFAULT_PASSWORD)

# Canonical mapping from structure names / aliases to primary email
NAME_MAP = {
    # Heads
    "JAVED": "sales1@getmeds.ph",                    # Javed Shaikh
    "SUBIR": "sales5@getmeds.ph",                    # Subir Dey
    "VANESSA": "sales3@getmeds.ph",                  # Vanessa Tolentino Escalderon
    "MHALOU": "finance@getmeds.ph",                  # Marilou Mercado Jagonoy (Mhalou)
    
    # Team Leads / Supervisors
    "HONEY": "sales9@getmeds.ph",                    # Honey Salve Cordero
    "SHIELA": "care20@getmeds.ph",                   # Sheila Mae Yape Bazar
    "KZ": "msr3@getmeds.ph",                         # Kate Labaclado Cagoyong
    "MITZY": "care21@getmeds.ph",                    # Mitzi Villa Francisco
    "KHALY": "care22@getmeds.ph",                    # Khalygen Lopez Boayes
    "JESSA DOMINO": "sales5@2mginc.com",             # Jessa Rompe Domino
    "JIMLORD": "sales15@getmeds.ph",                 # Jim Lord Baron Dacpano Palomares
    "DANIEL": "sales4@getmeds.ph",                   # Daniel Andrew Pacificador Cruz
    "SAURAV": "saurav@getmeds.ph",                   # Saurav Kumar
    "JULIUS": "sales10@getmeds.ph",                  # Julius Santos Abucay
    "KEN": "sales3@2mginc.com",                      # Kindred Gadil Malaluan (Ken)
    
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

# Team configurations: (Manager email, description, default headquarters)
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

def load_data():
    # 1. Load employees
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

        # Ensure unique primary email per employee
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

    # 2. Load structure
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

    # Add Heads
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

    # Add Leads
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

    # Add Reps from rows
    current_head = None
    current_channel = None
    current_lead = None
    current_sublead = None

    for idx, r in enumerate(rows_struct, 1):
        head = r[0]
        channel = r[1]
        lead = r[2]
        sublead = r[3]
        territory = str(r[4] or "").strip()
        sales_person = str(r[5] or "").strip()
        zoho_name = str(r[6] or "").strip()
        division = str(r[7] or "").strip()
        sub_division = str(r[8] or "").strip()
        hq = str(r[9] or "").strip()

        if head: current_head = str(head).strip()
        if channel: current_channel = str(channel).strip()
        if lead: current_lead = str(lead).strip()
        if sublead: current_sublead = str(sublead).strip()

        comb = f"{territory} {sales_person} {zoho_name}".upper()
        if any(k in comb for k in ["TOTAL", "GRAND TOTAL"]) or not comb.strip():
            continue
        if sales_person.upper() == "VACANT":
            continue

        email = NAME_MAP.get(sales_person) or NAME_MAP.get(sales_person.upper())
        if not email:
            print(f"Warning: Unknown rep '{sales_person}' at row {idx}")
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

def sync_platform_db(all_employees, commercial_accounts, pwd_hash):
    print("\n--- Synchronizing Bishnoi One Platform (platform.db) ---")
    conn = sqlite3.connect(PLATFORM_DB)
    c = conn.cursor()

    # Get application IDs
    c.execute("SELECT key, id FROM nbpl_applications")
    apps = dict(c.fetchall())
    crm_app_id = apps.get("crm")
    print(f"CRM App ID in platform: {crm_app_id}")

    # Purge test identities
    c.execute("DELETE FROM nbpl_identities WHERE email LIKE '%@pharmacrm.test' OR email LIKE '%@getmeds.test'")
    conn.commit()

    # Track identities by email
    c.execute("SELECT LOWER(email), id FROM nbpl_identities WHERE company_id = ?", (GETMEDS_COMPANY_ID,))
    existing_identities = dict(c.fetchall())

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    identities_created = 0
    identities_updated = 0
    email_to_id = {}

    for emp in all_employees:
        email = emp['email'].lower().strip()
        if not email:
            continue
        
        full_name = emp['full_name']
        title = emp['pos']

        if email in existing_identities:
            ident_id = existing_identities[email]
            c.execute("""
                UPDATE nbpl_identities
                SET full_name = ?, title = ?, status = 'active'
                WHERE id = ?
            """, (full_name, title, ident_id))
            identities_updated += 1
            email_to_id[email] = ident_id
        elif email in email_to_id:
            continue
        else:
            ident_id = str(uuid.uuid4())
            c.execute("""
                INSERT INTO nbpl_identities (id, company_id, full_name, email, title, is_company_admin, status, created_at, password_hash, password_changed_at)
                VALUES (?, ?, ?, ?, ?, 0, 'active', ?, ?, ?)
            """, (ident_id, GETMEDS_COMPANY_ID, full_name, email, title, now, pwd_hash, now))
            identities_created += 1
            existing_identities[email] = ident_id
            email_to_id[email] = ident_id

    conn.commit()
    print(f"Platform identities: {identities_created} created, {identities_updated} updated (Total: {len(email_to_id)})")

    # Grant application access
    app_grants = 0
    for email, comm in commercial_accounts.items():
        ident_id = email_to_id.get(email)
        if not ident_id:
            continue
        role = comm['role']
        is_admin = 1 if role == "Administrator" else 0

        # Check existing grant
        c.execute("SELECT 1 FROM nbpl_identity_apps WHERE identity_id = ? AND application_id = ?", (ident_id, crm_app_id))
        if c.fetchone():
            c.execute("""
                UPDATE nbpl_identity_apps
                SET role = ?, is_app_admin = ?
                WHERE identity_id = ? AND application_id = ?
            """, (role, is_admin, ident_id, crm_app_id))
        else:
            c.execute("""
                INSERT INTO nbpl_identity_apps (identity_id, application_id, role, is_app_admin, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ident_id, crm_app_id, role, is_admin, now, "Excel Structure Import"))
            app_grants += 1

    # Grant access to other departmental apps
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
            target_app_id = apps.get(app_key)
            if target_app_id:
                c.execute("SELECT 1 FROM nbpl_identity_apps WHERE identity_id = ? AND application_id = ?", (ident_id, target_app_id))
                if not c.fetchone():
                    c.execute("""
                        INSERT INTO nbpl_identity_apps (identity_id, application_id, role, is_app_admin, granted_at, granted_by)
                        VALUES (?, ?, ?, 0, ?, ?)
                    """, (ident_id, target_app_id, default_role, now, "Excel Employee Import"))

    conn.commit()
    conn.close()
    return email_to_id

def sync_crm_database(db_path, db_name, commercial_accounts, email_to_identity_id, pwd_hash):
    print(f"\n--- Synchronizing CRM Database ({db_name}: {db_path}) ---")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    def has_column(table, col):
        c.execute(f"PRAGMA table_info('{table}')")
        return any(row[1] == col for row in c.fetchall())

    has_team_no = has_column('nbcm_teams', 'no')
    has_user_no = has_column('nbcm_users', 'no')

    # Purge test users
    c.execute("SELECT id FROM nbcm_users WHERE email LIKE '%@pharmacrm.test' OR email LIKE '%@getmeds.test'")
    test_uids = [r[0] for r in c.fetchall()]
    if test_uids:
        ph = ','.join('?' * len(test_uids))
        c.execute("SELECT id FROM nbcm_users WHERE LOWER(email) = 'ai4@getmeds.ph'")
        ai4_row = c.fetchone()
        ai4_id = ai4_row[0] if ai4_row else None
        if ai4_id:
            c.execute(f"UPDATE nbcm_companies SET owner_id = ? WHERE owner_id IN ({ph})", [ai4_id] + test_uids)
            c.execute(f"UPDATE nbcm_contacts SET owner_id = ? WHERE owner_id IN ({ph})", [ai4_id] + test_uids)
            c.execute(f"UPDATE nbcm_quotes SET owner_id = ? WHERE owner_id IN ({ph})", [ai4_id] + test_uids)
            c.execute(f"UPDATE nbcm_deals SET owner_id = ? WHERE owner_id IN ({ph})", [ai4_id] + test_uids)
        c.execute(f"DELETE FROM nbcm_sessions WHERE user_id IN ({ph})", test_uids)
        c.execute(f"DELETE FROM nbcm_trail_batches WHERE user_id IN ({ph})", test_uids)
        c.execute(f"DELETE FROM nbcm_users WHERE id IN ({ph})", test_uids)
        conn.commit()
        print(f"Purged {len(test_uids)} test users from {db_name}")

    # 1. Fetch roles & ensure Manager exists
    c.execute("SELECT name, id FROM nbcm_roles")
    roles = dict(c.fetchall())
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    if "Manager" not in roles:
        mgr_id = "ea444690-f50b-4d37-b4f8-9bbb431a7cfd"
        c.execute("INSERT INTO nbcm_roles (id, name, description, scope, is_system, created_at) VALUES (?, 'Manager', 'Oversees teams and their sales pipeline', 'managed', 0, ?)", (mgr_id, now))
        roles["Manager"] = mgr_id
    print("CRM Roles:", roles)

    # 2. Synchronize teams
    c.execute("SELECT name, id FROM nbcm_teams")
    teams = dict(c.fetchall())

    next_team_no = 40000001
    if has_team_no:
        c.execute("SELECT COALESCE(MAX(no), 40000000) FROM nbcm_teams")
        next_team_no = c.fetchone()[0] + 1

    for team_name, (mgr_email, desc, hq_list) in TEAMS_CONFIG.items():
        hq_json = json.dumps(hq_list)
        if team_name in teams:
            team_id = teams[team_name]
            c.execute("""
                UPDATE nbcm_teams
                SET description = ?, headquarters = ?, is_active = 1
                WHERE id = ?
            """, (desc, hq_json, team_id))
        else:
            team_id = str(uuid.uuid4())
            if has_team_no:
                c.execute("""
                    INSERT INTO nbcm_teams (id, no, name, description, headquarters, is_active, created_at, share_customers)
                    VALUES (?, ?, ?, ?, ?, 1, ?, 1)
                """, (team_id, next_team_no, team_name, desc, hq_json, now))
                next_team_no += 1
            else:
                c.execute("""
                    INSERT INTO nbcm_teams (id, name, description, headquarters, is_active, created_at, share_customers)
                    VALUES (?, ?, ?, ?, 1, ?, 1)
                """, (team_id, team_name, desc, hq_json, now))
            teams[team_name] = team_id
            print(f"Created CRM Team: {team_name} ({team_id})")

    conn.commit()

    # 3. Synchronize users
    c.execute("SELECT LOWER(email), id FROM nbcm_users")
    existing_users = dict(c.fetchall())

    next_user_no = 40000001
    if has_user_no:
        c.execute("SELECT COALESCE(MAX(no), 40000000) FROM nbcm_users")
        next_user_no = c.fetchone()[0] + 1

    created_users = 0
    updated_users = 0
    user_email_to_id = {}

    for email, comm in commercial_accounts.items():
        fn = comm['full_name']
        role_name = comm['role']
        role_id = roles.get(role_name, roles.get("Salesperson"))
        team_name = comm['team']
        team_id = teams.get(team_name)
        platform_ident_id = email_to_identity_id.get(email)

        if email in existing_users:
            u_id = existing_users[email]
            c.execute("""
                UPDATE nbcm_users
                SET full_name = ?, role_id = ?, team_id = ?, platform_identity_id = COALESCE(?, platform_identity_id), is_active = 1
                WHERE id = ?
            """, (fn, role_id, team_id, platform_ident_id, u_id))
            updated_users += 1
            user_email_to_id[email] = u_id
        else:
            u_id = str(uuid.uuid4())
            if has_user_no:
                c.execute("""
                    INSERT INTO nbcm_users (id, no, email, full_name, password_hash, is_active, created_at, password_changed_at, role_id, team_id, platform_identity_id)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """, (u_id, next_user_no, email, fn, pwd_hash, now, now, role_id, team_id, platform_ident_id))
                next_user_no += 1
            else:
                c.execute("""
                    INSERT INTO nbcm_users (id, email, full_name, password_hash, is_active, created_at, password_changed_at, role_id, team_id, platform_identity_id)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """, (u_id, email, fn, pwd_hash, now, now, role_id, team_id, platform_ident_id))
            created_users += 1
            user_email_to_id[email] = u_id

    conn.commit()
    print(f"CRM Users in {db_name}: {created_users} created, {updated_users} updated (Total: {len(user_email_to_id)})")

    # 4. Update team manager_ids
    for team_name, (mgr_email, _, _) in TEAMS_CONFIG.items():
        mgr_id = user_email_to_id.get(mgr_email)
        team_id = teams.get(team_name)
        if team_id and mgr_id:
            c.execute("UPDATE nbcm_teams SET manager_id = ? WHERE id = ?", (mgr_id, team_id))

    conn.commit()
    conn.close()
    return user_email_to_id

def sync_admin_db(all_employees, email_to_identity_id, pwd_hash):
    print("\n--- Synchronizing Executive Admin (admin.db) ---")
    conn = sqlite3.connect(ADMIN_DB)
    c = conn.cursor()

    c.execute("SELECT LOWER(email), id FROM nbad_users")
    existing_users = dict(c.fetchall())

    c.execute("SELECT name, id FROM nbad_roles")
    roles = dict(c.fetchall())
    print("Admin Roles:", roles)

    exec_role_id = roles.get("Executive Assistant", "00000000-0000-4000-8000-000000000002")
    admin_role_id = roles.get("Administrator", "00000000-0000-4000-8000-000000000001")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # Add Executive Management & Directors
    target_staff = [
        ("ea@getmeds.ph", "Mira Matias Verango", exec_role_id),
        ("ea2@getmeds.ph", "Jasmine Arbes Guatchin", exec_role_id),
        ("naresh@getmeds.ph", "Naresh Kumar Bishnoi", admin_role_id),
    ]

    for email, fn, r_id in target_staff:
        email = email.lower()
        plat_id = email_to_identity_id.get(email)
        if email in existing_users:
            u_id = existing_users[email]
            c.execute("""
                UPDATE nbad_users
                SET full_name = ?, role_id = ?, platform_identity_id = COALESCE(?, platform_identity_id), is_active = 1
                WHERE id = ?
            """, (fn, r_id, plat_id, u_id))
            print(f"Updated Admin user: {email} ({fn})")
        else:
            u_id = str(uuid.uuid4())
            c.execute("""
                INSERT INTO nbad_users (id, email, full_name, password_hash, role_id, is_active, created_at, password_changed_at, platform_identity_id)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (u_id, email, fn, pwd_hash, r_id, now, now, plat_id))
            print(f"Created Admin user: {email} ({fn})")

    conn.commit()
    conn.close()

def main():
    print("=================================================================")
    print("   BISHNOI ONE COMMERCIAL HIERARCHY & EMPLOYEE IMPORT PIPELINE   ")
    print("=================================================================")

    # 1. Backups
    make_backup(CRM_GETMEDS_DB)
    make_backup(CRM_DB)
    make_backup(PLATFORM_DB)
    make_backup(ADMIN_DB)

    # 2. Load data
    all_employees, employees_by_email, commercial_accounts = load_data()
    print(f"\nLoaded {len(all_employees)} employees from {os.path.basename(EMPLOYEES_XLSX)}")
    print(f"Resolved {len(commercial_accounts)} commercial hierarchy accounts from {os.path.basename(STRUCTURE_XLSX)}")

    pwd_hash = get_password_hash()

    # 3. Synchronize Platform DB
    email_to_identity_id = sync_platform_db(all_employees, commercial_accounts, pwd_hash)

    # 4. Synchronize CRM Tenant DB (crm-getmeds.db)
    sync_crm_database(CRM_GETMEDS_DB, "crm-getmeds.db", commercial_accounts, email_to_identity_id, pwd_hash)

    # 5. Synchronize CRM Default DB (crm.db)
    sync_crm_database(CRM_DB, "crm.db", commercial_accounts, email_to_identity_id, pwd_hash)

    # 6. Synchronize Admin DB (admin.db)
    sync_admin_db(all_employees, email_to_identity_id, pwd_hash)

    print("\n=================================================================")
    print("                   IMPORT COMPLETED SUCCESSFULLY                 ")
    print("=================================================================")

if __name__ == '__main__':
    main()
