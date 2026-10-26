"use server";

// The shared kit's, so every module does it the same way (decided 2026-10-26, DRY).
export { saveMyPhoto, removeMyPhoto, savePersonPhoto, removePersonPhoto, saveProfile } from "@/src/platform/actions/account";
export type { Profile, ProfileInput } from "@/src/platform/actions/account";
