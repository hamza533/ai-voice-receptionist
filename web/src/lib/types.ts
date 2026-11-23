export type Outcome =
  | "booked"
  | "rescheduled"
  | "cancelled"
  | "faq_answered"
  | "message_taken"
  | "handed_to_human"
  | "abandoned";

export interface Me {
  id: number;
  email: string;
  name: string;
  role: "admin" | "staff";
}

export interface CallListItem {
  id: string;
  channel: "web" | "phone";
  caller: string;
  started_at: string;
  duration_s: number | null;
  outcome: Outcome | null;
  summary: string | null;
  status: string;
}

export interface CallList {
  items: CallListItem[];
  total: number;
  counts: Record<string, number>;
}

export interface ToolCall {
  id: number;
  tool: string;
  args: Record<string, unknown>;
  result_status: string;
  result_summary: string;
  latency_ms: number;
  created_at: string;
}

export interface Turn {
  speaker: "caller" | "agent" | "system";
  text: string;
  ts: string;
}

export interface Appointment {
  id: string;
  ref: string;
  service: string;
  service_id: number;
  staff: string;
  staff_id: number;
  staff_color: string;
  start_utc: string;
  end_utc: string;
  customer_name: string;
  phone: string;
  email: string;
  status: "booked" | "rescheduled" | "cancelled";
  source: "ai" | "manual";
  call_id: string | null;
  calendar_synced: boolean;
}

export interface CallDetail extends CallListItem {
  ended_at: string | null;
  end_reason: string | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  interruptions: number;
  est_cost_usd: number;
  turns: Turn[];
  tool_calls: ToolCall[];
  appointments: Appointment[];
}

export interface Message {
  id: number;
  call_id: string | null;
  name: string;
  callback_number: string;
  text: string;
  urgent: boolean;
  handled: boolean;
  created_at: string;
}

export interface Overview {
  range: { from: string; to: string; days: number };
  calls: number;
  calls_change_pct: number | null;
  appointments_booked: number;
  booking_rate: number;
  avg_duration_s: number;
  median_latency_ms: number | null;
  handoffs: number;
  outcomes: Record<string, number>;
  per_day: { date: string; calls: number }[];
  upcoming_today: Appointment[];
  recent_calls: CallListItem[];
  messages_open: number;
  messages_urgent: number;
  time_saved_min: number;
}

export interface Business {
  name: string;
  timezone: string;
  address: string;
  phone: string;
  website: string;
  currency: string;
  greeting: string;
  recording_notice: string;
  voice: string;
  language: string;
  handoff_number: string;
  staff_notify_email: string;
  email_signature: string;
  extra_instructions: string;
}

export interface Service {
  id: number;
  name: string;
  description: string;
  duration_min: number;
  price: string | number;
  buffer_min: number;
  active: boolean;
  staff_ids: number[];
}

export interface Staff {
  id: number;
  name: string;
  title: string;
  calendar_id: string;
  color: string;
  active: boolean;
}

export interface Hours {
  id?: number;
  weekday: number;
  open_time: string;
  close_time: string;
}

export interface Faq {
  id: number;
  question: string;
  answer: string;
  tags: string;
  active: boolean;
}

export interface PublicBusiness {
  name: string;
  address: string;
  phone: string;
  currency: string;
  timezone: string;
  greeting: string;
  hours: Record<string, string[]>;
  services: { name: string; duration_min: number; price: number }[];
  staff: { name: string; title: string }[];
  demo_mode: boolean;
  max_call_minutes: number;
  web_call_enabled: boolean;
  calendar: "google" | "local";
}

export interface Unanswered {
  question: string;
  count: number;
  call_id: string;
  at: string;
}
