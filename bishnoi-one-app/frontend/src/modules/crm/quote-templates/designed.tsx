import type { Format } from "@/src/platform/lib/format";
import type { QuoteDocument } from "@/src/modules/crm/quote-templates/types";

const peso = (fmt: Format, amount: number | null) => (amount === null || amount === undefined ? "" : fmt.peso(Math.round(amount * 100)));

/** A quotation designed in Settings, laid out like the forms PCSO and the
 *  Office of the President take: letterhead, control number, the patient,
 *  the products, the certification, the company block and the e-signature. */
export function DesignedQuotation({ doc, fmt }: { doc: QuoteDocument; fmt: Format }) {
  const d = doc.design;
  const t = doc.template;
  const discounts = doc.lines.some((l) => l.discount);
  return (
    <div className="text-[10pt]">
      <header className="relative border-b-2 border-black pb-3 text-center">
        {t.hasLogo && (
          // eslint-disable-next-line @next/next/no-img-element -- a stored file, sized by its own proportions
          <img src={`/crm/quote-templates/${t.id}/images/logo`} alt="" className="absolute top-0 left-0 max-h-[22mm] max-w-[45mm] object-contain" />
        )}
        <p className="text-[15pt] font-bold uppercase">{d.companyName}</p>
        {d.address && <p className="mx-auto max-w-[120mm] whitespace-pre-line">{d.address}</p>}
        {d.phone && <p>{d.phone}</p>}
      </header>

      <div className="mt-4 text-center">
        <p className="text-[15pt] font-bold tracking-wide">{d.heading}</p>
        <p className="font-semibold">Control No. {doc.controlNumber}</p>
      </div>

      <section className="mt-5 grid grid-cols-[1fr_auto] gap-x-10 gap-y-1.5">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="font-semibold uppercase">{d.customerLabel}:</dt>
          <dd className="border-b border-neutral-400">{doc.customer}</dd>
          <dt className="font-semibold uppercase">Contact no.:</dt>
          <dd className="border-b border-neutral-400">{doc.phone || " "}</dd>
          <dt className="font-semibold uppercase">Address:</dt>
          <dd className="border-b border-neutral-400">{doc.address || " "}</dd>
          <dt className="font-semibold uppercase">Hospital or clinic:</dt>
          <dd className="border-b border-neutral-400">{doc.hospital || " "}</dd>
        </dl>
        <dl className="grid h-fit grid-cols-[auto_auto] gap-x-3 gap-y-1.5">
          <dt>Date issued</dt>
          <dd className="font-semibold">{fmt.dateLabel(doc.date)}</dd>
          {doc.validUntil && (
            <>
              <dt>Valid until</dt>
              <dd className="font-semibold">{fmt.dateLabel(doc.validUntil)}</dd>
            </>
          )}
          {doc.letterNumber && (
            <>
              <dt>GL number</dt>
              <dd className="font-semibold">{doc.letterNumber}</dd>
            </>
          )}
        </dl>
      </section>

      <table className="mt-5 w-full border-collapse text-[9pt]">
        <thead>
          <tr className="border border-black bg-neutral-100 text-left">
            {["No.", "Generic name", "Brand name", "Strength", "Preparation", "Quantity", "Price", ...(discounts ? ["Discount", "Price after discount"] : []), "Total"].map((h) => (
              <th key={h} scope="col" className="border border-black px-1.5 py-1 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {doc.lines.map((l) => (
            <tr key={l.no} className="break-inside-avoid align-top">
              <td className="border border-black px-1.5 py-1 tabular-nums">{l.no}</td>
              <td className="border border-black px-1.5 py-1">{l.generic}</td>
              <td className="border border-black px-1.5 py-1">{l.brand}</td>
              <td className="border border-black px-1.5 py-1">{l.strength}</td>
              <td className="border border-black px-1.5 py-1">{l.form}</td>
              <td className="border border-black px-1.5 py-1 text-right tabular-nums">
                {l.qty}
                {l.free > 0 && <span className="block">+{l.free} free</span>}
              </td>
              <td className="border border-black px-1.5 py-1 text-right tabular-nums">{peso(fmt, l.price)}</td>
              {discounts && (
                <>
                  <td className="border border-black px-1.5 py-1 text-right tabular-nums">{peso(fmt, l.discount)}</td>
                  <td className="border border-black px-1.5 py-1 text-right tabular-nums">{peso(fmt, l.net)}</td>
                </>
              )}
              <td className="border border-black px-1.5 py-1 text-right tabular-nums">{peso(fmt, l.total)}</td>
            </tr>
          ))}
          <tr>
            <td colSpan={discounts ? 9 : 7} className="border border-black px-1.5 py-1 text-right font-bold">
              GRAND TOTAL
            </td>
            <td className="border border-black px-1.5 py-1 text-right font-bold tabular-nums">{peso(fmt, doc.total)}</td>
          </tr>
        </tbody>
      </table>

      <section className="mt-5 break-inside-avoid space-y-2">
        {d.certification && <p>{d.certification}</p>}
        {d.acceptance && <p className="font-semibold">{d.acceptance}</p>}
      </section>

      <section className="mt-6 grid break-inside-avoid grid-cols-2 gap-x-10 gap-y-4">
        <div>
          <p className="border-b border-black font-semibold uppercase">{d.companyName}</p>
          <p className="text-[8.5pt] text-neutral-600">Name of partner health facility or medicine retailer</p>
        </div>
        <div>
          <p className="border-b border-black font-semibold uppercase">{d.payableTo}</p>
          <p className="text-[8.5pt] text-neutral-600">Company name the check is made payable to</p>
        </div>
        <div>
          <p>
            ( {d.vat === "vat" ? "x" : "  "} ) VAT&nbsp;&nbsp;&nbsp;( {d.vat === "non_vat" ? "x" : "  "} ) Non-VAT
          </p>
          {d.tin && <p>TIN: {d.tin}</p>}
        </div>
        <div>
          <p className="border-b border-black">{d.address || " "}</p>
          <p className="text-[8.5pt] text-neutral-600">Address</p>
        </div>
      </section>

      <section className="mt-6 w-[80mm] break-inside-avoid">
        <div className="relative h-[18mm]">
          {t.hasSignature && (
            // eslint-disable-next-line @next/next/no-img-element -- a stored file, sized by its own proportions
            <img src={`/crm/quote-templates/${t.id}/images/signature`} alt="Signature" className="absolute bottom-[-3mm] left-2 max-h-[20mm] max-w-[60mm] object-contain" />
          )}
        </div>
        <p className="border-b border-black font-semibold uppercase">{d.signatoryName || doc.preparedBy}</p>
        <p className="text-[8.5pt] text-neutral-600">Printed name and signature (authorized representative)</p>
        {d.signatoryTitle && (
          <>
            <p className="mt-2 border-b border-black">{d.signatoryTitle}</p>
            <p className="text-[8.5pt] text-neutral-600">Designation</p>
          </>
        )}
        {(d.signatoryContact || d.phone) && (
          <>
            <p className="mt-2 border-b border-black">{d.signatoryContact || d.phone}</p>
            <p className="text-[8.5pt] text-neutral-600">Customer service contact number</p>
          </>
        )}
      </section>

      {d.notes && <footer className="mt-6 border-t border-neutral-400 pt-2 text-center text-[9pt] whitespace-pre-line italic">{d.notes}</footer>}
    </div>
  );
}
