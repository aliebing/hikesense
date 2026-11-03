// Generates the PWA icons, apple-touch-icon and favicon PNGs from the HikeSense mark.
// The geometry mirrors src/components/Logo.tsx (keep both in sync). Run in web/: node scripts/make-icons.mjs
// The favicon.ico is then packed from the three favicon PNGs (e.g. Pillow) into src/app/favicon.ico.
import sharp from "sharp";
import { writeFileSync } from "node:fs";

const GROUND = "#1f3f27"; // the app's dark green (wald-dunkel)
const SUN = "M21 44 A37 37 0 1 1 93 38";
const MOUNTAIN = "M3 68 L36 43 L44 52 L67 28 L81 44 L85 42 L117 71";
const TRAIL = "M66 50 C 58 53, 54 55, 60 58 C 67 61, 62 66, 52 68 C 42 70, 38 74, 32 79";

/** size: canvas px; scale: share of the canvas width the mark takes; round: corner radius share. */
function svg({ size, scale, round = 0, trail = true, bold = 1 }) {
  const w = size * scale;
  const s = w / 120;
  const h = 92 * s;
  const x = (size - w) / 2;
  const y = (size - h) / 2 + 8 * s; // viewBox starts at y=-8
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <defs><linearGradient id="sun" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6b04a"/><stop offset="1" stop-color="#e47f1c"/></linearGradient></defs>
  <rect width="${size}" height="${size}" rx="${size * round}" fill="${GROUND}"/>
  <g transform="translate(${x} ${y}) scale(${s})">
    <path d="${SUN}" fill="none" stroke="url(#sun)" stroke-width="${5 * bold}" stroke-linecap="round"/>
    <path d="${MOUNTAIN}" fill="none" stroke="#ffffff" stroke-width="${5.5 * bold}" stroke-linejoin="miter" stroke-linecap="round"/>
    ${trail ? `<path d="${TRAIL}" fill="none" stroke="#a6dc7a" stroke-width="${3 * bold}" stroke-linecap="round"/>` : ""}
  </g>
</svg>`;
}

const png = (file, opts) => sharp(Buffer.from(svg(opts))).png({ compressionLevel: 9 }).toFile(file);

const out = process.argv[2] ?? "/tmp";
writeFileSync("public/icons/icon.svg", svg({ size: 512, scale: 0.8, round: 0.18 }));
await png("public/icons/icon-192.png", { size: 192, scale: 0.8, round: 0.18 });
await png("public/icons/icon-512.png", { size: 512, scale: 0.8, round: 0.18 });
// maskable: full-bleed ground, mark inside the 80 % safe circle
await png("public/icons/maskable-192.png", { size: 192, scale: 0.6 });
await png("public/icons/maskable-512.png", { size: 512, scale: 0.6 });
await png("public/icons/apple-touch-icon.png", { size: 180, scale: 0.74 });
// favicon sizes: no trail, bolder strokes so the mark survives 16 px
await png(`${out}/favicon-16.png`, { size: 16, scale: 0.92, round: 0.2, trail: false, bold: 1.8 });
await png(`${out}/favicon-32.png`, { size: 32, scale: 0.9, round: 0.2, trail: false, bold: 1.5 });
await png(`${out}/favicon-48.png`, { size: 48, scale: 0.88, round: 0.2, trail: false, bold: 1.3 });
