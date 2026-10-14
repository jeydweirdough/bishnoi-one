"""The CRM's demo accounts, for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), with
their role and team, and makes the teams they're in. The sign-in page lists
the ones that exist here, so it only ever shows accounts that can sign in to
Sales. Neither works in production.
"""

from dataclasses import dataclass

DEMO_PASSWORD = "demo1234"

# Demo teams that were renamed or split: old name -> the name it goes on as.
# "STC, URO" was one team; STC and URO are different, so URO is made anew.
RENAMED_TEAMS = {"STC, URO": "STC"}


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # what the sign-in page says they are
    access: str  # the role they're given (app/permissions.py)
    team: str | None = None
    # A manager's divisions: they're made those teams' manager (Manager reaches every team it manages).
    manages: tuple[str, ...] = ()


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Administration", "carmen@pharmacrm.test", "Carmen Villanueva", "Admin · users, roles, teams and the audit log", "Administrator"),
    Demo("Management", "mia@pharmacrm.test", "Mia Santos", "Manager · B2C and B2B divisions: approves their quotes, sets their targets", "Manager", "B2C", ("B2C", "B2B")),
    Demo("Sales · B2C", "ben@pharmacrm.test", "Ben Cruz", "Salesperson · B2C MD Telesales", "Salesperson", "B2C"),
    Demo("Sales · B2C", "tess@pharmacrm.test", "Tess Aquino", "Team Lead · B2C General", "Team Lead", "B2C"),
    Demo("Sales · STC", "nena@pharmacrm.test", "Nena Gutierrez", "Salesperson · STC MD Telesales", "Salesperson", "STC"),
    Demo("Sales · URO", "rico@pharmacrm.test", "Rico Padilla", "Salesperson · URO MD Telesales", "Salesperson", "URO"),
    Demo("Sales · B&B", "ana@pharmacrm.test", "Ana Reyes", "Salesperson · B&B MD Telesales + B2C General", "Salesperson", "B&B"),
    Demo("Sales · B&B", "paolo@pharmacrm.test", "Paolo Mendoza", "Team Lead · B&B MD Telesales", "Team Lead", "B&B"),
    Demo("Sales · B&B", "lorna@pharmacrm.test", "Lorna Bautista", "Team Lead · B&B division head", "Team Lead", "B&B"),
    Demo("Sales · B2B", "marlon@pharmacrm.test", "Marlon Yap", "Salesperson · B2B NBD", "Salesperson", "B2B"),
    Demo("Sales · B2B", "dina@pharmacrm.test", "Dina Salazar", "Salesperson · B2B CRR", "Salesperson", "B2B"),
    Demo("Sales · B2B", "noel@pharmacrm.test", "Noel Ramos", "Team Lead · B2B division head", "Team Lead", "B2B"),
    Demo("Sales · HOS", "grace@pharmacrm.test", "Grace Lim", "Salesperson · HOS Hospital", "Salesperson", "HOS"),
    Demo("Sales · HOS", "elmer@pharmacrm.test", "Elmer Tan", "Salesperson · HOS Telesales", "Salesperson", "HOS"),
    Demo("Sales · HOS", "vicky@pharmacrm.test", "Vicky Ong", "Team Lead · HOS Hospital", "Team Lead", "HOS"),
    Demo("Sales · BID", "rosa@pharmacrm.test", "Rosa Ferrer", "Salesperson · BID Bidding", "Salesperson", "BID"),
    Demo("Field · B2C", "fay@pharmacrm.test", "Fay Dizon", "Field agent · visits doctors and collects", "Field agent", "B2C"),
    Demo("Field · B2C", "gil@pharmacrm.test", "Gil Navarro", "Field agent · visits doctors and collects", "Field agent", "B2C"),
)


# Sample customers, made with the demo accounts (only when there are none yet).
# owner email, name, status, industry, city, phone, email
DEMO_COMPANIES: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("ben@pharmacrm.test", "St. Luke's Family Clinic", "customer", "Clinic", "Quezon City", "02 8723 0101", "frontdesk@stlukesfamily.test"),
    ("ben@pharmacrm.test", "Mabuhay Drugstore", "prospect", "Retail pharmacy", "Pasig", "02 8631 2210", "orders@mabuhaydrug.test"),
    ("tess@pharmacrm.test", "Healthway Medical", "customer", "Hospital group", "Makati", "02 8858 4400", "procurement@healthway.test"),
    ("ana@pharmacrm.test", "Riverside Medical Center", "customer", "Hospital", "Parañaque", "02 8820 7000", "pharmacy@riverside.test"),
    ("ana@pharmacrm.test", "Bayview Pediatrics", "prospect", "Clinic", "Pasay", "02 8551 3322", "hello@bayviewpeds.test"),
    ("marlon@pharmacrm.test", "Northstar Distribution", "partner", "Distributor", "Caloocan", "02 8362 9900", "trade@northstar.test"),
    ("dina@pharmacrm.test", "Cebu Doctors' Pharmacy", "customer", "Retail pharmacy", "Cebu City", "032 255 5555", "buying@cebudocs.test"),
    ("grace@pharmacrm.test", "Manila Central Hospital", "customer", "Hospital", "Manila", "02 8711 1000", "supply@mch.test"),
    ("elmer@pharmacrm.test", "Davao Care Hospital", "prospect", "Hospital", "Davao City", "082 300 1234", "info@davaocare.test"),
    ("rosa@pharmacrm.test", "Department of Health – Region IV-A", "prospect", "Government", "Calamba", "049 545 0000", "bids@doh4a.test"),
)

# company, first name, last name, job title, email, phone
DEMO_CONTACTS: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("St. Luke's Family Clinic", "Alma", "Dizon", "Head of Pediatrics", "alma.dizon@stlukesfamily.test", "0917 555 0101"),
    ("St. Luke's Family Clinic", "Victor", "Salcedo", "Clinic Manager", "victor@stlukesfamily.test", "0917 555 0102"),
    ("Mabuhay Drugstore", "Joy", "Lim", "Owner", "joy@mabuhaydrug.test", "0918 222 3344"),
    ("Healthway Medical", "Paolo", "Reyes", "Procurement Lead", "p.reyes@healthway.test", "0917 800 1200"),
    ("Riverside Medical Center", "Carla", "Mendoza", "Chief Pharmacist", "carla@riverside.test", "0917 333 7788"),
    ("Riverside Medical Center", "Ramon", "Cruz", "Purchasing Officer", "ramon.cruz@riverside.test", "0917 333 7789"),
    ("Bayview Pediatrics", "Liza", "Tan", "Pediatrician", "liza@bayviewpeds.test", "0919 123 4567"),
    ("Northstar Distribution", "Edwin", "Go", "Trade Manager", "edwin.go@northstar.test", "0917 999 1010"),
    ("Cebu Doctors' Pharmacy", "Maricel", "Uy", "Store Manager", "maricel@cebudocs.test", "0922 456 7890"),
    ("Manila Central Hospital", "Jose", "Villareal", "Medical Director", "jvillareal@mch.test", "0917 121 3434"),
    ("Davao Care Hospital", "Nina", "Lopez", "Supply Chain Head", "nina.lopez@davaocare.test", "0918 765 4321"),
    ("Department of Health – Region IV-A", "Arturo", "Santos", "BAC Secretariat", "bac@doh4a.test", "049 545 0011"),
)

# company, contact first name (or None), kind, subject, days from now (negative: past), done
DEMO_ACTIVITIES: tuple[tuple[str, str | None, str, str, int, bool], ...] = (
    ("St. Luke's Family Clinic", "Alma", "call", "Talked about the new pediatric syrup; wants samples", -6, True),
    ("St. Luke's Family Clinic", "Alma", "task", "Drop off syrup samples", -1, False),
    ("St. Luke's Family Clinic", "Victor", "email", "Sent the updated price list", -3, True),
    ("Mabuhay Drugstore", "Joy", "meeting", "Store visit: shelf space for the OTC line", 0, False),
    ("Mabuhay Drugstore", None, "note", "Pays within 30 days; prefers weekday deliveries", -10, True),
    ("Healthway Medical", "Paolo", "meeting", "Quarterly review with procurement", 2, False),
    ("Healthway Medical", "Paolo", "call", "Confirmed Q4 volumes", -2, True),
    ("Riverside Medical Center", "Carla", "task", "Send the formulary application", 1, False),
    ("Riverside Medical Center", "Ramon", "email", "Answered questions on delivery lead times", -4, True),
    ("Riverside Medical Center", None, "meeting", "P&T committee presentation", -8, True),
    ("Bayview Pediatrics", "Liza", "call", "First call: interested in the vaccines line", -1, True),
    ("Bayview Pediatrics", "Liza", "task", "Book a demo with Dr. Tan", 3, False),
    ("Northstar Distribution", "Edwin", "meeting", "Renew distribution terms", 5, False),
    ("Cebu Doctors' Pharmacy", "Maricel", "task", "Chase the unpaid invoice", -3, False),
    ("Cebu Doctors' Pharmacy", "Maricel", "call", "Restock order for antibiotics", -5, True),
    ("Manila Central Hospital", "Jose", "meeting", "Tender briefing", 0, False),
    ("Davao Care Hospital", "Nina", "email", "Introduced the company and product range", -2, True),
    ("Davao Care Hospital", "Nina", "task", "Follow up on the introduction email", 4, False),
    ("Department of Health – Region IV-A", "Arturo", "task", "Prepare bid documents", 6, False),
    ("Department of Health – Region IV-A", None, "note", "Bid opening moved to next month", -7, True),
)


# The catalogue quotes are priced from (only when there are no products yet).
# code, name, entry, rule, requires notes, needs approval
DEMO_PRICE_TYPES: tuple[tuple[str, str, str, str, bool, bool], ...] = (
    ("PATIENT", "Patient Price", "list", "always", False, False),
    ("TRADE", "Drugstore/Hospital Price", "list", "always", False, False),
    ("DOCTOR", "Doctor's Price", "list", "with_rx", False, False),
    ("SPECIAL", "Requested price", "entered", "always", True, True),
    # Finance's own: a product with no approved SRP can't be quoted (app/pricing.py).
    ("SRP", "SRP", "list", "always", False, False),
)

# code, name
DEMO_ISSUERS: tuple[tuple[str, str], ...] = (("DSWD", "DSWD"), ("PCSO", "PCSO"), ("MAYOR", "Office of the Mayor"), ("OP", "Office of the President"))

# code, name, generic name, strength, form, unit, prices in pesos (PATIENT, TRADE, DOCTOR)
DEMO_PRODUCTS: tuple[tuple[str, str, str, str, str, str, tuple[int, int, int]], ...] = (
    ("AMX-500", "Amoxil", "Amoxicillin", "500 mg", "Capsule", "box of 100", (1450, 1180, 1300)),
    ("CTZ-10", "Cetrin", "Cetirizine", "10 mg", "Tablet", "box of 100", (980, 760, 870)),
    ("PCM-SYR", "Tempra Syrup", "Paracetamol", "250 mg/5 mL", "Syrup", "bottle 60 mL", (165, 128, 150)),
    ("MTF-500", "Glucophage", "Metformin", "500 mg", "Tablet", "box of 100", (1250, 990, 1120)),
    ("ALP-5", "Norvasc", "Amlodipine", "5 mg", "Tablet", "box of 30", (1890, 1520, 1700)),
    ("OMP-20", "Losec", "Omeprazole", "20 mg", "Capsule", "box of 30", (1320, 1050, 1190)),
    ("ORS-SACH", "Hydrite", "Oral rehydration salts", "", "Sachet", "box of 25", (310, 240, 280)),
    ("VTC-500", "Poten-Cee", "Ascorbic acid", "500 mg", "Tablet", "box of 100", (720, 560, 650)),
)

# name, kind, terms, product codes (None: every product)
DEMO_PROMOS: tuple[tuple[str, str, dict, tuple[str, ...] | None], ...] = (
    ("Flu season 10% off", "percent", {"percent_bp": 1000}, ("CTZ-10", "PCM-SYR", "VTC-500")),
    ("Buy 10, get 1", "free_goods", {"buy_qty": 10, "free_qty": 1}, ("AMX-500", "OMP-20")),
    ("Volume discount", "tiered", {"tiers": [{"minQty": 20, "percentBp": 300}, {"minQty": 50, "percentBp": 500}]}, None),
)

# code, name, set price in pesos, as one line, (product code, qty)...
DEMO_BUNDLES: tuple[tuple[str, str, int, bool, tuple[tuple[str, int], ...]], ...] = (
    ("KIDS-KIT", "Pedia fever kit", 900, True, (("PCM-SYR", 4), ("ORS-SACH", 1))),
    ("MAINT-3", "Maintenance trio", 4200, False, (("MTF-500", 1), ("ALP-5", 1), ("OMP-20", 1))),
)

# The divisions each demo promo (by name) and bundle (by code) is for. A B2C
# promo is B2C's alone: B2B, HOS and the rest never see it.
DEMO_DIVISIONS: dict[str, tuple[str, ...]] = {
    "Flu season 10% off": ("B2C", "B&B"),
    "Buy 10, get 1": ("HOS",),
    "Volume discount": ("B2B", "BID"),
    "KIDS-KIT": ("B2C",),
    "MAINT-3": ("B2B", "HOS"),
}
