import "server-only";
import type { TroponinWorkspaceView } from "@web/entities/troponin/model";
import { createServerApiClient } from "@web/shared/api/client";

export async function loadTroponinWorkspace(
  caseId: string,
): Promise<TroponinWorkspaceView> {
  return (await createServerApiClient().getTroponinWorkspace(
    caseId,
  )) as TroponinWorkspaceView;
}
