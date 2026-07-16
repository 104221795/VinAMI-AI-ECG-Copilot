import "server-only";
import type { CommandCenterQuery } from "@vinami/api-client";
import { createServerApiClient } from "@web/shared/api/client";
import { loadCommandCenterWith } from "./data";
import type { CommandCenterPageView } from "./model";

export function loadCommandCenter(
  query: CommandCenterQuery,
): Promise<CommandCenterPageView> {
  return loadCommandCenterWith(createServerApiClient(), query);
}
