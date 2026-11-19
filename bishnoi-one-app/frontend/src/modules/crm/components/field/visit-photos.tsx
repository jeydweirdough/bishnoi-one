"use client";

import { addVisitPhoto, removeVisitPhoto, type VisitPhoto } from "@/src/modules/crm/actions/field";
import { AddPhoto } from "@/src/platform/ui/photo-field";

// A visit's photos (Step 4B): thumbnails, and the shared Add photo control for whoever may change the visit.
export function VisitPhotos({ visitId, photos, canAdd }: { visitId: string; photos: VisitPhoto[]; canAdd: boolean }) {
  return (
    <AddPhoto photos={photos} max={10} label="Photos (optional)" readOnly={!canAdd}
      upload={(form) => addVisitPhoto(visitId, form)} remove={(id) => removeVisitPhoto(id)} />
  );
}
