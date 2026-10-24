// Your profile: who you are, Edit profile and Change password, and what you did lately.
import ProfilePage from "@/src/modules/console/platform/screens/profile";
import { ACTION_LINES } from "@/src/modules/console/lib/words";

export { metadata } from "@/src/modules/console/platform/screens/profile";

export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <ProfilePage searchParams={searchParams} actions={ACTION_LINES} />;
}
