import { ErrorScreen } from "@/src/modules/admin/platform/screens/error-screen";
import { GoBack, GoHome } from "@/src/modules/admin/platform/screens/error-actions";

export default function NotFound() {
  return <ErrorScreen kind="notFound" actions={<><GoHome primary /><GoBack primary={false} /></>} />;
}
