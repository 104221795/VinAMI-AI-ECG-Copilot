"use client";

import {
  Activity,
  ClipboardList,
  FileClock,
  HeartPulse,
  ListTodo,
  Stethoscope,
  ServerCog,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { publicConfig } from "@web/shared/config/public";

function navClass(active: boolean) {
  return `vm-nav-link${active ? " vm-nav-link--active" : ""}`;
}

export function ClinicalSidebar() {
  const pathname = usePathname();
  const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
  const caseId = caseMatch?.[1];
  return (
    <aside className="vm-sidebar" aria-label="Primary navigation">
      <div className="vm-brand">
        <span className="vm-brand__mark" aria-hidden="true">
          <HeartPulse size={21} />
        </span>
        <div>
          <strong>{publicConfig.productName}</strong>
          <span>{publicConfig.organizationName}</span>
        </div>
      </div>
      <nav>
        <p className="vm-nav-label">Clinical operations</p>
        <Link
          href="/command-center"
          className={navClass(pathname === "/command-center")}
        >
          <ClipboardList size={18} /> Command Center
        </Link>
        {caseId && (
          <div className="vm-case-nav">
            <p className="vm-nav-label">Selected case</p>
            <Link
              href={`/cases/${caseId}/workflow`}
              className={navClass(pathname.endsWith("/workflow"))}
            >
              <ListTodo size={18} /> Tasks and Alerts
            </Link>
            <Link
              href={`/cases/${caseId}/clinical-reasoning`}
              className={navClass(pathname.endsWith("/clinical-reasoning"))}
            >
              <Stethoscope size={18} /> Clinical Reasoning
            </Link>
            <Link
              href={`/cases/${caseId}`}
              className={navClass(pathname === `/cases/${caseId}`)}
            >
              <Activity size={18} /> Overview
            </Link>
            <Link
              href={`/cases/${caseId}/timeline`}
              className={navClass(pathname.endsWith("/timeline"))}
            >
              <FileClock size={18} /> Timeline
            </Link>
            <Link
              href={`/cases/${caseId}/audit`}
              className={navClass(pathname.endsWith("/audit"))}
            >
              <ShieldCheck size={18} /> Audit
            </Link>
          </div>
        )}
        <p className="vm-nav-label vm-nav-label--system">System</p>
        <Link
          href="/system-health"
          className={navClass(pathname === "/system-health")}
        >
          <ServerCog size={18} /> System Health
        </Link>
      </nav>
      <footer>
        <span className="vm-research-dot" />
        <div>
          <strong>Research-use prototype</strong>
          <span>Not for patient-care decisions</span>
        </div>
      </footer>
    </aside>
  );
}
