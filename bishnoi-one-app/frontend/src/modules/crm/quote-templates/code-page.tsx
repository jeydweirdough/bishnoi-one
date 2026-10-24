"use client";

import { useRef, useState } from "react";

/** A quotation written as code, on the print page: in a frame of its own, so its
 *  styles stay on the quotation, as tall as the quotation. The Print button prints
 *  this frame. No scripts run in it (the CRM takes them out, and the frame forbids them). */
export function CodeQuotation({ html, title }: { html: string; title: string }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(1123); // an A4 page, at 96 dpi
  return (
    <iframe
      ref={frame}
      data-print
      title={title}
      sandbox="allow-same-origin allow-modals"
      srcDoc={html}
      onLoad={() => {
        const body = frame.current?.contentDocument?.documentElement;
        if (body) setHeight(Math.max(body.scrollHeight, 400));
      }}
      style={{ height }}
      className="mx-auto my-8 block w-full max-w-[210mm] bg-white shadow-sm"
    />
  );
}
