import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const source =
  process.env.VINAMI_OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json";
const targetDirectory = path.resolve("packages/contracts");

function sortObject(value) {
  if (Array.isArray(value)) return value.map(sortObject);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, sortObject(child)]),
    );
  }
  return value;
}

const response = await fetch(source, {
  headers: { Accept: "application/json" },
});
if (!response.ok)
  throw new Error(`OpenAPI snapshot failed with HTTP ${response.status}`);
const schema = sortObject(await response.json());
const serialized = `${JSON.stringify(schema, null, 2)}\n`;
const checksum = createHash("sha256").update(serialized).digest("hex");

await mkdir(targetDirectory, { recursive: true });
await writeFile(path.join(targetDirectory, "openapi.json"), serialized, "utf8");
await writeFile(
  path.join(targetDirectory, "openapi.sha256"),
  `${checksum}\n`,
  "utf8",
);
process.stdout.write(`${checksum}\n`);
