import type { Metadata } from "next";
import { thisAppLabel } from "../lib/apps";
import { APP_NAME } from "../lib/labels";
import { LoginForm } from "./login-form";

// Each Orbit app signs in on its own page, so the tab says which one it is:
// six sign-in tabs that all read the same thing are six tabs you have to guess at.
export const metadata: Metadata = {
  title: thisAppLabel() ? `Sign in to ${thisAppLabel()}` : "Sign in",
};

// Shown only when SHOW_DEMO_ACCOUNTS=1 (development). Matches app/seed.py:
// one account per division, per team, per department and per role, so every
// perspective in the company can be signed into and looked at.
const DEMO_ACCOUNTS = [
  { group: "Sales · B2C", email: "ben@pharmacrm.test", who: "Ben Cruz", role: "Rep · B2C MD Telesales" },
  { email: "tess@pharmacrm.test", who: "Tess Aquino", role: "Team Lead · B2C General" },

  { group: "Sales · STC, URO", email: "nena@pharmacrm.test", who: "Nena Gutierrez", role: "Rep · STC MD Telesales" },
  { email: "rico@pharmacrm.test", who: "Rico Padilla", role: "Rep · URO MD Telesales" },

  { group: "Sales · B&B", email: "ana@pharmacrm.test", who: "Ana Reyes", role: "Rep · B&B MD Telesales + B2C General" },
  { email: "paolo@pharmacrm.test", who: "Paolo Mendoza", role: "Team Lead · B&B MD Telesales" },
  { email: "lorna@pharmacrm.test", who: "Lorna Bautista", role: "Division Head · B&B" },

  { group: "Sales · B2B", email: "marlon@pharmacrm.test", who: "Marlon Yap", role: "Rep · B2B NBD" },
  { email: "dina@pharmacrm.test", who: "Dina Salazar", role: "Rep · B2B CRR" },
  { email: "noel@pharmacrm.test", who: "Noel Ramos", role: "Division Head · B2B" },

  { group: "Sales · HOS", email: "grace@pharmacrm.test", who: "Grace Lim", role: "Rep · HOS Hospital" },
  { email: "elmer@pharmacrm.test", who: "Elmer Tan", role: "Rep · HOS Telesales" },
  { email: "vicky@pharmacrm.test", who: "Vicky Ong", role: "Team Lead · HOS Hospital" },

  { group: "Sales · BID", email: "rosa@pharmacrm.test", who: "Rosa Ferrer", role: "Rep · BID Bidding" },

  { group: "Across the company", email: "mila@pharmacrm.test", who: "Mila Aguilar", role: "Management · approves orders, sees every division" },
  { email: "fely@pharmacrm.test", who: "Fely Domingo", role: "Finance Staff · verifies order payments" },
  { email: "bong@pharmacrm.test", who: "Bong Rivera", role: "Dispatch Staff · picks, packs, delivers" },

  { group: "Departments", email: "joy@pharmacrm.test", who: "Joy Navarro", role: "Department Staff · Finance" },
  { email: "iris@pharmacrm.test", who: "Iris Dela Cruz", role: "Department Staff · Inventory" },
  { email: "teresa@pharmacrm.test", who: "Teresa Abad", role: "Department Staff · Human Resource" },
  { email: "alex@pharmacrm.test", who: "Alex Soriano", role: "Department Staff · Regulatory Affairs" },
  { email: "karla@pharmacrm.test", who: "Karla Ilagan", role: "Department Staff · In-Licensing" },
  { email: "ruth@pharmacrm.test", who: "Ruth Sarmiento", role: "Department Staff · Pharmacy" },
  { email: "deo@pharmacrm.test", who: "Deo Castillo", role: "Department Staff · Executive Admin" },

  { group: "Admin", email: "ramon@pharmacrm.test", who: "Ramon Santos", role: "Executive · everything, read-only" },
  { email: "carmen@pharmacrm.test", who: "Carmen Villanueva", role: "Admin · every setting, owns the company" },
  { email: "jun@pharmacrm.test", who: "Jun Espino", role: "Developer Admin · apps, log, company, accounts" },
];

export async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : "/";
  const expired = params.expired === "1";
  const denied = params.denied === "1";
  const demo = process.env.SHOW_DEMO_ACCOUNTS === "1" ? DEMO_ACCOUNTS : [];
  const app = thisAppLabel();

  return (
    <main className="flex min-h-dvh items-start justify-center px-4 py-10 sm:items-center">
      <div className="w-full max-w-[25rem]">
        <div className="rounded-[3px] bg-sheet px-6 pt-6 pb-7 shadow-sheet sm:px-8">
          {/* No company name here, and not by omission: nobody has signed in
              yet, so which company this is isn't known. One sign-in page serves
              every company on the platform. The company's own name appears the
              moment there is a person to read it from.

              Which *app* is known, though, and is said plainly. Each one signs
              in separately, and a person should see what they are entering
              rather than read it off the address bar. The shell is every app at
              once, so it has no name of its own to add. */}
          <div className="border-b-[3px] border-double border-ink pb-3">
            {app ? (
              <>
                <p className="text-stamp text-ink-3 uppercase">{APP_NAME}</p>
                <p className="text-heading leading-tight">{app}</p>
              </>
            ) : (
              <p className="text-heading">{APP_NAME}</p>
            )}
          </div>
          <h1 className="mt-6 text-title">Sign in</h1>
          {expired && <p className="mt-1 text-ink-2">Your session ended. Sign in again to pick up where you left off.</p>}
          {denied && (
            <p className="mt-1 text-ink-2">
              The account you're signed in with doesn't work in {app ?? "this app"}. Sign in with one that does.
            </p>
          )}
          <LoginForm next={next} demo={demo} />
        </div>
        <p className="mt-4 text-center text-meta text-ink-3">Forgot your password? Ask your admin to reset it.</p>
      </div>
    </main>
  );
}
