"use client";

import { addPhoto, removePhoto, type InventoryPhoto } from "@/src/modules/inventory/actions/inventory";
import { AddPhoto } from "@/src/platform/ui/photo-field";

// A delivery's or a package's photos (Step 4B): the shared Add photo control, sent as soon as one is picked.
export function RecordPhotos({ targetType, targetId, photos, canAdd, max = 10, label = "Photos (optional)" }: {
  targetType: "delivery" | "package";
  targetId: string;
  photos: InventoryPhoto[];
  canAdd: boolean;
  max?: number;
  label?: string;
}) {
  return (
    <AddPhoto photos={photos} max={max} label={label} readOnly={!canAdd}
      upload={(form) => addPhoto(targetType, targetId, form)} remove={(id) => removePhoto(id)} />
  );
}
