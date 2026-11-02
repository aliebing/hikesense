import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return n === "i18n" ? [] : sources(p);
    return /\.(ts|tsx)$/.test(n) && !/\.test\.tsx?$/.test(n) ? [p] : [];
  });
}

it("no source file outside i18n/ hard-codes the German Intl locale", () => {
  const offenders = sources(join(process.cwd(), "src")).filter((f) => readFileSync(f, "utf8").includes('"de-DE"'));
  expect(offenders).toEqual([]);
});

/** Strips comments; string literals stay. */
const withoutComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");

// Data values and parsers that legitimately contain German (stored values, backend vocabulary, filename regexes).
const ALLOWED = [/"geprüft"/, /"Eigenes Foto"/];

it("no German umlaut or ß in string literals outside i18n/ (texts belong in the catalogs)", () => {
  const offenders: string[] = [];
  for (const f of sources(join(process.cwd(), "src"))) {
    const lines = withoutComments(readFileSync(f, "utf8")).split("\n");
    lines.forEach((line, i) => {
      if (!/["'`][^"'`\n]*[äöüÄÖÜß]/.test(line)) return;
      if (ALLOWED.some((a) => a.test(line))) return;
      offenders.push(`${f.replace(process.cwd() + "/", "")}:${i + 1}: ${line.trim()}`);
    });
  }
  expect(offenders).toEqual([]);
});
