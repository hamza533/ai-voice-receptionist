"use client";

import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { WEEKDAYS } from "@/lib/format";

export interface DayRange {
  on: boolean;
  from: string;
  to: string;
}

export type Week = Record<number, DayRange>;

/** One range per weekday, from API rows ({weekday, start, end}); days without a row are off. */
export function toWeek<T extends { weekday: number }>(
  rows: T[],
  start: (r: T) => string,
  end: (r: T) => string,
  fallback: DayRange = { on: false, from: "10:00", to: "18:00" },
): Week {
  const week: Week = {};
  for (let d = 0; d < 7; d++) {
    const r = rows.find((x) => x.weekday === d);
    week[d] = r ? { on: true, from: start(r).slice(0, 5), to: end(r).slice(0, 5) } : { ...fallback };
  }
  return week;
}

export function weekRows(week: Week) {
  return Object.entries(week)
    .filter(([, r]) => r.on)
    .map(([d, r]) => ({ weekday: Number(d), from: r.from, to: r.to }));
}

export function weekError(week: Week): string | null {
  for (const [d, r] of Object.entries(week)) {
    if (r.on && r.to <= r.from) return `${WEEKDAYS[Number(d)]}: the end time must be after the start.`;
  }
  return null;
}

export function WeekEditor({
  week,
  onChange,
  offLabel = "Closed",
  disabled = false,
  testId,
}: {
  week: Week;
  onChange: (w: Week) => void;
  offLabel?: string;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <div className="flex flex-col divide-y rounded-xl border" data-testid={testId}>
      {WEEKDAYS.map((day, d) => {
        const r = week[d];
        if (!r) return null;
        const set = (patch: Partial<DayRange>) => onChange({ ...week, [d]: { ...r, ...patch } });
        return (
          <div key={day} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
            <span className="w-28 text-sm font-medium">{day}</span>
            <Switch checked={r.on} disabled={disabled} onCheckedChange={(v) => set({ on: v })} aria-label={`${day} on`} />
            {r.on ? (
              <div className="flex items-center gap-2 text-sm">
                <Input type="time" value={r.from} disabled={disabled} onChange={(e) => set({ from: e.target.value })} className="h-9 w-32" aria-label={`${day} from`} />
                –
                <Input type="time" value={r.to} disabled={disabled} onChange={(e) => set({ to: e.target.value })} className="h-9 w-32" aria-label={`${day} to`} />
              </div>
            ) : (
              <span className="rounded-full bg-surface-container px-2 py-0.5 text-xs font-semibold text-[#394761]">{offLabel}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
