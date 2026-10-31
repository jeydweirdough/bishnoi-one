import type { ReactNode } from "react";
import { Brand } from "@/src/one/brand";

/** The sign-in pages' frame (forgot password, a link's new password, the first sign-in): the brand, a title, the form. */
export function SignInShell({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <div className="mx-auto flex min-h-[calc(100dvh-1.5rem)] max-w-[80rem] flex-col px-3 pt-4 pb-6 sm:min-h-[calc(100dvh-2.5rem)] sm:px-8">
        <Brand href="/login" />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[26rem]">
            <div className="text-center">
              <h1 className="text-[2rem] leading-[1.15] font-semibold tracking-[-0.02em] text-ink sm:text-[2.25rem]">{title}</h1>
              {intro && <p className="mx-auto mt-3 max-w-[23rem] text-sm leading-relaxed text-ink-2">{intro}</p>}
            </div>
            {children}
          </div>
        </div>
      </div>
    </main>
  );
}
