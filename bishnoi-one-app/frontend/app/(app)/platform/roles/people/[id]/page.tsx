// The route. The screen is in src/, so it can be read on its own.
import { PersonScreen } from "@/src/one/access/person-page";

export const metadata = { title: "Person" };

export default async function Person({ params }: { params: Promise<{ id: string }> }) {
  return <PersonScreen id={(await params).id} />;
}
