import { ErrorScreen } from "./error-screen";
import { GoBack, GoHome } from "./error-actions";

export default function NotFound() {
  return <ErrorScreen kind="notFound" actions={<><GoHome primary /><GoBack primary={false} /></>} />;
}
