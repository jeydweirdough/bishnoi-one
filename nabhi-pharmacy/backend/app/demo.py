"""The Pharmacy's demo accounts and records, for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), and
the sign-in page lists the accounts that exist here, so it only ever shows
accounts that can sign in to this app. Neither works in production.
"""

from dataclasses import dataclass

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # as the sign-in page describes them
    access: str  # the role they're given here
    license_no: str | None = None


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Pharmacist", "ruth@pharmacrm.test", "Ruth Sarmiento", "Pharmacist · checks, verifies and dispenses", "Pharmacist", "PRC-0048213"),
    Demo("Pharmacy Assistant", "migs@pharmacrm.test", "Miguel Santos", "Pharmacy Assistant · takes prescriptions in, sells", "Pharmacy Assistant"),
    Demo("Administrator", "tess@pharmacrm.test", "Tess Villanueva", "Administrator · users, roles, everything", "Administrator", "PRC-0031977"),
)

DEMO_CATEGORIES = ("Antibiotics", "Analgesics", "Antihypertensives", "Antidiabetics", "Vitamins & supplements", "Cough & cold")

# name, manufacturer
DEMO_BRANDS = (
    ("Amoxil", "GSK"),
    ("Biogesic", "Unilab"),
    ("Norvasc", "Pfizer"),
    ("Glucophage", "Merck"),
    ("Enervon", "Unilab"),
    ("Solmux", "Unilab"),
    ("RiteMED", "RiteMED"),
)

# code, generic, brand, category, strength, form, unit, rx_class, pesos, reorder
DEMO_MEDICINES = (
    ("AMX500", "Amoxicillin", "Amoxil", "Antibiotics", "500 mg", "capsule", "capsule", "rx", 12.50, 100),
    ("AMX250S", "Amoxicillin", "RiteMED", "Antibiotics", "250 mg/5 mL", "suspension", "bottle", "rx", 95.00, 10),
    ("CEF500", "Cefalexin", "RiteMED", "Antibiotics", "500 mg", "capsule", "capsule", "rx", 9.75, 60),
    ("PCM500", "Paracetamol", "Biogesic", "Analgesics", "500 mg", "tablet", "tablet", "otc", 4.50, 200),
    ("IBU400", "Ibuprofen", "RiteMED", "Analgesics", "400 mg", "tablet", "tablet", "otc", 6.00, 100),
    ("TRA50", "Tramadol", "RiteMED", "Analgesics", "50 mg", "capsule", "capsule", "dangerous", 18.00, 30),
    ("AML5", "Amlodipine", "Norvasc", "Antihypertensives", "5 mg", "tablet", "tablet", "rx", 32.00, 90),
    ("LOS50", "Losartan", "RiteMED", "Antihypertensives", "50 mg", "tablet", "tablet", "rx", 11.00, 90),
    ("MET500", "Metformin", "Glucophage", "Antidiabetics", "500 mg", "tablet", "tablet", "rx", 8.25, 120),
    ("VITB", "Vitamin B complex", "Enervon", "Vitamins & supplements", None, "tablet", "tablet", "otc", 7.50, 100),
    ("CARB500", "Carbocisteine", "Solmux", "Cough & cold", "500 mg", "capsule", "capsule", "otc", 9.00, 80),
)

# name, contact, phone, email
DEMO_SUPPLIERS = (
    ("Zuellig Pharma", "Carlo Mendoza", "+63 2 8908 2222", "orders@zuellig.test"),
    ("Metro Drug", "Ana Lim", "+63 2 8411 5000", "sales@metrodrug.test"),
)

# code, lot, supplier, days to expiry, quantity, cost in pesos. Some expire
# soon, one already has, and one medicine runs low, so every list has something.
DEMO_BATCHES = (
    ("AMX500", "AMX-24A11", "Zuellig Pharma", 420, 300, 7.10),
    ("AMX500", "AMX-23K02", "Zuellig Pharma", 40, 60, 6.90),
    ("AMX250S", "AMXS-2407", "Metro Drug", 300, 24, 61.00),
    ("CEF500", "CEF-2405", "Metro Drug", 260, 150, 5.40),
    ("PCM500", "BG-240912", "Metro Drug", 700, 1000, 2.20),
    ("PCM500", "BG-230301", "Metro Drug", -12, 40, 2.05),
    ("IBU400", "IBU-2406", "Metro Drug", 520, 250, 3.10),
    ("TRA50", "TRA-2402", "Zuellig Pharma", 380, 60, 11.00),
    ("AML5", "NV-24B19", "Zuellig Pharma", 610, 180, 19.50),
    ("LOS50", "LOS-2311", "Metro Drug", 75, 40, 6.20),
    ("MET500", "GL-2404", "Zuellig Pharma", 480, 400, 4.60),
    ("VITB", "ENV-2408", "Metro Drug", 540, 300, 4.10),
    ("CARB500", "SLX-2403", "Metro Drug", 25, 90, 5.30),
)

# name, kind, birth date, sex, phone, allergies
DEMO_PATIENTS = (
    ("Juan Dela Cruz", "patient", "1968-03-14", "male", "+63 917 555 0101", None),
    ("Maria Clara Reyes", "patient", "1990-11-02", "female", "+63 918 555 0142", "Penicillin"),
    ("Roberto Aquino", "patient", "1955-07-21", "male", "+63 919 555 0177", None),
    ("Liza Manalo", "customer", None, "female", "+63 920 555 0188", None),
)

# patient, prescriber, licence, clinic, days ago, status, [(written as, code, qty, directions)]
DEMO_PRESCRIPTIONS = (
    ("Juan Dela Cruz", "Dr. Elena Ramos", "PRC-0112233", "Manila Doctors Clinic", 1, "received",
     [("Amoxicillin 500mg cap", "AMX500", 21, "1 capsule 3x a day for 7 days")]),
    ("Roberto Aquino", "Dr. Paolo Garcia", "PRC-0098765", "St. Luke's QC", 2, "pending",
     [("Amlodipine 5mg", "AML5", 30, "1 tablet once a day"), ("Metformin 500mg", "MET500", 60, "1 tablet twice a day after meals")]),
    ("Maria Clara Reyes", "Dr. Elena Ramos", "PRC-0112233", "Manila Doctors Clinic", 3, "needs_clarification",
     [("Amoxicillin 500mg", "AMX500", 21, "1 capsule 3x a day")]),
    ("Roberto Aquino", "Dr. Paolo Garcia", "PRC-0098765", "St. Luke's QC", 5, "verified",
     [("Losartan 50mg", "LOS50", 30, "1 tablet once a day")]),
)
