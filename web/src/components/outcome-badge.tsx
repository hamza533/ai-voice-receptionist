import { outcomeMeta } from "@/lib/format";
import { cn } from "@/lib/utils";

export function OutcomeBadge({ outcome, className }: { outcome: string | null; className?: string }) {
  const meta = outcomeMeta(outcome);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        meta.className,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}

export function Pill({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-surface-container px-2 py-0.5 text-[11px] font-semibold text-[#394761]",
        className,
      )}
    >
      {children}
    </span>
  );
}
