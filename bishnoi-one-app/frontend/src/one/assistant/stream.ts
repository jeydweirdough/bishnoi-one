export type AssistantSource = { label: string; href?: string; reference?: string };
export type AssistantEvent = {
  type: "status" | "sources" | "text" | "error" | "done";
  text?: string; message?: string; items?: AssistantSource[];
  dateRange?: { from: string; to: string } | null;
  definitions?: Record<string, string> | null; retrievedAt?: string;
};

/** SSE frames may split anywhere, including UTF-8 characters and the data prefix. */
export async function readAssistantStream(body: ReadableStream<Uint8Array>, onEvent: (event: AssistantEvent) => void) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", completed = false, failed = false;
  try {
    while (true) {
      const part = await reader.read();
      buffer += part.done ? decoder.decode() : decoder.decode(part.value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      if (buffer.length > 65536) throw new Error("The assistant returned an oversized stream frame.");
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split("\n").filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const event = JSON.parse(data) as AssistantEvent;
        if (!["status", "sources", "text", "error", "done"].includes(event.type)) throw new Error("Unsupported assistant stream event.");
        completed ||= event.type === "done";
        failed ||= event.type === "error";
        onEvent(event);
      }
      if (part.done) break;
    }
    if (!completed && !failed) throw new Error("The connection ended before the answer was complete. Please retry.");
  } finally { await reader.cancel().catch(() => undefined); reader.releaseLock(); }
}
