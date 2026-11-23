// Small SVG charts in the Stitch style. No chart library needed for two charts.
import { cn } from "@/lib/utils";

export function WeeklyBars({
  data,
  className,
}: {
  data: { label: string; value: number; highlight?: boolean }[];
  className?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const peak = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);
  return (
    <div className={cn("flex h-44 items-end gap-2.5", className)} role="img" aria-label="Calls per day">
      {data.map((d, i) => {
        const h = Math.max(6, Math.round((d.value / max) * 100));
        const isPeak = i === peak && d.value > 0;
        return (
          <div key={d.label + i} className="flex flex-1 flex-col items-center gap-1.5">
            <span className={cn("text-xs font-semibold tabular-nums", isPeak ? "text-primary" : "text-muted-foreground")}>
              {d.value}
            </span>
            <div className="flex h-32 w-full items-end">
              <div
                className={cn(
                  "w-full rounded-t-lg transition-all",
                  isPeak ? "bg-primary" : d.highlight ? "bg-primary-container/80" : "bg-[#2a8577]/80",
                )}
                style={{ height: `${h}%` }}
              >
                {isPeak ? <div className="h-1.5 rounded-t-lg bg-primary-fixed" /> : null}
              </div>
            </div>
            <span className={cn("text-xs", isPeak ? "font-bold text-primary" : "text-muted-foreground")}>
              {d.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function Donut({
  segments,
  centerLabel,
  centerValue,
  size = 132,
}: {
  segments: { label: string; value: number; color: string }[];
  centerLabel: string;
  centerValue: string;
  size?: number;
}) {
  const total = Math.max(1, segments.reduce((s, x) => s + x.value, 0));
  const r = 52;
  const c = 2 * Math.PI * r;
  const lengths = segments.map((s) => (s.value / total) * c);
  const offsets = lengths.map((_, i) => lengths.slice(0, i).reduce((a, b) => a + b, 0));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="0 0 132 132" className="-rotate-90" width={size} height={size} aria-hidden>
        <circle cx="66" cy="66" r={r} fill="none" stroke="#eff4ff" strokeWidth="16" />
        {segments.map((s, i) => (
          <circle
            key={s.label}
            cx="66"
            cy="66"
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth="16"
            strokeDasharray={`${Math.max(0, lengths[i] - 2)} ${c}`}
            strokeDashoffset={-offsets[i]}
          />
        ))}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tracking-tight">{centerValue}</span>
        <span className="label-caps text-muted-foreground">{centerLabel}</span>
      </div>
    </div>
  );
}
