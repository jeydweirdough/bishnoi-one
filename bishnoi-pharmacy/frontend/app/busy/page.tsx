import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { GoBack, GoHome } from "@/src/platform/screens/error-actions";

export const metadata = { title: "Slow down", robots: { index: false } };

export default function Busy() {
  return <ErrorScreen kind="busy" actions={<><GoBack /><GoHome /></>} />;
}
