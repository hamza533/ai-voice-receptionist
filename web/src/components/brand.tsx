import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-xl bg-gradient-to-b from-brand to-primary text-white shadow-[0_4px_12px_-4px_rgb(0_104_91/0.6)]",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" />
      </svg>
    </span>
  );
}

export function Brand({ subtitle, className }: { subtitle?: string; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="flex flex-col leading-tight">
        <span className="text-[15px] font-bold tracking-tight text-foreground">Receptly</span>
        {subtitle ? <span className="text-xs font-medium text-primary">{subtitle}</span> : null}
      </span>
    </span>
  );
}

export function AiActivePill({ label = "AI Active" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-fixed/80 px-2 py-0.5 text-[11px] font-semibold text-[#00201b]">
      <span className="relative flex size-1.5">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
        <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
      </span>
      {label}
    </span>
  );
}
