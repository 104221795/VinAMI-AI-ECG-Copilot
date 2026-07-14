import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile, rm } from "node:fs/promises";
import path from "node:path";

const schemaPath = path.resolve("packages/contracts/openapi.json");
const checksumPath = path.resolve("packages/contracts/openapi.sha256");
const generatedPath = path.resolve("packages/contracts/src/generated.ts");
const checkPath = path.resolve("packages/contracts/src/generated.check.ts");

const schema = await readFile(schemaPath);
const expectedChecksum = (await readFile(checksumPath, "utf8")).trim();
const actualChecksum = createHash("sha256").update(schema).digest("hex");
if (actualChecksum !== expectedChecksum)
  throw new Error("OpenAPI snapshot checksum mismatch");

const generator = path.resolve("node_modules/openapi-typescript/bin/cli.js");
try {
  execFileSync(
    process.execPath,
    [generator, schemaPath, "--output", checkPath],
    { stdio: "inherit" },
  );
  const [generated, checked] = await Promise.all([
    readFile(generatedPath, "utf8"),
    readFile(checkPath, "utf8"),
  ]);
  if (generated !== checked)
    throw new Error("Generated API contract has drifted");
} finally {
  await rm(checkPath, { force: true });
}

process.stdout.write(`OpenAPI contract verified: ${actualChecksum}\n`);
