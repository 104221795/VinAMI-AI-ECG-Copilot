// @vitest-environment node
import { readFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";

const root = resolve(process.cwd());
const files = execFileSync("rg", ["--files", "apps/web", "packages"], {
  cwd: root,
  encoding: "utf8",
})
  .split(/\r?\n/)
  .filter((name) => /\.(ts|tsx|js|mjs)$/.test(name));
const source = files.map(
  (name) => [name, readFileSync(resolve(root, name), "utf8")] as const,
);
const productionSource = source.filter(
  ([file]) => !/(?:e2e|stories|\.test\.|\.spec\.|generated\.ts)/.test(file),
);

describe("frontend architecture boundaries", () => {
  it("does not import Python, ORM, model runtime, or database clients", () => {
    for (const [file, content] of source)
      expect(content, file).not.toMatch(
        /from ["'](?:vinami\.|apps\.api|sqlalchemy|torch|psycopg|pg)["']/,
      );
  });
  it("does not persist access tokens in localStorage", () => {
    for (const [file, content] of source)
      expect(content, file).not.toMatch(
        /localStorage\.(?:setItem|getItem).*token/i,
      );
  });
  it("keeps server-only modules outside Client Components", () => {
    for (const [file, content] of source) {
      if (!/^\s*["']use client["'];/m.test(content)) continue;
      expect(content, file).not.toMatch(
        /(?:server-data|shared\/api\/client|shared\/config\/server)/,
      );
    }
  });
  it("does not create unapproved future clinical route pages", () => {
    const routes = files
      .filter((file) => file.endsWith("page.tsx"))
      .map((file) => relative("apps/web/app", file).replaceAll("\\", "/"));
    expect(routes.join("\n")).not.toMatch(
      /triage|vitals|pathway|tasks|alerts/i,
    );
    expect(routes.filter((route) => /ecg/i.test(route))).toEqual([
      "(clinical)/cases/[caseId]/ecg/page.tsx",
    ]);
    expect(routes.filter((route) => /troponin/i.test(route))).toEqual([
      "(clinical)/cases/[caseId]/troponin/page.tsx",
    ]);
  });
  it("does not embed prohibited clinical claims", () => {
    const combined = productionSource
      .map(([, content]) => content)
      .join("\n")
      .toLowerCase();
    expect(combined).not.toContain("ami ruled out");
    expect(combined).not.toContain("patient diagnosed by ai");
    expect(combined).not.toContain("cath lab activated by ai");
    expect(combined).not.toContain("clinically validated");
  });
});
