import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { GoBack, GoHome } from "@/src/platform/screens/error-actions";

export const metadata = { title: "Not available right now", robots: { index: false } };

export default function Unavailable() {
  return <ErrorScreen kind="unavailable" actions={<><GoBack /><GoHome /></>} />;
}
