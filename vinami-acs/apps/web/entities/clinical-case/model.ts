export interface CaseQueueRowView {
  caseId: string;
  caseReference: string;
  encounterId: string;
  encounterReference: string;
  patientId: string | null;
  patientReference: string;
  demographics: string;
  location: string;
  priority: string;
  status: string;
  openedAt: string;
  updatedAt: string;
  aggregateVersion: number;
  partial: boolean;
}

export interface CaseQueueView {
  rows: CaseQueueRowView[];
  page: number;
  pageSize: number;
  total: number;
  partialCount: number;
  refreshedAt: string;
}

export interface CaseWorkspaceView {
  caseId: string;
  caseReference: string;
  encounterId: string;
  encounterReference: string;
  patientId: string;
  patientReference: string;
  patientReferenceSystem: string;
  demographics: string;
  location: string;
  arrivalAt: string;
  encounterStatus: string;
  priority: string;
  status: string;
  openingReason: string;
  openedAt: string;
  updatedAt: string;
  aggregateVersion: number;
}
