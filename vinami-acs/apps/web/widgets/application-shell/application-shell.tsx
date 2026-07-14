import type { ReactNode } from "react";
import type { IdentityView } from "@web/entities/identity/model";
import { ClinicalSidebar } from "@web/widgets/clinical-sidebar/clinical-sidebar";
import { CommandHeader } from "@web/widgets/command-header/command-header";

export function ApplicationShell({
  identity,
  children,
}: {
  identity: IdentityView | null;
  children: ReactNode;
}) {
  return (
    <div className="vm-shell">
      <a className="vm-skip-link" href="#main-content">
        Skip to main content
      </a>
      <ClinicalSidebar />
      <div className="vm-shell__workspace">
        <CommandHeader identity={identity} />
        <main id="main-content" className="vm-main" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
