"use client";

import { Camera } from "lucide-react";
import { Modal } from "../ui/modal";
import { useState } from "react";
import { PhotoPicker } from "./photo-picker";
import { removeMyPhoto, saveMyPhoto } from "../actions/account";

/** A camera on the corner of the profile's picture: the picker in a dialog. */
export function PictureButton({ name, id, photoAt }: { name: string; id: string; photoAt: string | null }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Change your picture"
        title="Change profile photo"
        className="absolute right-0 bottom-0 grid size-8 place-items-center rounded-full border border-rule bg-sheet text-ink-2 shadow-sheet transition-colors hover:bg-mint hover:text-ink"
      >
        <Camera className="size-4" aria-hidden />
      </button>
      <Modal open={open} title="Profile photo" footer={null} onCancel={() => setOpen(false)} width={440}>
        <p className="mb-4 text-meta text-ink-3">It appears wherever your name does, for the people you work with. Without one, your initials do.</p>
        <PhotoPicker name={name} id={id} photoAt={photoAt} whose="your" onSave={saveMyPhoto} onRemove={removeMyPhoto} />
      </Modal>
    </>
  );
}
