// Your profile: who you are, Edit profile and Change password, what you did lately,
// and your e-signature (Finance's own, below the shared profile screen).
import ProfilePage from "@/src/platform/screens/profile";
import { load } from "@/src/platform/lib/api";
import { ACTIONS } from "@/src/screens/admin";
import { SignatureCard } from "@/src/signature/card";
import type { MySignature } from "@/src/signature/types";

export { metadata } from "@/src/platform/screens/profile";

export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const signature = await load<MySignature>("/auth/signature");
  return (
    <>
      <ProfilePage searchParams={searchParams} actions={ACTIONS} />
      <SignatureCard data={signature} />
    </>
  );
}
