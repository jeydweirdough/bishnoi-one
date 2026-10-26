import { redirect } from "next/navigation";
export default async function ModuleReports({ params }: { params: Promise<{ module: string }> }) {
  redirect(`/platform/reports?group=${encodeURIComponent((await params).module)}`);
}
