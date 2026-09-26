"use client";

import { X } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  saveDocument,
  saveImmigration,
  savePermit,
  saveProperty,
  saveTicket,
  addTicketUpdate,
} from "@/src/actions/executive";
import type {
  ComplianceRecord,
  CorporateDocument,
  ImmigrationRecord,
  OfficeTicket,
  PropertyRecord,
} from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";

function FormField({ label, optional, children }: { label: string; optional?: boolean; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <label className="mb-1 block text-meta font-medium text-ink-2">
        {label}
        {optional && <span className="font-normal text-ink-3"> (optional)</span>}
      </label>
      {children}
    </div>
  );
}

const inputClass =
  "block w-full min-w-0 bg-transparent border-0 border-b border-control rounded-none px-0 py-1.5 text-sm text-ink placeholder:text-ink-3/70 focus:outline-none focus:shadow-[inset_0_-1px_0_var(--color-hema)] focus:border-hema aria-[invalid=true]:border-danger disabled:text-ink-3";

function ModalFrame({
  title,
  subtitle,
  children,
  onClose,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-ink/40 backdrop-blur-xs" onClick={onClose} aria-hidden />
      <div className="relative z-10 w-full max-w-xl rounded-[3px] border border-rule bg-sheet p-6 shadow-overlay max-h-[92dvh] overflow-y-auto">
        <div className="mb-5 flex items-start justify-between gap-4 border-b border-rule pb-3.5">
          <div>
            <h2 className="text-heading text-ink">{title}</h2>
            {subtitle && <p className="mt-1 text-meta text-ink-3">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-ink"
          >
            <X className="size-4" />
            <span className="sr-only">Close</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// --- Permit Modal (BOC, SEC, BIR, LGU, FDA) ---

export function PermitModal({
  permit,
  onClose,
}: {
  permit?: ComplianceRecord | null;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const expDate = formData.get("expirationDate") as string;
    if (!expDate) {
      setError("Expiration Date is required for renewal countdown tracking.");
      return;
    }

    const payload = {
      title: (formData.get("title") as string) || "",
      category: (formData.get("category") as string) || "other",
      agency: (formData.get("agency") as string) || "",
      referenceNumber: (formData.get("referenceNumber") as string) || "",
      issuanceDate: (formData.get("issuanceDate") as string) || null,
      expirationDate: expDate,
      renewalWindowDays: Number(formData.get("renewalWindowDays")) || 60,
      status: (formData.get("status") as string) || "active",
      responsiblePerson: (formData.get("responsiblePerson") as string) || null,
      estimatedCost: formData.get("estimatedCost") ? Number(formData.get("estimatedCost")) : null,
      notes: (formData.get("notes") as string) || null,
    };

    const res = await savePermit(permit ? permit.id : null, payload);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={permit ? "Edit Registration / Permit" : "Record Registration or Permit"}
      subtitle="BOC CPRS accreditation, LGU Mayor's Permit, SEC GIS, BIR, FDA licenses"
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Registration / Permit Title">
          <input
            name="title"
            required
            defaultValue={permit?.title ?? ""}
            placeholder="e.g. BOC CPRS Importer Accreditation"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Category / Scope">
            <select
              name="category"
              defaultValue={permit?.category ?? "boc"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="boc">Bureau of Customs (BOC)</option>
              <option value="lgu">LGU Mayor's Business Permit</option>
              <option value="sec">SEC Annual GIS & Filings</option>
              <option value="bir">BIR Form 0605 / 2303 Registration</option>
              <option value="fda">FDA License to Operate (LTO)</option>
              <option value="sanitary_fire">Fire Safety (FSIC) & Sanitary</option>
              <option value="other">Other Regulatory Clearance</option>
            </select>
          </FormField>

          <FormField label="Issuing Body / Agency">
            <input
              name="agency"
              required
              defaultValue={permit?.agency ?? "Bureau of Customs (BOC)"}
              placeholder="e.g. Bureau of Customs"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="License / Reference Number">
            <input
              name="referenceNumber"
              required
              defaultValue={permit?.referenceNumber ?? ""}
              placeholder="e.g. BOC-CPRS-2026-0941"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Status">
            <select
              name="status"
              defaultValue={permit?.status ?? "active"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="active">Active / Valid</option>
              <option value="pending_renewal">Pending Renewal</option>
              <option value="under_review">Under Agency Review</option>
              <option value="expired">Expired</option>
            </select>
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Issuance Date (Optional)">
            <input
              type="date"
              name="issuanceDate"
              defaultValue={permit?.issuanceDate ? permit.issuanceDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiration Date">
            <input
              type="date"
              name="expirationDate"
              required
              defaultValue={permit?.expirationDate ? permit.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Renewal Window (Days)">
            <input
              type="number"
              name="renewalWindowDays"
              defaultValue={permit?.renewalWindowDays ?? 60}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Responsible Executive / Assistant">
            <input
              name="responsiblePerson"
              defaultValue={permit?.responsiblePerson ?? ""}
              placeholder="e.g. Deo Castillo"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Estimated Cost (PHP)">
            <input
              type="number"
              step="0.01"
              name="estimatedCost"
              defaultValue={permit?.estimatedCost ?? ""}
              placeholder="e.g. 15000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Compliance Notes & Action Items">
          <textarea
            name="notes"
            rows={2}
            defaultValue={permit?.notes ?? ""}
            placeholder="Special instructions, broker contact, liaison tracking..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {permit ? "Save Changes" : "Create Record"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}

// --- Immigration & Expatriate Modal (ACR, AEP, Visas, Passports) ---

export function ImmigrationModal({
  record,
  onClose,
}: {
  record?: ImmigrationRecord | null;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const expDate = formData.get("expirationDate") as string;
    if (!expDate) {
      setError("Expiration Date is required for countdown tracking.");
      return;
    }

    const payload = {
      individualName: (formData.get("individualName") as string) || "",
      designation: (formData.get("designation") as string) || "",
      nationality: (formData.get("nationality") as string) || "",
      documentType: (formData.get("documentType") as string) || "visa",
      documentNumber: (formData.get("documentNumber") as string) || "",
      issuanceDate: (formData.get("issuanceDate") as string) || null,
      expirationDate: expDate,
      renewalLeadDays: Number(formData.get("renewalLeadDays")) || 60,
      sponsoringEntity: (formData.get("sponsoringEntity") as string) || null,
      status: (formData.get("status") as string) || "valid",
      assignedAssistant: (formData.get("assignedAssistant") as string) || null,
      notes: (formData.get("notes") as string) || null,
    };

    const res = await saveImmigration(record ? record.id : null, payload);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={record ? "Edit Immigration Document" : "Record Expatriate Compliance"}
      subtitle="ACR I-Card, DOLE AEP, 9(g)/47(a)(2) Visas, Passports & Executive IDs"
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Individual Full Name">
            <input
              name="individualName"
              required
              defaultValue={record?.individualName ?? ""}
              placeholder="e.g. Dr. Alistair Finch"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Designation / Executive Role">
            <input
              name="designation"
              required
              defaultValue={record?.designation ?? ""}
              placeholder="e.g. Managing Director - APAC"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Nationality">
            <input
              name="nationality"
              required
              defaultValue={record?.nationality ?? ""}
              placeholder="e.g. British"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Document Type">
            <select
              name="documentType"
              defaultValue={record?.documentType ?? "acr_card"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="acr_card">Alien Cert. of Registration (ACR I-Card)</option>
              <option value="aep_permit">DOLE Alien Employment Permit (AEP)</option>
              <option value="visa">Executive Visa (9g / 47a2 / PEZA)</option>
              <option value="passport">Passport</option>
              <option value="exec_id">Official Executive ID</option>
            </select>
          </FormField>

          <FormField label="Document / Card Number">
            <input
              name="documentNumber"
              required
              defaultValue={record?.documentNumber ?? ""}
              placeholder="e.g. ACR-F00009841"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Issuance Date (Optional)">
            <input
              type="date"
              name="issuanceDate"
              defaultValue={record?.issuanceDate ? record.issuanceDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiration Date">
            <input
              type="date"
              name="expirationDate"
              required
              defaultValue={record?.expirationDate ? record.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Lead Time (Days)">
            <input
              type="number"
              name="renewalLeadDays"
              defaultValue={record?.renewalLeadDays ?? 60}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Sponsoring Entity">
            <input
              name="sponsoringEntity"
              defaultValue={record?.sponsoringEntity ?? "Nabhi Pharma Philippines Inc."}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Assigned Executive Assistant">
            <input
              name="assignedAssistant"
              defaultValue={record?.assignedAssistant ?? ""}
              placeholder="e.g. Mila Aguilar"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Immigration Status">
          <select
            name="status"
            defaultValue={record?.status ?? "valid"}
            className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
          >
            <option value="valid">Valid / In Good Standing</option>
            <option value="expiring_soon">Expiring Soon (Within Window)</option>
            <option value="in_renewal">Petition / Renewal Filed</option>
            <option value="expired">Expired / Urgent Regularisation</option>
          </select>
        </FormField>

        <FormField label="Notes / Counsel Instructions">
          <textarea
            name="notes"
            rows={2}
            defaultValue={record?.notes ?? ""}
            placeholder="Embassy or Bureau of Immigration notes, biometrics appointment, legal counsel contact..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {record ? "Save Changes" : "Save Expatriate Record"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}

// --- Corporate Document Modal (Insurance, Contracts, Resolutions) ---

export function DocumentModal({
  document,
  onClose,
}: {
  document?: CorporateDocument | null;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const payload = {
      title: (formData.get("title") as string) || "",
      category: (formData.get("category") as string) || "insurance",
      counterparty: (formData.get("counterparty") as string) || "",
      referenceNumber: (formData.get("referenceNumber") as string) || null,
      effectiveDate: (formData.get("effectiveDate") as string) || null,
      expirationDate: (formData.get("expirationDate") as string) || null,
      autoRenews: formData.get("autoRenews") === "on",
      noticePeriodDays: Number(formData.get("noticePeriodDays")) || 30,
      custodian: (formData.get("custodian") as string) || null,
      status: (formData.get("status") as string) || "active",
      annualValue: formData.get("annualValue") ? Number(formData.get("annualValue")) : null,
      notes: (formData.get("notes") as string) || null,
    };

    const res = await saveDocument(document ? document.id : null, payload);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={document ? "Edit Corporate Document" : "Record Corporate Document & Insurance"}
      subtitle="D&O liability, general insurance policies, commercial contracts, board resolutions"
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Document / Policy Title">
          <input
            name="title"
            required
            defaultValue={document?.title ?? ""}
            placeholder="e.g. Directors & Officers (D&O) Liability Insurance Policy"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Category">
            <select
              name="category"
              defaultValue={document?.category ?? "insurance"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="insurance">Corporate Insurance Policy</option>
              <option value="commercial_contract">Commercial Contract / Vendor Agreement</option>
              <option value="nda">Non-Disclosure Agreement (NDA)</option>
              <option value="board_resolution">Board Resolution / Sec. Certificate</option>
              <option value="legal_retainer">Legal / Consultant Retainer</option>
              <option value="sla">Service Level Agreement (SLA)</option>
            </select>
          </FormField>

          <FormField label="Counterparty / Underwriter / Institution">
            <input
              name="counterparty"
              required
              defaultValue={document?.counterparty ?? ""}
              placeholder="e.g. Malayan Insurance Co., Inc."
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Policy / Contract Reference">
            <input
              name="referenceNumber"
              defaultValue={document?.referenceNumber ?? ""}
              placeholder="e.g. POL-DO-2026-01"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiration Date (if applicable)">
            <input
              type="date"
              name="expirationDate"
              defaultValue={document?.expirationDate ? document.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Notice Required (Days)">
            <input
              type="number"
              name="noticePeriodDays"
              defaultValue={document?.noticePeriodDays ?? 30}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Annual Premium / Value (PHP)">
            <input
              type="number"
              step="0.01"
              name="annualValue"
              defaultValue={document?.annualValue ?? ""}
              placeholder="e.g. 350000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Internal Custodian">
            <input
              name="custodian"
              defaultValue={document?.custodian ?? "Corporate Secretary"}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="autoRenews"
            name="autoRenews"
            defaultChecked={document?.autoRenews ?? false}
            className="size-4 rounded-[2px] border-control text-hema"
          />
          <label htmlFor="autoRenews" className="text-meta text-ink-2">
            Auto-renews unless prior cancellation notice is provided
          </label>
        </div>

        <FormField label="Notes / Renewal Conditions">
          <textarea
            name="notes"
            rows={2}
            defaultValue={document?.notes ?? ""}
            placeholder="Coverage terms, renewal broker details, arbitration clauses..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {document ? "Save Changes" : "Save Document"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}

// --- Properties & Facilities Modal ---

export function PropertyModal({
  property,
  onClose,
}: {
  property?: PropertyRecord | null;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const leaseEnd = formData.get("leaseEnd") as string;
    if (!leaseEnd) {
      setError("Lease End Date is required for renewal countdown.");
      return;
    }

    const payload = {
      name: (formData.get("name") as string) || "",
      propertyType: (formData.get("propertyType") as string) || "office",
      address: (formData.get("address") as string) || "",
      lessorName: (formData.get("lessorName") as string) || "",
      lessorContact: (formData.get("lessorContact") as string) || null,
      leaseStart: (formData.get("leaseStart") as string) || null,
      leaseEnd,
      noticeDeadlineDays: Number(formData.get("noticeDeadlineDays")) || 90,
      monthlyRent: formData.get("monthlyRent") ? Number(formData.get("monthlyRent")) : null,
      escalationRatePct: formData.get("escalationRatePct") ? Number(formData.get("escalationRatePct")) : null,
      securityDeposit: formData.get("securityDeposit") ? Number(formData.get("securityDeposit")) : null,
      utilitiesInfo: (formData.get("utilitiesInfo") as string) || null,
      status: (formData.get("status") as string) || "active",
      assignedManager: (formData.get("assignedManager") as string) || null,
      notes: (formData.get("notes") as string) || null,
    };

    const res = await saveProperty(property ? property.id : null, payload);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={property ? "Edit Property / Lease" : "Record Corporate Property & Lease"}
      subtitle="Corporate offices, pharma warehouses, regional depots, lease countdowns, utilities"
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Property Name">
          <input
            name="name"
            required
            defaultValue={property?.name ?? ""}
            placeholder="e.g. Nabhi Corporate Headquarters — Ayala Triangle Tower One"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Property Type">
            <select
              name="propertyType"
              defaultValue={property?.propertyType ?? "office"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="office">Corporate Head Office / Branch</option>
              <option value="warehouse">Central Pharma Distribution Warehouse</option>
              <option value="depot">Regional Distribution Depot</option>
              <option value="parking">Dedicated Fleet / Executive Parking</option>
              <option value="expat_housing">Expatriate Executive Residence</option>
            </select>
          </FormField>

          <FormField label="Lessor / Landlord Entity">
            <input
              name="lessorName"
              required
              defaultValue={property?.lessorName ?? ""}
              placeholder="e.g. Ayala Land Offices Inc."
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Full Physical Address">
          <input
            name="address"
            required
            defaultValue={property?.address ?? ""}
            placeholder="e.g. 24th Floor, Tower One & Exchange Plaza, Ayala Ave, Makati City"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Lease Start Date">
            <input
              type="date"
              name="leaseStart"
              defaultValue={property?.leaseStart ? property.leaseStart.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Lease Expiration Date">
            <input
              type="date"
              name="leaseEnd"
              required
              defaultValue={property?.leaseEnd ? property.leaseEnd.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Notice Required (Days)">
            <input
              type="number"
              name="noticeDeadlineDays"
              defaultValue={property?.noticeDeadlineDays ?? 90}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Monthly Rent (PHP)">
            <input
              type="number"
              step="0.01"
              name="monthlyRent"
              defaultValue={property?.monthlyRent ?? ""}
              placeholder="e.g. 385000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Escalation Rate (%/yr)">
            <input
              type="number"
              step="0.1"
              name="escalationRatePct"
              defaultValue={property?.escalationRatePct ?? 5.0}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Security Deposit (PHP)">
            <input
              type="number"
              step="0.01"
              name="securityDeposit"
              defaultValue={property?.securityDeposit ?? ""}
              placeholder="e.g. 1155000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Utilities & Meter Accounts">
          <textarea
            name="utilitiesInfo"
            rows={2}
            defaultValue={property?.utilitiesInfo ?? ""}
            placeholder="Meralco CIN, Manila Water account, Leased-line telecom account, Building association dues..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {property ? "Save Changes" : "Save Property"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}

// --- Office Concern & Service Desk Ticket Modal ---

export function TicketModal({
  ticket,
  onClose,
}: {
  ticket?: OfficeTicket | null;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const payload = {
      title: (formData.get("title") as string) || "",
      category: (formData.get("category") as string) || "facilities",
      priority: ((formData.get("priority") as string) || "normal") as OfficeTicket["priority"],
      status: ((formData.get("status") as string) || "open") as OfficeTicket["status"],
      requesterName: (formData.get("requesterName") as string) || "",
      requesterEmail: (formData.get("requesterEmail") as string) || null,
      executiveSponsor: (formData.get("executiveSponsor") as string) || null,
      assignedTo: (formData.get("assignedTo") as string) || null,
      slaDueDate: (formData.get("slaDueDate") as string) || null,
      description: (formData.get("description") as string) || "",
      resolutionNotes: (formData.get("resolutionNotes") as string) || null,
    };

    const res = await saveTicket(ticket ? ticket.id : null, payload);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={ticket ? `Edit Ticket ${ticket.ticketNumber}` : "Raise Office Concern / Service Request"}
      subtitle="Facilities maintenance, executive VIP transport, supplies procurement, messenger dispatch"
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Concern / Request Title">
          <input
            name="title"
            required
            defaultValue={ticket?.title ?? ""}
            placeholder="e.g. Boardroom A HVAC Inverter Malfunction prior to Board Session"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Category">
            <select
              name="category"
              defaultValue={ticket?.category ?? "facilities"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="facilities">Facilities & Maintenance (Aircon, Plumbing, Power)</option>
              <option value="vip_logistics">Executive VIP Transport & Protocol</option>
              <option value="supplies">Office Supplies & Asset Procurement</option>
              <option value="boardroom">Boardroom & Executive Meeting Concierge</option>
              <option value="courier_dispatch">Emergency Courier & Government Liaison</option>
              <option value="it_security">IT Hardware & Building Access Badges</option>
              <option value="general">General Administrative Concern</option>
            </select>
          </FormField>

          <FormField label="Priority / Urgency">
            <select
              name="priority"
              defaultValue={ticket?.priority ?? "normal"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="urgent">Urgent / Emergency (Immediate SLA)</option>
              <option value="high">High (24-48 Hours)</option>
              <option value="normal">Normal</option>
              <option value="low">Low / Scheduled</option>
            </select>
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Requester Name">
            <input
              name="requesterName"
              required
              defaultValue={ticket?.requesterName ?? ""}
              placeholder="e.g. Carmen Villanueva"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Executive Sponsor (Optional)">
            <input
              name="executiveSponsor"
              defaultValue={ticket?.executiveSponsor ?? "CEO Office"}
              placeholder="e.g. Managing Director Office"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Assigned Assistant / Administrator">
            <input
              name="assignedTo"
              defaultValue={ticket?.assignedTo ?? "Deo Castillo"}
              placeholder="e.g. Deo Castillo"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Target SLA Completion Date">
            <input
              type="date"
              name="slaDueDate"
              defaultValue={ticket?.slaDueDate ? ticket.slaDueDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Detailed Description">
          <textarea
            name="description"
            rows={3}
            required
            defaultValue={ticket?.description ?? ""}
            placeholder="State exact requirements, room location, flight number for VIP pickup, or courier destination..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        {ticket && (
          <div className="grid gap-3 sm:grid-cols-2 border-t border-rule pt-3">
            <FormField label="Status">
              <select
                name="status"
                defaultValue={ticket.status}
                className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
              >
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="pending_vendor">Pending External Vendor</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </FormField>

            <FormField label="Resolution Notes">
              <input
                name="resolutionNotes"
                defaultValue={ticket.resolutionNotes ?? ""}
                placeholder="Technician details, completion remarks..."
                className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
              />
            </FormField>
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {ticket ? "Save Changes" : "Log Ticket"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}

// --- Ticket Update / Note Log Modal ---

export function TicketUpdateModal({
  ticket,
  onClose,
}: {
  ticket: OfficeTicket;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(formData: FormData) {
    setError(null);
    const content = (formData.get("content") as string) || "";
    if (!content.trim()) {
      setError("Please write an update note.");
      return;
    }
    const newStatus = (formData.get("newStatus") as string) || undefined;
    const authorName = (formData.get("authorName") as string) || "Executive Admin";

    const res = await addTicketUpdate(ticket.id, {
      authorName,
      content,
      newStatus,
      updateType: newStatus && newStatus !== ticket.status ? "status_change" : "comment",
    });
    if (!res.ok) {
      setError(res.error);
      return;
    }
    onClose();
  }

  return (
    <ModalFrame
      title={`Update on Ticket ${ticket.ticketNumber}`}
      subtitle={ticket.title}
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <div className="rounded-[2px] bg-bench p-3 text-meta text-ink-2">
          <div className="font-semibold text-ink">Original Description:</div>
          <p className="mt-1 line-clamp-3 text-ink-3">{ticket.description}</p>
        </div>

        <FormField label="Your Name / Role">
          <input
            name="authorName"
            required
            defaultValue="Executive Admin"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <FormField label="Action Taken / Status Note">
          <textarea
            name="content"
            rows={3}
            required
            placeholder="e.g. Contacted building administration; technician arriving at 2:00 PM today..."
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <FormField label="Update Ticket Status">
          <select
            name="newStatus"
            defaultValue={ticket.status}
            className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
          >
            <option value="open">Keep as Open</option>
            <option value="in_progress">Set to In Progress</option>
            <option value="pending_vendor">Set to Pending External Vendor</option>
            <option value="resolved">Mark Resolved</option>
            <option value="closed">Close Ticket</option>
          </select>
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            Post Update
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}
