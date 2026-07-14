import { VinamiApiError } from "@vinami/api-client";
import type { z } from "zod";

export function parseContract<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (result.success) return result.data;
  console.warn("vinami_contract_mismatch", {
    issueCount: result.error.issues.length,
  });
  throw new VinamiApiError(
    "malformed",
    "The clinical service returned information that does not match the verified contract.",
    null,
    null,
    false,
  );
}
