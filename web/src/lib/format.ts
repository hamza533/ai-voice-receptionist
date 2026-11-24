import type { Outcome } from "./types";

export const OUTCOMES: Record<Outcome, { label: string; className: string; dot: string }> = {
  booked: { label: "Appointment booked", className: "bg-primary-fixed/70 text-[#00201b]", dot: "bg-primary" },
  rescheduled: { label: "Rescheduled", className: "bg-secondary text-[#394761]", dot: "bg-[#505f7a]" },
  cancelled: { label: "Cancelled", className: "bg-[#ffdad6] text-[#93000a]", dot: "bg-destructive" },
  faq_answered: { label: "FAQ answered", className: "bg-mint text-primary", dot: "bg-brand" },
  message_taken: { label: "Message taken", className: "bg-[#fef3c7] text-[#92400e]", dot: "bg-warning" },
  waitlisted: { label: "Joined waitlist", className: "bg-secondary text-[#394761]", dot: "bg-[#505f7a]" },
  handed_to_human: { label: "Handed to human", className: "bg-[#fde2e1] text-[#93000a]", dot: "bg-[#e11d48]" },
  abandoned: { label: "Abandoned", className: "bg-muted text-muted-foreground", dot: "bg-[#94a3b8]" },
};

export function outcomeMeta(o: string | null | undefined) {
  if (!o) return { label: "In progress", className: "bg-muted text-muted-foreground", dot: "bg-[#94a3b8]" };
  return OUTCOMES[o as Outcome] ?? { label: o, className: "bg-muted", dot: "bg-muted-foreground" };
}

export function fmtTime(iso: string, tz?: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: tz,
  }).format(new Date(iso));
}

export function fmtDate(iso: string, tz?: string, opts: Intl.DateTimeFormatOptions = {}) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: tz,
    ...opts,
  }).format(new Date(iso));
}

export function fmtDateTime(iso: string, tz?: string) {
  return `${fmtDate(iso, tz)}, ${fmtTime(iso, tz)}`;
}

/** YYYY-MM-DD for a date in the given time zone. */
export function isoDay(d: Date, tz?: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

export function relDay(iso: string, tz?: string) {
  const day = isoDay(new Date(iso), tz);
  if (day === isoDay(new Date(), tz)) return "Today";
  if (day === isoDay(new Date(Date.now() - 86_400_000), tz)) return "Yesterday";
  return fmtDate(iso, tz);
}

export function fmtDuration(s: number | null | undefined) {
  if (s === null || s === undefined) return "—";
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m ? `${m}m ${sec.toString().padStart(2, "0")}s` : `${sec}s`;
}

export function money(amount: number | string, currency = "PKR") {
  return `${currency} ${Number(amount).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export const TOOL_LABELS: Record<string, string> = {
  get_business_info: "Looked up business info",
  answer_faq: "Answered from the FAQ",
  check_availability: "Checked availability",
  book_appointment: "Booked the appointment",
  reschedule_appointment: "Rescheduled the appointment",
  cancel_appointment: "Cancelled the appointment",
  take_message: "Took a message for the team",
  request_human: "Alerted staff for a handoff",
  join_waitlist: "Added the caller to the waitlist",
};

export function fmtMoney(amount: number, currency: string) {
  const whole = Number.isInteger(amount);
  return `${currency} ${amount.toLocaleString("en-US", {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  })}`;
}

/** "HH:MM" from an API time ("HH:MM:SS"). */
export const hhmm = (t: string | null | undefined) => (t ?? "").slice(0, 5);

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
