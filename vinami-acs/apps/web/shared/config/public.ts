export const publicConfig = {
  productName:
    process.env.NEXT_PUBLIC_PRODUCT_NAME ?? "VinAMI ACS Operating System",
  organizationName:
    process.env.NEXT_PUBLIC_ORGANIZATION_NAME ?? "VinAMI Clinical Research",
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? "Development",
  researchUse:
    (process.env.NEXT_PUBLIC_RESEARCH_USE ?? "true").toLowerCase() === "true",
} as const;
