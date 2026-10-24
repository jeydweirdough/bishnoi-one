import { redirect } from "next/navigation";

// The Platform module opens on people and access.
export default function PlatformHome() {
  redirect("/platform/access");
}
