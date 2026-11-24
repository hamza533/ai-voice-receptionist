"use client";

import { OptionSelect } from "@/components/dashboard/option-select";
import { Input } from "@/components/ui/input";
import type { GoogleCalendarItem, Integrations } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const DEFAULT = "__default__";

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
      <OptionSelect
        value={value || DEFAULT}
        onChange={(v) => onChange(v === DEFAULT ? "" : v)}
        disabled={disabled}
        ariaLabel="Calendar"
        options={[
          { value: DEFAULT, label: emptyLabel },
          ...calendars.map((c) => ({ value: c.id, label: c.primary ? `${c.name} (main)` : c.name })),
          ...(value && !known ? [{ value, label: value }] : []),
        ]}
      />
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
