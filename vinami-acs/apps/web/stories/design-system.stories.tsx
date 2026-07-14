import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { AlertCircle, RefreshCw } from "lucide-react";
import {
  Badge,
  Button,
  ClinicalCard,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  MetricTile,
  OfflineState,
  PriorityBadge,
  SearchField,
  StaleDataBanner,
  StatusBadge,
  TechnicalDetailsDisclosure,
  TimelineItem,
} from "@vinami/ui";

const meta = {
  title: "Clinical Foundation/Design System",
  parameters: { layout: "padded" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Normal: Story = {
  render: () => (
    <div className="vm-section-stack">
      <div className="vm-case-header">
        <Badge>Development</Badge>
        <Badge tone="warning">Research MVP</Badge>
        <StatusBadge status="open" />
        <PriorityBadge priority="urgent" />
      </div>
      <ClinicalCard
        title="Patient and encounter"
        action={
          <Button>
            <RefreshCw size={16} />
            Refresh
          </Button>
        }
      >
        <dl className="vm-definition-list">
          <dt>Patient</dt>
          <dd>SYN-R1-001</dd>
          <dt>Location</dt>
          <dd>Emergency Department</dd>
        </dl>
      </ClinicalCard>
      <div style={{ display: "flex", gap: 1 }}>
        <MetricTile label="Active cases" value={3} />
        <MetricTile label="Last refreshed" value="just now" />
      </div>
    </div>
  ),
};
export const Loading: Story = { render: () => <LoadingSkeleton lines={7} /> };
export const Empty: Story = {
  render: () => (
    <EmptyState
      title="No active cases"
      description="No PostgreSQL-backed cases match the current filters."
    />
  ),
};
export const Error: Story = {
  render: () => (
    <ErrorState
      title="Clinical service unavailable"
      description="The server could not complete the request. No clinical action was taken."
      correlationId="7fc88d15-f71f-4baf-b65a-741d05058f08"
      onRetry={() => undefined}
    />
  ),
};
export const Offline: Story = {
  render: () => <OfflineState onRetry={() => undefined} />,
};
export const Stale: Story = {
  render: () => <StaleDataBanner updatedLabel="8 minutes ago" />,
};
export const CriticalStatus: Story = {
  render: () => (
    <div className="vm-case-header">
      <PriorityBadge priority="critical" />
      <Badge tone="critical">
        <AlertCircle size={14} /> Critical state
      </Badge>
    </div>
  ),
};
export const LongText: Story = {
  render: () => (
    <ClinicalCard title="Long operational content">
      <p>
        This deliberately long lifecycle explanation checks wrapping without
        shrinking clinical text or creating uncontrolled horizontal scrolling
        across narrow workspaces.
      </p>
      <TechnicalDetailsDisclosure>
        <code>7fc88d15-f71f-4baf-b65a-741d05058f08</code>
      </TechnicalDetailsDisclosure>
    </ClinicalCard>
  ),
};
export const UnknownEnum: Story = {
  render: () => <Badge tone="neutral">Unknown (future_status)</Badge>,
};
export const NarrowViewport: Story = {
  parameters: { viewport: { defaultViewport: "mobile1" } },
  render: () => (
    <div style={{ width: 320 }}>
      <SearchField placeholder="Patient or case reference" />
      <TimelineItem
        title="Clinical case opened"
        timestamp="13 Jul 2026, 14:44 UTC"
        actor="ACT-12345678"
        last
      />
    </div>
  ),
};
