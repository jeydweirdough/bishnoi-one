import { load } from "@/src/platform/lib/api";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { ImmigrationScreen } from "@/src/screens/immigration";

export const metadata = { title: "Expatriate & Immigration · Executive Admin" };

export default async function Page() {
  const records = await load<ImmigrationRecord[]>("/admin/immigration");
  return <ImmigrationScreen records={records} />;
}
