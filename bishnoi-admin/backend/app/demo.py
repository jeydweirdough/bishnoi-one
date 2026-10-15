"""This app's demo accounts and corporate demo records for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), and
the sign-in page lists the ones that exist here, so it only ever shows
accounts that can sign in to this app. Neither works in production.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.executive import safe_tz, sync_notifications
from app.models import (
    ComplianceRecord,
    CorporateDocument,
    ImmigrationRecord,
    PropertyRecord,
    Ticket,
    TicketUpdate,
    User,
    new_id,
    utcnow,
)
from app.permissions import (
    ADMINISTRATOR,
    AUDITOR,
    COMPLIANCE_OFFICER,
    EXECUTIVE_ASSISTANT,
    MARKETING_ASSISTANT,
    ROLE_ADMIN_ID,
    ROLE_AUDITOR_ID,
    ROLE_COMPLIANCE_ID,
    ROLE_EXEC_ASST_ID,
    ROLE_MARKETING_ID,
)
from app.security import hash_password

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # what the sign-in page shows: "<role> · <what they do>"
    role_id: str

    @property
    def admin(self) -> bool:
        return self.role_id == ROLE_ADMIN_ID


# One of every starting role (app/permissions.py), so each can be tried.
DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Executive Office", "deo@pharmacrm.test", "Deo Castillo", f"{EXECUTIVE_ASSISTANT} · permits, leases, tickets day to day", ROLE_EXEC_ASST_ID),
    Demo("Executive Office", "mila@pharmacrm.test", "Mila Aguilar", f"{EXECUTIVE_ASSISTANT} · expatriate visas and VIP logistics", ROLE_EXEC_ASST_ID),
    Demo("Executive Office", "teresa@pharmacrm.test", "Teresa Abad", f"{COMPLIANCE_OFFICER} · BOC, FDA, SEC, BIR, LGU, visas, contracts", ROLE_COMPLIANCE_ID),
    Demo("Executive Office", "ramon@pharmacrm.test", "Ramon Santos", f"{AUDITOR} · everything and the activity log, read-only", ROLE_AUDITOR_ID),
    Demo("Marketing", "bea@pharmacrm.test", "Bea Navarro", f"{MARKETING_ASSISTANT} · promotional materials, from design to giving out", ROLE_MARKETING_ID),
    Demo("Administration", "carmen@pharmacrm.test", "Carmen Villanueva", f"{ADMINISTRATOR} · every setting, users and roles", ROLE_ADMIN_ID),
)


def seed_demo_data(db: Session, settings: Settings) -> None:
    """Seeds realistic Philippine corporate pharma records if tables are empty."""
    tz = safe_tz(settings.org_timezone)
    now = datetime.now(tz)

    def days_from_now(days: int) -> datetime:
        target = now + timedelta(days=days)
        return target.astimezone(UTC)

    # 1. Compliance & Permits
    if db.scalar(select(func.count(ComplianceRecord.id))) == 0:
        permits = [
            ComplianceRecord(
                id=new_id(),
                title="BOC CPRS Importer Accreditation",
                category="boc",
                agency="Bureau of Customs (BOC)",
                reference_number="BOC-CPRS-IMP-2025-08492",
                issuance_date=days_from_now(-337),
                expiration_date=days_from_now(28),  # Approaching (28 days left)
                renewal_window_days=60,
                status="active",
                responsible_person="Deo Castillo",
                estimated_cost=15000.0,
                notes="Customs broker accreditation renewal required before CPRS profile updates.",
            ),
            ComplianceRecord(
                id=new_id(),
                title="Makati City Mayor's Permit & Business License",
                category="lgu",
                agency="City Government of Makati",
                reference_number="BP-2025-MKT-094182",
                issuance_date=days_from_now(-353),
                expiration_date=days_from_now(12),  # Urgent (12 days left)
                renewal_window_days=45,
                status="pending_renewal",
                responsible_person="Mila Aguilar",
                estimated_cost=85000.0,
                notes="LGU assessment received. Sanitary and FSIC inspection cleared.",
            ),
            ComplianceRecord(
                id=new_id(),
                title="SEC Annual General Information Sheet (GIS)",
                category="sec",
                agency="Securities and Exchange Commission (SEC)",
                reference_number="SEC-GIS-CS2020-09384",
                issuance_date=days_from_now(-347),
                expiration_date=days_from_now(18),  # Urgent (18 days left)
                renewal_window_days=30,
                status="under_review",
                responsible_person="Carmen Villanueva",
                estimated_cost=5000.0,
                notes="Board meeting scheduled for signing by Corporate Secretary and President.",
            ),
            ComplianceRecord(
                id=new_id(),
                title="FDA License to Operate (LTO) — Drug Wholesaler/Distributor",
                category="fda",
                agency="Food and Drug Administration (FDA)",
                reference_number="FDA-CDRR-LTO-0049281",
                issuance_date=days_from_now(-655),
                expiration_date=days_from_now(75),  # Upcoming (75 days left)
                renewal_window_days=90,
                status="active",
                responsible_person="Deo Castillo",
                estimated_cost=42000.0,
                notes="Supervising Pharmacist documentation submitted; awaiting final online portal validation.",
            ),
            ComplianceRecord(
                id=new_id(),
                title="BIR Annual Registration Renewal (Form 0605 / 2303)",
                category="bir",
                agency="Bureau of Internal Revenue (BIR RDO 047)",
                reference_number="BIR-TIN-009-847-291-000",
                issuance_date=days_from_now(-250),
                expiration_date=days_from_now(115),  # Good standing (115 days left)
                renewal_window_days=30,
                status="active",
                responsible_person="Carmen Villanueva",
                estimated_cost=500.0,
                notes="Annual registration tax due by January 31.",
            ),
            ComplianceRecord(
                id=new_id(),
                title="Bureau of Fire Protection (FSIC) — Taguig Warehouse",
                category="sanitary_fire",
                agency="Bureau of Fire Protection (BFP Taguig)",
                reference_number="FSIC-TG-2025-00412",
                issuance_date=days_from_now(-368),
                expiration_date=days_from_now(-3),  # OVERDUE (-3 days!)
                renewal_window_days=30,
                status="pending_renewal",
                responsible_person="Deo Castillo",
                estimated_cost=12500.0,
                notes="Urgent re-inspection fee paid at BFP station. Waiting for certificate release.",
            ),
        ]
        db.add_all(permits)

    # 2. Expatriate & Immigration Compliance
    if db.scalar(select(func.count(ImmigrationRecord.id))) == 0:
        immigs = [
            ImmigrationRecord(
                id=new_id(),
                individual_name="Dr. Alistair Finch",
                designation="Managing Director - Southeast Asia",
                nationality="British",
                document_type="acr_card",
                document_number="ACR-F0000984712",
                issuance_date=days_from_now(-351),
                expiration_date=days_from_now(14),  # Urgent (14 days left)
                renewal_lead_days=60,
                sponsoring_entity="Bishnoi One Pharma Philippines Inc.",
                status="expiring_soon",
                assigned_assistant="Mila Aguilar",
                notes="Bureau of Immigration annual report and biometric re-validation appointment scheduled.",
            ),
            ImmigrationRecord(
                id=new_id(),
                individual_name="Dr. Alistair Finch",
                designation="Managing Director - Southeast Asia",
                nationality="British",
                document_type="visa",
                document_number="9G-COMM-2024-00192",
                issuance_date=days_from_now(-685),
                expiration_date=days_from_now(45),  # Upcoming (45 days left)
                renewal_lead_days=90,
                sponsoring_entity="Bishnoi One Pharma Philippines Inc.",
                status="in_renewal",
                assigned_assistant="Mila Aguilar",
                notes="Petition for 9(g) visa extension filed with immigration legal counsel.",
            ),
            ImmigrationRecord(
                id=new_id(),
                individual_name="Rajesh Subramanian",
                designation="VP of Supply Chain & Formulations",
                nationality="Indian",
                document_type="aep_permit",
                document_number="DOLE-NCR-AEP-2024-4910",
                issuance_date=days_from_now(-327),
                expiration_date=days_from_now(38),  # Approaching (38 days left)
                renewal_lead_days=60,
                sponsoring_entity="Bishnoi One Pharma Philippines Inc.",
                status="valid",
                assigned_assistant="Teresa Abad",
                notes="DOLE newspaper publication of vacancy completed. Filing application at DOLE NCR.",
            ),
            ImmigrationRecord(
                id=new_id(),
                individual_name="Claire Dubois",
                designation="Director of Clinical In-Licensing",
                nationality="French",
                document_type="passport",
                document_number="21FRA94819",
                issuance_date=days_from_now(-3200),
                expiration_date=days_from_now(8),  # Critical / Urgent (8 days left)
                renewal_lead_days=90,
                sponsoring_entity="Bishnoi One Pharma Philippines Inc.",
                status="expiring_soon",
                assigned_assistant="Deo Castillo",
                notes="French Embassy Manila appointment confirmed. Urgent renewal needed for outbound corporate travel.",
            ),
        ]
        db.add_all(immigs)

    # 3. Corporate Documents & Insurances
    if db.scalar(select(func.count(CorporateDocument.id))) == 0:
        docs = [
            CorporateDocument(
                id=new_id(),
                title="Directors & Officers (D&O) Liability Insurance Policy",
                category="insurance",
                counterparty="Malayan Insurance Co., Inc.",
                reference_number="POL-DO-2025-00941",
                effective_date=days_from_now(-344),
                expiration_date=days_from_now(21),  # Urgent (21 days left)
                auto_renews=False,
                notice_period_days=30,
                custodian="Carmen Villanueva",
                status="in_review",
                annual_value=350000.0,
                notes="Broker proposal submitted with updated executive coverage limits.",
            ),
            CorporateDocument(
                id=new_id(),
                title="Master Commercial Warehousing & Third-Party Logistics Agreement",
                category="commercial_contract",
                counterparty="Metro Logistics Solutions Corp.",
                reference_number="AGR-3PL-2023-004",
                effective_date=days_from_now(-1040),
                expiration_date=days_from_now(55),  # Upcoming (55 days left)
                auto_renews=True,
                notice_period_days=60,
                custodian="Deo Castillo",
                status="active",
                annual_value=1200000.0,
                notes="60 days prior written notice required to prevent automated 12-month rollover.",
            ),
            CorporateDocument(
                id=new_id(),
                title="External Legal Counsel & Corporate Secretarial Retainer",
                category="legal_retainer",
                counterparty="SyCip Salazar Hernandez & Gatmaitan",
                reference_number="RET-LAW-2024-012",
                effective_date=days_from_now(-300),
                expiration_date=days_from_now(65),
                auto_renews=True,
                notice_period_days=30,
                custodian="Carmen Villanueva",
                status="active",
                annual_value=600000.0,
                notes="Monthly retainer covering corporate secretarial, SEC compliance, and contract review.",
            ),
        ]
        db.add_all(docs)

    # 4. Properties & Facilities
    if db.scalar(select(func.count(PropertyRecord.id))) == 0:
        props = [
            PropertyRecord(
                id=new_id(),
                name="Bishnoi One Corporate Headquarters — Ayala Triangle Tower One",
                property_type="office",
                address="24th Floor, Tower One & Exchange Plaza, Ayala Ave, Makati City",
                lessor_name="Ayala Land Offices Inc.",
                lessor_contact="Property Mgr: Ms. Bea Alonzo (02-8848-1000 / offices@ayalaland.com.ph)",
                lease_start=days_from_now(-1053),
                lease_end=days_from_now(42),  # Approaching (42 days left)
                notice_deadline_days=60,
                monthly_rent=385000.0,
                escalation_rate_pct=5.0,
                security_deposit=1155000.0,
                utilities_info="Meralco Account: 2049182019; Manila Water: 0948192; Globe Fiber 1Gbps Leased Line: 84920192; Building Dues: P35,000/mo",
                status="renewal_negotiation",
                assigned_manager="Deo Castillo",
                notes="Drafting renewal addendum for additional 3-year term with 5% escalation cap.",
            ),
            PropertyRecord(
                id=new_id(),
                name="Taguig Central Pharma Distribution Warehouse",
                property_type="warehouse",
                address="Building 4, FTI Special Economic Zone, Taguig City, Metro Manila",
                lessor_name="First Taguig Industrial Park Corp.",
                lessor_contact="Engr. Robert Tan (0917-555-8492 / rtan@ftipark.ph)",
                lease_start=days_from_now(-940),
                lease_end=days_from_now(125),  # Good standing (125 days left, notice deadline in 35 days)
                notice_deadline_days=90,
                monthly_rent=520000.0,
                escalation_rate_pct=4.0,
                security_deposit=1560000.0,
                utilities_info="Meralco Industrial Meter: 948102948; Sub-metered Water: Taguig Utilities; Back-up Generator 250kVA contract",
                status="active",
                assigned_manager="Deo Castillo",
                notes="Notice of intent to renew required 90 days before contract termination.",
            ),
        ]
        db.add_all(props)

    # 5. Office Concerns & Service Desk Tickets
    if db.scalar(select(func.count(Ticket.id))) == 0:
        tickets = [
            Ticket(
                id=new_id(),
                ticket_number="EX-2026-0001",
                title="Boardroom A HVAC Inverter Malfunction prior to Board Meeting",
                category="facilities",
                priority="urgent",
                status="in_progress",
                requester_name="Carmen Villanueva",
                requester_email="carmen@pharmacrm.test",
                executive_sponsor="CEO Office",
                assigned_to="Deo Castillo",
                sla_due_date=days_from_now(1),  # SLA in 24 hours
                description="The ceiling duct air conditioning in Main Boardroom A is leaking condensation and failing to cool. Need emergency technician before tomorrow's board session.",
                resolution_notes="Carrier certified technician scheduled for 1:30 PM inspection today.",
            ),
            Ticket(
                id=new_id(),
                ticket_number="EX-2026-0002",
                title="VIP Airport Protocol & Chauffeur Transfer for APAC Regional Director",
                category="vip_logistics",
                priority="high",
                status="open",
                requester_name="Mila Aguilar",
                requester_email="mila@pharmacrm.test",
                executive_sponsor="Managing Director",
                assigned_to="Deo Castillo",
                sla_due_date=days_from_now(2),  # SLA in 48 hours
                description="Flight SQ 918 arriving NAIA Terminal 3 on Friday 18:45. Arrange executive van, expedited immigration tarmac liaison, and transfer to Makati Shangri-La.",
                resolution_notes=None,
            ),
            Ticket(
                id=new_id(),
                ticket_number="EX-2026-0003",
                title="Emergency Courier Liaison Dispatch — Bureau of Customs Submissions",
                category="courier_dispatch",
                priority="urgent",
                status="open",
                requester_name="Deo Castillo",
                requester_email="deo@pharmacrm.test",
                executive_sponsor="Executive Admin",
                assigned_to="Deo Castillo",
                sla_due_date=days_from_now(1),
                description="Physical submission of notarized Board Resolution and Secretary's Certificate to BOC Assessment Office Port of Manila before 3:00 PM cutoff.",
                resolution_notes=None,
            ),
        ]
        db.add_all(tickets)

    db.commit()
    sync_notifications(db, settings)
