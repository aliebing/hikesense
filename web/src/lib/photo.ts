import type { SupabaseClient } from "@supabase/supabase-js";
import type { Photo } from "./data";

/** Own photos (Spec §11): private, EXIF/GPS removed in the browser before anything is uploaded. */
export const MAX_BYTES = 10 * 1024 * 1024;
export const MAX_SIDE = 2560;
export const QUALITY = 0.85;
export const BUCKET = "uploads";
export const SIGNED_URL_SECONDS = 3600;

export const MSG_HEIC = "HEIC wird nicht unterstützt – bitte als JPEG exportieren";
export const MSG_TOO_BIG = "Foto ist größer als 10 MB";
export const MSG_TYPE = "Nur JPEG, PNG oder WebP werden unterstützt";
export const MSG_REENCODE = "Das Foto konnte nicht verarbeitet werden";

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

/** Turns the chosen image into JPEG bytes (the browser implementation draws it on a canvas). */
export type Reencode = (file: File) => Promise<Blob>;

/** Re-encodes through a canvas: only pixels survive, so EXIF, GPS, XMP and thumbnails are gone. */
export const canvasReencode: Reencode = async (file) => {
  const bitmap = await createImageBitmap(file); // honours the EXIF orientation before it is dropped
  try {
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
    if (!blob) throw new Error("toBlob failed");
    return blob;
  } finally {
    bitmap.close();
  }
};

function readBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(new Uint8Array(r.result as ArrayBuffer));
    r.onerror = () => reject(r.error);
    r.readAsArrayBuffer(blob);
  });
}

/**
 * True when the bytes are not a plain JPEG or carry an APP1 segment (EXIF or XMP, both can hold GPS).
 * Walks the marker segments up to the start of the scan.
 */
export function hasMetadata(bytes: Uint8Array): boolean {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return true;
  let i = 2;
  while (i + 4 <= bytes.length) {
    if (bytes[i] !== 0xff) return true;
    const marker = bytes[i + 1];
    if (marker === 0xff) {
      i += 1; // fill byte
      continue;
    }
    if (marker === 0xda || marker === 0xd9) return false; // start of scan: image data only from here
    if (marker === 0xe1) return true; // APP1: EXIF / XMP
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) {
      i += 2; // standalone markers without length
      continue;
    }
    i += 2 + ((bytes[i + 2] << 8) | bytes[i + 3]);
  }
  return false;
}

/** Checks type and size, re-encodes and verifies the result carries no metadata. Throws a German message. */
export async function prepareUpload(file: File, reencode: Reencode = canvasReencode): Promise<Blob> {
  const name = file.name.toLowerCase();
  if (/image\/hei[cf]/.test(file.type) || /\.hei[cf]$/.test(name)) throw new Error(MSG_HEIC);
  if (!ALLOWED.includes(file.type)) throw new Error(MSG_TYPE);
  if (file.size > MAX_BYTES) throw new Error(MSG_TOO_BIG);
  let out: Blob;
  try {
    out = await reencode(file);
    if (hasMetadata(await readBytes(out))) throw new Error("metadata left");
  } catch {
    // never fall back to the original: it may carry GPS
    throw new Error(MSG_REENCODE);
  }
  return out;
}

const OWN_COLUMNS = "id,url,author,license";

/** The signed-in user's photos of one trail with signed URLs (1 h). Empty on any error: own photos are optional. */
export async function listOwnPhotos(sb: SupabaseClient, trailId: string): Promise<Photo[]> {
  try {
    const { data, error } = await sb.from("photos").select(OWN_COLUMNS).eq("trail_id", trailId).eq("source", "upload").order("id");
    if (error || !data?.length) return [];
    const paths = data.map((r) => r.url as string);
    const signed = await sb.storage.from(BUCKET).createSignedUrls(paths, SIGNED_URL_SECONDS);
    if (signed.error || !signed.data) return [];
    const urlByPath = new Map(signed.data.map((s) => [s.path, s.signedUrl] as const));
    return data.flatMap((r) => {
      const url = urlByPath.get(r.url as string);
      if (!url) return [];
      return [
        {
          url,
          thumb_url: url,
          author: r.author as string,
          license: r.license as string,
          license_url: null,
          page_url: null,
          own: { id: r.id as number, path: r.url as string },
        },
      ];
    });
  } catch {
    return [];
  }
}

/** crypto.randomUUID only exists in secure contexts (not over plain HTTP on the LAN); getRandomValues does. */
function fileId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Uploads the prepared JPEG to `<user_id>/<trail_id>/<uuid>.jpg` and records it. Throws a German message. */
export async function uploadOwnPhoto(sb: SupabaseClient, userId: string, trailId: string, blob: Blob): Promise<void> {
  const path = `${userId}/${trailId}/${fileId()}.jpg`;
  const up = await sb.storage.from(BUCKET).upload(path, blob, { contentType: "image/jpeg" });
  if (up.error) throw new Error("Hochladen hat nicht geklappt – bitte versuche es noch einmal");
  const ins = await sb.from("photos").insert({ trail_id: trailId, source: "upload", url: path, author: "Eigenes Foto", license: "privat" });
  if (ins.error) {
    await sb.storage.from(BUCKET).remove([path]); // no orphan file without its row
    throw new Error("Hochladen hat nicht geklappt – bitte versuche es noch einmal");
  }
}

/** Deletes row and file of one own photo. Throws a German message. */
export async function deleteOwnPhoto(sb: SupabaseClient, own: { id: number; path: string }): Promise<void> {
  const del = await sb.from("photos").delete().eq("id", own.id);
  if (del.error) throw new Error("Löschen hat nicht geklappt – bitte versuche es noch einmal");
  await sb.storage.from(BUCKET).remove([own.path]);
}
