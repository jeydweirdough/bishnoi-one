import { photoRoute } from "@/src/platform/photos/route";

// A delivery's or a package's photo (Step 4B).
export const GET = photoRoute((id) => `/inventory/photos/${id}`);
