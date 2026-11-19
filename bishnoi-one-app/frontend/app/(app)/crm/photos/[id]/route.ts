import { photoRoute } from "@/src/platform/photos/route";

// A visit's photo (Step 4B).
export const GET = photoRoute((id) => `/photos/${id}`);
