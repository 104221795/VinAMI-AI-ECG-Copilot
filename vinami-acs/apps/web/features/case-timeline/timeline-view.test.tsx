import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TimelineView } from "./timeline-view";

const events = [
  {
    id: "1",
    title: "Patient registered",
    eventType: "PatientRegistered",
    occurredAt: "2026-07-13T14:40:00Z",
    recordedAt: "2026-07-13T14:40:01Z",
    source: "outbox",
    actorId: null,
    correlationId: "corr-1",
    causationId: null,
    sourceRecordId: null,
    sourceRecordVersion: 1,
    correctionStatus: "original",
    dataClassification: "clinical",
  },
  {
    id: "2",
    title: "Clinical case opened",
    eventType: "ClinicalCaseOpened",
    occurredAt: "2026-07-13T14:44:00Z",
    recordedAt: "2026-07-13T14:44:01Z",
    source: "outbox",
    actorId: null,
    correlationId: "corr-2",
    causationId: null,
    sourceRecordId: null,
    sourceRecordVersion: 1,
    correctionStatus: "original",
    dataClassification: "clinical",
  },
];

describe("TimelineView", () => {
  it("supports deterministic chronological order", () => {
    render(
      <TimelineView
        value={{ items: events, page: 1, pageSize: 25, total: 2 }}
      />,
    );
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent(
      "Mở ca ACS nghi ngờ",
    );
    fireEvent.change(screen.getByLabelText("Thứ tự"), {
      target: { value: "oldest" },
    });
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent(
      "Đăng ký bệnh nhân",
    );
  });
});
