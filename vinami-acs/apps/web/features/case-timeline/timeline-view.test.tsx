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
  },
];

describe("TimelineView", () => {
  it("supports deterministic chronological order", () => {
    render(<TimelineView events={events} />);
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent(
      "Clinical case opened",
    );
    fireEvent.change(screen.getByLabelText("Order"), {
      target: { value: "oldest" },
    });
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent(
      "Patient registered",
    );
  });
});
