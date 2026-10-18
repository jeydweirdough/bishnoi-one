import type { CodeFields } from "./types";

// A prompt to give another AI (ChatGPT, Claude, Gemini) so what it writes is a
// quotation in this format: one HTML page with the CRM's %fields%, that pastes
// straight into the Code box and previews as it will print. The rules here are
// the ones the CRM applies (backend app/quote_code.py): what isn't allowed
// there is taken out before showing or printing, so asking for it is wasted.

const TAGS =
  "html, head, body, style, div, span, p, br, hr, h1–h6, strong, b, em, i, u, small, sup, sub, table, thead, tbody, tfoot, tr, td, th, colgroup, col, caption, ul, ol, li, section, header, footer, main, article, figure, figcaption, blockquote, pre, code";

export function aiPrompt(fields: CodeFields): string {
  const [start, end] = fields.loop;
  const list = fields.groups.map((g) => `${g.name}:\n${g.fields.map((f) => `  ${f.field}  ${f.label}`).join("\n")}`).join("\n\n");
  return `You are designing a printable quotation template for our CRM (Bishnoi One). Follow this format exactly, because your answer will be pasted into the CRM as it is.

WHAT TO REPLY WITH
- One complete HTML document, and nothing else: no explanation before or after.
- Put it in a single \`\`\`html code block.

THE PAGE
- It is printed on A4 portrait. Start the <style> with: @page { size: A4; margin: 14mm; }
- Put all styling in one <style> block in <head>, or in style="" attributes.
- Use only these tags: ${TAGS}.
- Use only these attributes: class, style, id, align, valign, width, height, colspan, rowspan, title, dir, lang.
- Not allowed, and removed by the CRM if present: <script> or any JavaScript, onclick and other event attributes, <iframe>, <form>, <input>, <link>, <a> links, @import, and anything loaded from the internet (web fonts, outside CSS, outside images). Use system fonts such as Arial, Helvetica or "Times New Roman".
- Pictures: write %logo% where the company logo goes and %signature% where the e-signature goes. Each becomes a whole image by itself; do not wrap them in <img>. Size them with CSS on img.logo and img.signature.
- Keep it black on white so it prints well. Avoid page breaks inside a product row (tr { break-inside: avoid; }).

THE FIELDS
Write a field exactly as listed, percent signs included, wherever its value should appear. The CRM fills each in with the quote's details. Don't invent fields that aren't listed.

PRODUCT ROWS
Inside the table's <tbody>, put ${start} before one <tr> and ${end} after it. That row repeats for every product, so use only the "Each product" fields inside it. Alternatively, %items_table% puts in a ready-made products table.

${list}

AN EXAMPLE IN THIS FORMAT (our standard layout; restyle it freely)
\`\`\`html
${fields.starter.trim()}
\`\`\`

MY DESIGN
[Describe the look you want here, or attach a photo or PDF of your current quotation and say "make it look like this".]`;
}

/** What another AI pasted back, without the \`\`\`html fence around it. */
export function unfence(text: string): string {
  // The code block wherever it sits: an AI often says a line before or after it.
  const m = text.match(/```[a-zA-Z]*[ \t]*\r?\n([\s\S]*?)\r?\n?```/);
  return m && m[1].includes("<") ? m[1] : text;
}
