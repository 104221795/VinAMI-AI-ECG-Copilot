import { LoadingSkeleton } from "@vinami/ui";

export default function Loading() {
  return (
    <LoadingSkeleton
      lines={8}
      label="Loading verified clinical workflow information"
    />
  );
}
