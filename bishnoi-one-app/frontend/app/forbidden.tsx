import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { plainButton } from "@/src/platform/screens/error-screen";
import { GoBack, GoHome } from "@/src/platform/screens/error-actions";

export default function Forbidden() {
  return <ErrorScreen kind="forbidden" actions={<><GoBack /><GoHome /><form method="post" action="/auth/view-as/stop"><button type="submit" className={plainButton()}>Stop viewing and return to my account</button></form></>} />;
}
