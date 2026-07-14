import * as Dialog from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleOff,
  Info,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldAlert,
  TriangleAlert,
  X,
} from "lucide-react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";

export type SemanticTone =
  "neutral" | "info" | "success" | "warning" | "critical" | "stale";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: SemanticTone;
}) {
  return <span className={`vm-badge vm-badge--${tone}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone: SemanticTone =
    normalized.includes("critical") || normalized.includes("failed")
      ? "critical"
      : normalized.includes("open") || normalized.includes("review")
        ? "info"
        : normalized.includes("ready") || normalized.includes("healthy")
          ? "success"
          : "neutral";
  return <Badge tone={tone}>{status.replaceAll("_", " ")}</Badge>;
}

export function PriorityBadge({ priority }: { priority: string }) {
  const tone: SemanticTone =
    priority === "critical"
      ? "critical"
      : priority === "urgent"
        ? "warning"
        : "neutral";
  return <Badge tone={tone}>{priority}</Badge>;
}

export function Button({
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`vm-button ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}

export function IconButton({
  label,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <Tooltip text={label}>
      <button className="vm-icon-button" aria-label={label} {...props}>
        {children}
      </button>
    </Tooltip>
  );
}

export function Tooltip({
  text,
  children,
}: {
  text: string;
  children: ReactNode;
}) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="vm-tooltip" sideOffset={6}>
            {text}
            <TooltipPrimitive.Arrow className="vm-tooltip__arrow" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export function ClinicalCard({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`vm-card ${className}`.trim()}>
      {(title || action) && (
        <header className="vm-card__header">
          {title ? <h2>{title}</h2> : <span />}
          {action}
        </header>
      )}
      <div className="vm-card__body">{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <header className="vm-page-header">
      <div>
        {eyebrow && <p className="vm-eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="vm-page-header__actions">{actions}</div>}
    </header>
  );
}

export function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="vm-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

export function SearchField({
  label = "Search",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <label className="vm-search">
      <span className="vm-sr-only">{label}</span>
      <Search aria-hidden="true" size={17} />
      <input type="search" {...props} />
    </label>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className="vm-pagination" aria-label="Case queue pages">
      <span>
        Page {page} of {pages}
      </span>
      <IconButton
        label="Previous page"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        <ChevronLeft size={18} />
      </IconButton>
      <IconButton
        label="Next page"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        <ChevronRight size={18} />
      </IconButton>
    </nav>
  );
}

export function LoadingSkeleton({
  lines = 5,
  label = "Loading clinical information",
}: {
  lines?: number;
  label?: string;
}) {
  return (
    <div className="vm-skeleton" role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="vm-state vm-state--empty">
      <CircleOff size={28} aria-hidden="true" />
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

export function ErrorState({
  title,
  description,
  correlationId,
  onRetry,
}: {
  title: string;
  description: string;
  correlationId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="vm-state vm-state--error" role="alert">
      <AlertCircle size={28} aria-hidden="true" />
      <h2>{title}</h2>
      <p>{description}</p>
      {onRetry && (
        <Button onClick={onRetry}>
          <RefreshCw size={16} /> Retry
        </Button>
      )}
      {correlationId && (
        <TechnicalDetailsDisclosure title="Technical reference">
          <code>Correlation {correlationId}</code>
        </TechnicalDetailsDisclosure>
      )}
    </div>
  );
}

export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  return (
    <ErrorState
      title="Connection unavailable"
      description="Check the network connection. Previously loaded information may be out of date."
      onRetry={onRetry}
    />
  );
}

export function StaleDataBanner({ updatedLabel }: { updatedLabel: string }) {
  return (
    <div className="vm-banner vm-banner--stale" role="status">
      <TriangleAlert size={17} aria-hidden="true" />
      <span>
        Displayed information may be stale. Last refreshed {updatedLabel}.
      </span>
    </div>
  );
}

export function TechnicalDetailsDisclosure({
  title = "Technical details",
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <details className="vm-technical">
      <summary>
        <Info size={15} aria-hidden="true" /> {title}
      </summary>
      <div>{children}</div>
    </details>
  );
}

export function TimelineItem({
  title,
  timestamp,
  detail,
  actor,
  last = false,
}: {
  title: string;
  timestamp: string;
  detail?: ReactNode;
  actor?: string;
  last?: boolean;
}) {
  return (
    <li className={`vm-timeline-item${last ? " vm-timeline-item--last" : ""}`}>
      <span className="vm-timeline-item__marker" aria-hidden="true" />
      <div>
        <div className="vm-timeline-item__heading">
          <strong>{title}</strong>
          <time>{timestamp}</time>
        </div>
        {actor && <p>Recorded by {actor}</p>}
        {detail}
      </div>
    </li>
  );
}

export function ConfirmationDialog({
  trigger,
  title,
  description,
  confirmLabel,
  onConfirm,
  destructive = false,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="vm-dialog__overlay" />
        <Dialog.Content className="vm-dialog">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close asChild>
            <IconButton label="Close dialog" className="vm-dialog__close">
              <X size={18} />
            </IconButton>
          </Dialog.Close>
          <footer>
            <Dialog.Close asChild>
              <Button>Cancel</Button>
            </Dialog.Close>
            <Dialog.Close asChild>
              <Button
                className={
                  destructive ? "vm-button--danger" : "vm-button--primary"
                }
                onClick={onConfirm}
              >
                {confirmLabel}
              </Button>
            </Dialog.Close>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function SafeActionButton({
  requiresConfirmation = true,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  requiresConfirmation?: boolean;
}) {
  return (
    <Button
      data-confirmation-required={requiresConfirmation ? "true" : "false"}
      {...props}
    >
      {children}
    </Button>
  );
}

export const StateIcon = {
  success: CheckCircle2,
  warning: ShieldAlert,
  loading: LoaderCircle,
};
