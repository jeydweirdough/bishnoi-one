"""Sales' demo accounts, for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), with
their role and team, and makes the teams they're in. The sign-in page lists
the ones that exist here, so it only ever shows accounts that can sign in to
Sales. Neither works in production.
"""

from dataclasses import dataclass

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # what the sign-in page says they are
    access: str  # the role they're given (app/permissions.py)
    team: str | None = None


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Administration", "carmen@pharmacrm.test", "Carmen Villanueva", "Admin · users, roles, teams and the audit log", "Administrator"),
    Demo("Sales · B2C", "ben@pharmacrm.test", "Ben Cruz", "Rep · B2C MD Telesales", "Sales Rep", "B2C"),
    Demo("Sales · B2C", "tess@pharmacrm.test", "Tess Aquino", "Team Lead · B2C General", "Team Lead", "B2C"),
    Demo("Sales · STC, URO", "nena@pharmacrm.test", "Nena Gutierrez", "Rep · STC MD Telesales", "Sales Rep", "STC, URO"),
    Demo("Sales · STC, URO", "rico@pharmacrm.test", "Rico Padilla", "Rep · URO MD Telesales", "Sales Rep", "STC, URO"),
    Demo("Sales · B&B", "ana@pharmacrm.test", "Ana Reyes", "Rep · B&B MD Telesales + B2C General", "Sales Rep", "B&B"),
    Demo("Sales · B&B", "paolo@pharmacrm.test", "Paolo Mendoza", "Team Lead · B&B MD Telesales", "Team Lead", "B&B"),
    Demo("Sales · B&B", "lorna@pharmacrm.test", "Lorna Bautista", "Division Head · B&B", "Manager", "B&B"),
    Demo("Sales · B2B", "marlon@pharmacrm.test", "Marlon Yap", "Rep · B2B NBD", "Sales Rep", "B2B"),
    Demo("Sales · B2B", "dina@pharmacrm.test", "Dina Salazar", "Rep · B2B CRR", "Sales Rep", "B2B"),
    Demo("Sales · B2B", "noel@pharmacrm.test", "Noel Ramos", "Division Head · B2B", "Manager", "B2B"),
    Demo("Sales · HOS", "grace@pharmacrm.test", "Grace Lim", "Rep · HOS Hospital", "Sales Rep", "HOS"),
    Demo("Sales · HOS", "elmer@pharmacrm.test", "Elmer Tan", "Rep · HOS Telesales", "Sales Rep", "HOS"),
    Demo("Sales · HOS", "vicky@pharmacrm.test", "Vicky Ong", "Team Lead · HOS Hospital", "Team Lead", "HOS"),
    Demo("Sales · BID", "rosa@pharmacrm.test", "Rosa Ferrer", "Rep · BID Bidding", "Sales Rep", "BID"),
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
