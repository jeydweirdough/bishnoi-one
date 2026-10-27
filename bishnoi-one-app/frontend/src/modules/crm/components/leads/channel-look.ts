import { FileText, Globe, MessagesSquare, Phone, PhoneCall, Send, type LucideIcon } from "lucide-react";

// Each lead channel's mark: an icon in its own colour, so the channel reads before its name does.
// The same on the inbox's rows and on its Channels card. Colours are 4.5:1 or more on their tint.

export type ChannelLook = { icon: LucideIcon; tint: string; ink: string; short: string };

export const CHANNEL_LOOK: Record<string, ChannelLook> = {
  facebook: { icon: FileText, tint: "#e7effd", ink: "#1f5fd1", short: "Facebook" },
  messenger: { icon: Send, tint: "#efe8fd", ink: "#7a3fe0", short: "Messenger" },
  whatsapp: { icon: Phone, tint: "#e3f5ea", ink: "#1a7a43", short: "WhatsApp" },
  viber: { icon: PhoneCall, tint: "#f0e9fb", ink: "#6c4aa8", short: "Viber" },
  tawkto: { icon: MessagesSquare, tint: "#e6f4ee", ink: "#2c7a5a", short: "Tawk.to" },
  form: { icon: Globe, tint: "#f1f1ee", ink: "#55554f", short: "Website forms" },
  web_forms: { icon: Globe, tint: "#f1f1ee", ink: "#55554f", short: "Website forms" },
};

export const lookOf = (key: string): ChannelLook => CHANNEL_LOOK[key] ?? CHANNEL_LOOK.form;
