import { Video } from "lucide-react";

/** Which service a meeting link is on, by its address: "Google Meet", "Zoom", "Teams". */
export function meetingService(link: string): string | null {
  let host = "";
  try {
    host = new URL(link).hostname.toLowerCase();
  } catch {
    return null;
  }
  if (host === "meet.google.com") return "Google Meet";
  if (host.endsWith("zoom.us") || host.endsWith("zoom.com")) return "Zoom";
  if (host.endsWith("teams.microsoft.com") || host.endsWith("teams.live.com")) return "Teams";
  if (host.endsWith("webex.com")) return "Webex";
  return null;
}

/** "Join" a meeting: opens its link in a new tab, named by the service it's on. */
export function JoinLink({ link, size = "md" }: { link: string; size?: "sm" | "md" }) {
  const service = meetingService(link);
  return (
    <a
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full bg-ink font-medium text-white hover:bg-hema-hover ${size === "sm" ? "px-2.5 py-0.5 text-meta" : "px-3 py-1 text-sm"}`}
      title={link}
    >
      <Video className="size-3.5" aria-hidden />
      {service ? `Join on ${service}` : "Join"}
    </a>
  );
}
