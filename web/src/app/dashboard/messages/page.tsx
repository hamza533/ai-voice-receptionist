"use client";

import { AlertTriangle, CheckCircle2, ExternalLink, MessageSquareMore, Phone, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { useDashboard } from "@/components/dashboard/context";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, json } from "@/lib/api";
import { fmtTime, relDay } from "@/lib/format";
import type { Message } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

export default function MessagesPage() {
  const { tz } = useDashboard();
  const [tab, setTab] = useState<"open" | "handled">("open");
  const { data, setData } = useApi<Message[]>(`/api/messages?handled=${tab === "handled"}`, { refreshMs: 15000 });

  async function toggle(m: Message) {
    try {
      await api<Message>(`/api/messages/${m.id}`, { method: "PATCH", ...json({ handled: !m.handled }) });
      setData((prev) => prev?.filter((x) => x.id !== m.id));
      toast.success(m.handled ? "Moved back to open" : "Marked as handled");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Callbacks requested by callers and urgent handoffs. Staff are emailed for each one.
        </p>
        <div className="flex rounded-full bg-surface-container p-1">
          {(["open", "handled"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium capitalize",
                tab === t ? "bg-card text-foreground shadow-sm" : "text-muted-foreground",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {!data ? <Skeleton className="h-64 rounded-2xl" /> : null}
      {data && data.length === 0 ? (
        <div className="surface-card flex flex-col items-center gap-2 px-6 py-14 text-center">
          <MessageSquareMore className="size-8 text-primary" />
          <p className="font-semibold">{tab === "open" ? "Inbox zero" : "Nothing handled yet"}</p>
          <p className="text-sm text-muted-foreground">
            {tab === "open" ? "No callbacks waiting." : "Handled messages appear here."}
          </p>
        </div>
      ) : null}

      <div className="flex flex-col gap-4">
        {data?.map((m) => (
          <article
            key={m.id}
            className={cn("surface-card flex flex-col gap-3 p-5", m.urgent && !m.handled && "border-l-4 border-l-destructive")}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 font-semibold">
                  {m.name}
                  {m.urgent ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#ffdad6] px-2 py-0.5 text-[11px] font-semibold text-[#93000a]">
                      <AlertTriangle className="size-3" /> Urgent · wants a person
                    </span>
                  ) : null}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Phone className="size-3.5" />
                  <a href={`tel:${m.callback_number}`} className="hover:text-primary">{m.callback_number || "—"}</a>
                </p>
              </div>
              <span className="text-xs text-muted-foreground">
                {relDay(m.created_at, tz)}, {fmtTime(m.created_at, tz)}
              </span>
            </div>
            <p className="rounded-xl bg-surface-low px-4 py-3 text-sm leading-relaxed">{m.text}</p>
            <div className="flex justify-end gap-2">
              {m.call_id ? (
                <Link
                  href={`/dashboard/calls/${m.call_id}`}
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-primary hover:bg-mint"
                >
                  <ExternalLink className="size-4" /> View call
                </Link>
              ) : null}
              <Button variant={m.handled ? "outline" : "default"} onClick={() => void toggle(m)} className={cn(!m.handled && "btn-gradient text-white")}>
                {m.handled ? <RotateCcw /> : <CheckCircle2 />} {m.handled ? "Reopen" : "Mark handled"}
              </Button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
