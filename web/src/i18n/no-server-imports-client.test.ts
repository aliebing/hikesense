import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const isClient = (src: string) => /^\s*(\/\*[\s\S]*?\*\/\s*|\/\/.*\n\s*)*["']use client["']/.test(src);

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return files(p);
    return /\.(ts|tsx)$/.test(n) && !/\.test\.tsx?$/.test(n) ? [p] : [];
  });
}

function resolveModule(from: string, spec: string): string | null {
  const base = resolve(dirname(from), spec);
  for (const c of [base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts"), join(base, "index.tsx")]) {
    if (existsSync(c) && statSync(c).isFile()) return c;
  }
  return null;
}

// A server component that calls a function exported from a "use client" module crashes at runtime
// (Next only hands out client references there). Such helpers belong in a plain module.
it("server files under app/ import only components and types from client modules", () => {
  const offenders: string[] = [];
  for (const f of files(join(process.cwd(), "src/app"))) {
    const src = readFileSync(f, "utf8");
    if (isClient(src)) continue;
    for (const m of src.matchAll(/import\s+(?!type\b)([^;]*?)\s+from\s+["'](\.[^"']*)["']/g)) {
      const target = resolveModule(f, m[2]);
      if (!target || !isClient(readFileSync(target, "utf8"))) continue;
      const named = /\{([^}]*)\}/.exec(m[1])?.[1] ?? "";
      const values = named.split(",").map((x) => x.trim()).filter((x) => x && !x.startsWith("type "))
        // components (PascalCase) are rendered, so a client reference is fine; functions and constants are not
        .filter((x) => !/^[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*$/.test(x.split(/\s+as\s+/)[0]));
      if (values.length > 0) offenders.push(`${f} imports ${values.join(", ")} from ${m[2]}`);
    }
  }
  expect(offenders).toEqual([]);
});
