import type { Metadata } from "next";
import { CompleteCaseWorkspace } from "@web/features/complete-case-workspace/complete-case-workspace";
import { loadCompleteCaseWorkspace } from "@web/features/complete-case-workspace/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "Clinical Case" };

export default async function CaseWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const value = await loadCompleteCaseWorkspace(caseId);
    return <CompleteCaseWorkspace caseId={caseId} initialValue={value} />;
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
