import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { loadIdentitySafe } from "@web/features/identity-session/data";
import { publicConfig } from "@web/shared/config/public";
import { QueryProvider } from "@web/shared/query/query-provider";
import { ApplicationShell } from "@web/widgets/application-shell/application-shell";

export const metadata: Metadata = {
  title: {
    default: publicConfig.productName,
    template: `%s | ${publicConfig.productName}`,
  },
  description:
    "Research-use clinical workflow interface for suspected ACS cases",
  robots: { index: false, follow: false },
};

// Identity and clinical reads are actor-specific and must never be frozen at image build time.
export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const identity = await loadIdentitySafe();
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <ApplicationShell identity={identity}>{children}</ApplicationShell>
        </QueryProvider>
      </body>
    </html>
  );
}
