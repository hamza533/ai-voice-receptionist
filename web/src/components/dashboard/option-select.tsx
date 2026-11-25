"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface Option {
  value: string;
  label: string;
}

/** A simple value/label dropdown on the shadcn/ui Select (Clinical Calm tokens). */
export function OptionSelect({
  id,
  value,
  onChange,
  options,
  placeholder,
  disabled,
  ariaLabel,
  className,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <Select
      items={options}
      value={options.some((o) => o.value === value) ? value : null}
      onValueChange={(v) => onChange(v == null ? "" : String(v))}
      disabled={disabled}
    >
      <SelectTrigger id={id} aria-label={ariaLabel} className={cn("h-9 w-full bg-card", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
