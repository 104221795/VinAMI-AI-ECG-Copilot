import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActiveCaseTable } from "./active-case-table";

const row = {
  caseId: "cbbc0872-798f-40c5-83e3-64d66176e73b",
  caseReference: "CASE-CBBC0872",
  encounterId: "2a46ec31-5371-4424-99f0-c3aee1399e69",
  encounterReference: "ENC-2A46EC31",
  patientId: "8b78f75f-dfce-4ed4-948a-b25e186b645a",
  patientReference: "SYN-R1-001",
  demographics: "Age 45-64 · female",
  location: "Emergency Department",
  priority: "urgent",
  status: "open",
  openedAt: "2026-07-13T14:44:00Z",
  updatedAt: "2026-07-13T14:44:00Z",
  aggregateVersion: 1,
  partial: false,
};

describe("ActiveCaseTable", () => {
  it("shows only real R1 fields and supports keyboard selection", () => {
    const onSelect = vi.fn();
    render(
      <ActiveCaseTable
        rows={[row]}
        referenceTime="2026-07-13T15:00:00Z"
        onSelect={onSelect}
      />,
    );
    expect(screen.getByText("SYN-R1-001")).toBeInTheDocument();
    expect(screen.queryByText(/troponin/i)).not.toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("row", { name: /SYN-R1-001/i }), {
      key: "Enter",
    });
    expect(onSelect).toHaveBeenCalledWith(row.caseId);
  });
});
