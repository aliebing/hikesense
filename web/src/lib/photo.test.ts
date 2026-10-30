import { join } from "node:path";
import { readFileSync } from "node:fs";
import { hasMetadata, MSG_HEIC, MSG_REENCODE, MSG_TOO_BIG, MSG_TYPE, MAX_BYTES, prepareUpload } from "./photo";

const gpsBytes = new Uint8Array(readFileSync(join(__dirname, "fixtures", "gps.jpg")));
const fileOf = (parts: BlobPart[], name: string, type: string) => new File(parts, name, { type });

// What a canvas produces: SOI, JFIF (APP0), a quantisation table, start of scan, EOI — no APP1.
const CLEAN_JPEG = new Uint8Array([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x04, 0x4a, 0x46, 0xff, 0xdb, 0x00, 0x04, 0x01, 0x02, 0xff, 0xda, 0x00, 0x04, 0x00, 0x00, 0x12, 0x34, 0xff, 0xd9,
]);

const bytesOf = (b: Blob) =>
  new Promise<Uint8Array>((res) => {
    const r = new FileReader();
    r.onload = () => res(new Uint8Array(r.result as ArrayBuffer));
    r.readAsArrayBuffer(b);
  });

it("fixture really carries GPS EXIF (APP1/Exif)", () => {
  expect(hasMetadata(gpsBytes)).toBe(true);
  expect(new TextDecoder("latin1").decode(gpsBytes)).toContain("Exif");
});

it("strips exif before upload", async () => {
  const input = fileOf([gpsBytes], "wald.jpg", "image/jpeg");
  const reencode = vi.fn(async () => new Blob([CLEAN_JPEG], { type: "image/jpeg" }));
  const out = await prepareUpload(input, reencode);
  expect(reencode).toHaveBeenCalledWith(input);
  const bytes = await bytesOf(out);
  expect(hasMetadata(bytes)).toBe(false);
  expect(new TextDecoder("latin1").decode(bytes)).not.toContain("Exif");
  expect(Array.from(bytes)).toEqual(Array.from(CLEAN_JPEG));
});

it("never uploads the original when re-encoding leaves metadata or fails", async () => {
  const input = fileOf([gpsBytes], "wald.jpg", "image/jpeg");
  await expect(prepareUpload(input, async () => new Blob([gpsBytes]))).rejects.toThrow(MSG_REENCODE);
  await expect(prepareUpload(input, async () => Promise.reject(new Error("decode")))).rejects.toThrow(MSG_REENCODE);
});

it("rejects heic and oversized", async () => {
  const reencode = vi.fn();
  await expect(prepareUpload(fileOf(["x"], "IMG_1.HEIC", "image/heic"), reencode)).rejects.toThrow(MSG_HEIC);
  await expect(prepareUpload(fileOf(["x"], "IMG_1.heic", ""), reencode)).rejects.toThrow(MSG_HEIC);
  await expect(prepareUpload(fileOf(["x"], "a.gif", "image/gif"), reencode)).rejects.toThrow(MSG_TYPE);
  const big = fileOf([new Uint8Array(MAX_BYTES + 1)], "big.jpg", "image/jpeg");
  await expect(prepareUpload(big, reencode)).rejects.toThrow(MSG_TOO_BIG);
  expect(reencode).not.toHaveBeenCalled();
});

it("accepts png and webp up to exactly 10 MB", async () => {
  const reencode = async () => new Blob([CLEAN_JPEG]);
  await expect(prepareUpload(fileOf([new Uint8Array(MAX_BYTES)], "a.png", "image/png"), reencode)).resolves.toBeInstanceOf(Blob);
  await expect(prepareUpload(fileOf(["x"], "a.webp", "image/webp"), reencode)).resolves.toBeInstanceOf(Blob);
});

test("uploadOwnPhoto works without crypto.randomUUID (plain HTTP on the LAN)", async () => {
  const { uploadOwnPhoto } = await import("./photo");
  const paths: string[] = [];
  const sb = {
    storage: { from: () => ({ upload: async (p: string) => (paths.push(p), { error: null }), remove: async () => ({}) }) },
    from: () => ({ insert: async () => ({ error: null }) }),
  };
  const orig = crypto.randomUUID;
  Object.defineProperty(crypto, "randomUUID", { configurable: true, value: undefined });
  try {
    await uploadOwnPhoto(sb as never, "u1", "t1", new Blob(["x"]));
  } finally {
    Object.defineProperty(crypto, "randomUUID", { configurable: true, value: orig });
  }
  expect(paths[0]).toMatch(/^u1\/t1\/[0-9a-f]{32}\.jpg$/);
});

it("fails closed on a truncated JPEG (no start of scan reached)", () => {
  // SOI + APP0 + the start of a quantisation table header, cut off before its length bytes
  expect(hasMetadata(CLEAN_JPEG.slice(0, 10))).toBe(true);
  // segments end without start of scan
  expect(hasMetadata(CLEAN_JPEG.slice(0, 14))).toBe(true);
  expect(hasMetadata(CLEAN_JPEG)).toBe(false);
});
