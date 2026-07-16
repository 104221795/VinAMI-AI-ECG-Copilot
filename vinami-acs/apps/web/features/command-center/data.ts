import type { CommandCenterQuery, VinamiApiClient } from "@vinami/api-client";
import { parseContract } from "@web/shared/api/parse";
import { commandCenterPageSchema, type CommandCenterPageView } from "./model";

export async function loadCommandCenterWith(
  api: VinamiApiClient,
  query: CommandCenterQuery,
): Promise<CommandCenterPageView> {
  return parseContract(
    commandCenterPageSchema,
    await api.getCommandCenter(query),
  );
}
