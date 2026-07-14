"use client";

import { SearchField } from "@vinami/ui";

export interface CommandFilters {
  status: "" | "open" | "under_review" | "closed";
  priority: "" | "routine" | "urgent" | "critical";
  location: string;
  search: string;
}

export function FilterBar({
  value,
  locations,
  onChange,
}: {
  value: CommandFilters;
  locations: string[];
  onChange: (next: CommandFilters) => void;
}) {
  const set = (field: keyof CommandFilters, fieldValue: string) =>
    onChange({ ...value, [field]: fieldValue });
  return (
    <div className="vm-filter-bar" aria-label="Case queue filters">
      <SearchField
        label="Search current page by patient or case reference"
        placeholder="Patient or case reference"
        value={value.search}
        onChange={(event) => set("search", event.target.value)}
      />
      <label className="vm-field">
        <span>Status</span>
        <select
          value={value.status}
          onChange={(event) =>
            set("status", event.target.value as CommandFilters["status"])
          }
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under review</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Priority</span>
        <select
          value={value.priority}
          onChange={(event) =>
            set("priority", event.target.value as CommandFilters["priority"])
          }
        >
          <option value="">All priorities</option>
          <option value="critical">Critical</option>
          <option value="urgent">Urgent</option>
          <option value="routine">Routine</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Location</span>
        <select
          value={value.location}
          onChange={(event) => set("location", event.target.value)}
        >
          <option value="">All locations</option>
          {locations.map((location) => (
            <option key={location}>{location}</option>
          ))}
        </select>
      </label>
      <span className="vm-filter-spacer" />
      <small>Search applies to this server page</small>
    </div>
  );
}
