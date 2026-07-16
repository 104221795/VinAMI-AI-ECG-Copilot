import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AuditTable } from "./audit-table";

describe("AuditTable", () => {
  it("is read-only and keeps correlation inside technical details", () => {
    render(
      <AuditTable
        value={{
          items: [
            {
              id: "a",
              actor: "ACT-123",
              actorRole: "physician",
              actorRoles: ["physician"],
              action: "case:open",
              resource: "ClinicalCase",
              resourceId: "cbbc0872-798f-40c5-83e3-64d66176e73b",
              outcome: "success",
              priorVersion: 0,
              resultingVersion: 1,
              requestSource: "api",
              timestamp: "2026-07-13T14:44:00Z",
              reason: null,
              correlationId: "corr",
              causationId: null,
              identityProvider: "development",
              authenticationMethod: "fixture",
              idempotencyKey: "idempotent-1",
              authorizationResult: "authorized",
              correctionStatus: "original",
              sourceRecordVersion: 1,
            },
          ],
          page: 1,
          pageSize: 25,
          total: 1,
        }}
      />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /delete|edit/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Technical details")).toBeInTheDocument();
  });
});
