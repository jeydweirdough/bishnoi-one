// Your profile: who you are, Edit profile and Change password, and what you did lately.
import ProfilePage from "@/src/modules/finance/platform/screens/profile";
import { ACTIONS } from "@/src/modules/finance/screens/admin";

export { metadata } from "@/src/modules/finance/platform/screens/profile";

export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <ProfilePage searchParams={searchParams} actions={ACTIONS} />;
}
