import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { GoBack, GoHome } from "@/src/platform/screens/error-actions";

export default function Forbidden() {
  return <ErrorScreen kind="forbidden" actions={<><GoBack /><GoHome /></>} />;
}
