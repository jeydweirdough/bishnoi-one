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
      title={permit ? "Edit permit" : "New permit"}
      subtitle="A government registration or permit the company must keep current."
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Permit name">
          <input
            name="title"
            required
            defaultValue={permit?.title ?? ""}
            placeholder="e.g. BOC CPRS Importer Accreditation"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Type">
            <select
              name="category"
              defaultValue={permit?.category ?? "boc"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="boc">Bureau of Customs (BOC)</option>
              <option value="lgu">Mayor's business permit</option>
              <option value="sec">SEC GIS and filings</option>
              <option value="bir">BIR registration</option>
              <option value="fda">FDA license to operate</option>
              <option value="sanitary_fire">Fire safety and sanitary</option>
              <option value="other">Other</option>
            </select>
          </FormField>

          <FormField label="Issuing agency">
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
          <FormField label="Reference number">
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
              <option value="active">Active</option>
              <option value="pending_renewal">For renewal</option>
              <option value="under_review">Under agency review</option>
              <option value="expired">Expired</option>
            </select>
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Issue date" optional>
            <input
              type="date"
              name="issuanceDate"
              defaultValue={permit?.issuanceDate ? permit.issuanceDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiry date">
            <input
              type="date"
              name="expirationDate"
              required
              defaultValue={permit?.expirationDate ? permit.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Alert before expiry (days)">
            <input
              type="number"
              name="renewalWindowDays"
              defaultValue={permit?.renewalWindowDays ?? 60}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Person responsible">
            <input
              name="responsiblePerson"
              defaultValue={permit?.responsiblePerson ?? ""}
              placeholder="e.g. Deo Castillo"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Estimated cost (PHP)" optional>
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

        <FormField label="Notes" optional>
          <textarea
            name="notes"
            rows={2}
            defaultValue={permit?.notes ?? ""}
            placeholder="Broker contact, filing instructions"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {permit ? "Save changes" : "Add permit"}
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
      title={record ? "Edit expatriate document" : "New expatriate document"}
      subtitle="A foreign employee's ACR I-Card, work permit, visa, passport or company ID."
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Full name">
            <input
              name="individualName"
              required
              defaultValue={record?.individualName ?? ""}
              placeholder="e.g. Dr. Alistair Finch"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Position">
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
              <option value="acr_card">ACR I-Card</option>
              <option value="aep_permit">DOLE work permit (AEP)</option>
              <option value="visa">Visa (9(g), 47(a)(2), PEZA)</option>
              <option value="passport">Passport</option>
              <option value="exec_id">Company ID</option>
            </select>
          </FormField>

          <FormField label="Document number">
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
          <FormField label="Issue date" optional>
            <input
              type="date"
              name="issuanceDate"
              defaultValue={record?.issuanceDate ? record.issuanceDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiry date">
            <input
              type="date"
              name="expirationDate"
              required
              defaultValue={record?.expirationDate ? record.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Alert before expiry (days)">
            <input
              type="number"
              name="renewalLeadDays"
              defaultValue={record?.renewalLeadDays ?? 60}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Sponsoring company">
            <input
              name="sponsoringEntity"
              defaultValue={record?.sponsoringEntity ?? "Nabhi Pharma Philippines Inc."}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Person responsible">
            <input
              name="assignedAssistant"
              defaultValue={record?.assignedAssistant ?? ""}
              placeholder="e.g. Mila Aguilar"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Status">
          <select
            name="status"
            defaultValue={record?.status ?? "valid"}
            className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
          >
            <option value="valid">Valid</option>
            <option value="expiring_soon">Expiring soon</option>
            <option value="in_renewal">Renewal filed</option>
            <option value="expired">Expired</option>
          </select>
        </FormField>

        <FormField label="Notes" optional>
          <textarea
            name="notes"
            rows={2}
            defaultValue={record?.notes ?? ""}
            placeholder="Biometrics appointment, counsel contact"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {record ? "Save changes" : "Add document"}
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
      title={document ? "Edit document" : "New document"}
      subtitle="An insurance policy, contract, NDA, board resolution or retainer."
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Document name">
          <input
            name="title"
            required
            defaultValue={document?.title ?? ""}
            placeholder="e.g. Directors and officers liability insurance"
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
              <option value="insurance">Insurance policy</option>
              <option value="commercial_contract">Contract</option>
              <option value="nda">NDA</option>
              <option value="board_resolution">Board resolution or secretary's certificate</option>
              <option value="legal_retainer">Legal or consultant retainer</option>
              <option value="sla">Service level agreement</option>
            </select>
          </FormField>

          <FormField label="Other party">
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
          <FormField label="Reference number">
            <input
              name="referenceNumber"
              defaultValue={document?.referenceNumber ?? ""}
              placeholder="e.g. POL-DO-2026-01"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Expiry date" optional>
            <input
              type="date"
              name="expirationDate"
              defaultValue={document?.expirationDate ? document.expirationDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Notice period (days)">
            <input
              type="number"
              name="noticePeriodDays"
              defaultValue={document?.noticePeriodDays ?? 30}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Annual amount (PHP)" optional>
            <input
              type="number"
              step="0.01"
              name="annualValue"
              defaultValue={document?.annualValue ?? ""}
              placeholder="e.g. 350000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Custodian">
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

        <FormField label="Notes" optional>
          <textarea
            name="notes"
            rows={2}
            defaultValue={document?.notes ?? ""}
            placeholder="Coverage, renewal terms, broker"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {document ? "Save changes" : "Add document"}
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
      title={property ? "Edit property" : "New property"}
      subtitle="An office, warehouse, depot or residence the company leases or owns."
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Property name">
          <input
            name="name"
            required
            defaultValue={property?.name ?? ""}
            placeholder="e.g. Head office, Makati"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Type">
            <select
              name="propertyType"
              defaultValue={property?.propertyType ?? "office"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="office">Office</option>
              <option value="warehouse">Warehouse</option>
              <option value="depot">Depot</option>
              <option value="parking">Parking</option>
              <option value="expat_housing">Staff residence</option>
            </select>
          </FormField>

          <FormField label="Lessor">
            <input
              name="lessorName"
              required
              defaultValue={property?.lessorName ?? ""}
              placeholder="e.g. Ayala Land Offices Inc."
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Address">
          <input
            name="address"
            required
            defaultValue={property?.address ?? ""}
            placeholder="e.g. 24th Floor, Tower One, Ayala Ave, Makati City"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Lease start">
            <input
              type="date"
              name="leaseStart"
              defaultValue={property?.leaseStart ? property.leaseStart.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Lease end">
            <input
              type="date"
              name="leaseEnd"
              required
              defaultValue={property?.leaseEnd ? property.leaseEnd.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Notice period (days)">
            <input
              type="number"
              name="noticeDeadlineDays"
              defaultValue={property?.noticeDeadlineDays ?? 90}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Monthly rent (PHP)">
            <input
              type="number"
              step="0.01"
              name="monthlyRent"
              defaultValue={property?.monthlyRent ?? ""}
              placeholder="e.g. 385000"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Yearly rent increase (%)">
            <input
              type="number"
              step="0.1"
              name="escalationRatePct"
              defaultValue={property?.escalationRatePct ?? 5.0}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Security deposit (PHP)" optional>
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

        <FormField label="Utility accounts" optional>
          <textarea
            name="utilitiesInfo"
            rows={2}
            defaultValue={property?.utilitiesInfo ?? ""}
            placeholder="Meralco, Manila Water, telecom, association dues"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {property ? "Save changes" : "Add property"}
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
      title={ticket ? `Edit ${ticket.ticketNumber}` : "New office request"}
      subtitle="A repair, supplies, transport, courier or other request to the administration office."
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <FormField label="Request">
          <input
            name="title"
            required
            defaultValue={ticket?.title ?? ""}
            placeholder="e.g. Boardroom A air conditioning not cooling"
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
              <option value="facilities">Facilities and repairs</option>
              <option value="vip_logistics">Guest transport</option>
              <option value="supplies">Office supplies</option>
              <option value="boardroom">Meeting rooms</option>
              <option value="courier_dispatch">Courier and government liaison</option>
              <option value="it_security">IT equipment and access cards</option>
              <option value="general">Other</option>
            </select>
          </FormField>

          <FormField label="Priority">
            <select
              name="priority"
              defaultValue={ticket?.priority ?? "normal"}
              className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
            >
              <option value="urgent">Urgent (same day)</option>
              <option value="high">High (within 2 days)</option>
              <option value="normal">Normal</option>
              <option value="low">Low</option>
            </select>
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Requested by">
            <input
              name="requesterName"
              required
              defaultValue={ticket?.requesterName ?? ""}
              placeholder="e.g. Carmen Villanueva"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="On behalf of" optional>
            <input
              name="executiveSponsor"
              defaultValue={ticket?.executiveSponsor ?? "CEO Office"}
              placeholder="e.g. Office of the Managing Director"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Assigned to">
            <input
              name="assignedTo"
              defaultValue={ticket?.assignedTo ?? "Deo Castillo"}
              placeholder="e.g. Deo Castillo"
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>

          <FormField label="Target date">
            <input
              type="date"
              name="slaDueDate"
              defaultValue={ticket?.slaDueDate ? ticket.slaDueDate.slice(0, 10) : ""}
              className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
            />
          </FormField>
        </div>

        <FormField label="Details">
          <textarea
            name="description"
            rows={3}
            required
            defaultValue={ticket?.description ?? ""}
            placeholder="What is needed, where, and by when"
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
                <option value="in_progress">In progress</option>
                <option value="pending_vendor">Waiting on supplier</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </FormField>

            <FormField label="Resolution" optional>
              <input
                name="resolutionNotes"
                defaultValue={ticket.resolutionNotes ?? ""}
                placeholder="What was done"
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
            {ticket ? "Save changes" : "Submit request"}
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
      title={`Update ${ticket.ticketNumber}`}
      subtitle={ticket.title}
      onClose={onClose}
    >
      <form action={handleSubmit} className="space-y-4 text-sm">
        {error && <div className="rounded-[2px] bg-danger-tint p-2.5 text-meta font-medium text-danger">{error}</div>}

        <div className="rounded-[2px] bg-bench p-3 text-meta text-ink-2">
          <div className="font-semibold text-ink">Original Description:</div>
          <p className="mt-1 line-clamp-3 text-ink-3">{ticket.description}</p>
        </div>

        <FormField label="Your name">
          <input
            name="authorName"
            required
            defaultValue="Executive Admin"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <FormField label="Update">
          <textarea
            name="content"
            rows={3}
            required
            placeholder="e.g. Technician arriving at 2:00 PM today"
            className="w-full rounded-[2px] border border-control px-3 py-1.5 focus:border-hema focus:outline-hidden"
          />
        </FormField>

        <FormField label="Status">
          <select
            name="newStatus"
            defaultValue={ticket.status}
            className="w-full rounded-[2px] border border-control px-2.5 py-1.5 focus:border-hema focus:outline-hidden"
          >
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="pending_vendor">Waiting on supplier</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </FormField>

        <div className="flex justify-end gap-2 border-t border-rule pt-3">
          <Button variant="default" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            Post update
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}
