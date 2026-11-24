"use client";

import { Input } from "@/components/ui/input";
import type { GoogleCalendarItem, Integrations } from "@/lib/types";
import { useApi } from "@/lib/use-api";

export const selectClass =
  "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60";

/**
 * Pick a calendar. With Google connected (Settings → Integrations) it is a list of the
 * account's calendars; otherwise a plain field for a calendar ID (service-account setups).
 */
export function CalendarPicker({
  value,
  onChange,
  emptyLabel = "Use the business calendar",
  disabled = false,
  isAdmin = true,
}: {
  value: string;
  onChange: (id: string) => void;
  emptyLabel?: string;
  disabled?: boolean;
  isAdmin?: boolean;
}) {
  const { data: status } = useApi<Integrations>("/api/integrations");
  const connected = Boolean(status?.google.connected);
  const { data: calendars } = useApi<GoogleCalendarItem[]>(
    connected && isAdmin ? "/api/integrations/google/calendars" : null,
  );

  if (connected && calendars) {
    const known = calendars.some((c) => c.id === value);
    return (
      <select className={selectClass} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} aria-label="Calendar">
        <option value="">{emptyLabel}</option>
        {calendars.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
            {c.primary ? " (main)" : ""}
          </option>
        ))}
        {value && !known ? <option value={value}>{value}</option> : null}
      </select>
    );
  }
  return (
    <Input
      value={value}
      disabled={disabled}
      placeholder={emptyLabel}
      onChange={(e) => onChange(e.target.value)}
      className="h-9"
      aria-label="Calendar ID"
    />
  );
}
