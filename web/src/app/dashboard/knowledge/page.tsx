"use client";

import { AlertTriangle, Bot, Pencil, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useDashboard } from "@/components/dashboard/context";
import { Pill } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, json } from "@/lib/api";
import { money } from "@/lib/format";
import type { Faq, Service, Unanswered } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type Draft = { id?: number; question: string; answer: string; tags: string; active: boolean };

export default function KnowledgePage() {
  const { me, business } = useDashboard();
  const isAdmin = me.role === "admin";
  const { data: faqs, reload } = useApi<Faq[]>("/api/settings/faqs");
  const { data: services } = useApi<Service[]>("/api/settings/services");
  const { data: unanswered } = useApi<Unanswered[]>("/api/stats/unanswered?days=7");
  const [tab, setTab] = useState<"faqs" | "services">("faqs");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!draft) return;
    setSaving(true);
    try {
      const body = { question: draft.question, answer: draft.answer, tags: draft.tags, active: draft.active };
      if (draft.id) await api(`/api/settings/faqs/${draft.id}`, { method: "PUT", ...json(body) });
      else await api("/api/settings/faqs", { method: "POST", ...json(body) });
      toast.success("Saved — Ava uses it on the next call");
      setDraft(null);
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggle(f: Faq, active: boolean) {
    try {
      await api(`/api/settings/faqs/${f.id}`, { method: "PUT", ...json({ ...f, active }) });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function remove(f: Faq) {
    if (!window.confirm("Delete this FAQ?")) return;
    try {
      await api(`/api/settings/faqs/${f.id}`, { method: "DELETE" });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const activeCount = faqs?.filter((f) => f.active).length ?? 0;

  return (
    <div className="mx-auto grid max-w-7xl gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold tracking-tight">Salon knowledge base</h2>
            <Pill className="bg-surface-container">{activeCount} active FAQs</Pill>
          </div>
          {isAdmin ? (
            <Button
              className="btn-gradient h-9 rounded-lg text-white"
              onClick={() => setDraft({ question: "", answer: "", tags: "", active: true })}
              data-testid="add-faq"
            >
              <Plus /> Add FAQ
            </Button>
          ) : null}
        </div>

        {unanswered && unanswered.length > 0 ? (
          <div className="flex flex-col gap-3 rounded-2xl border border-[#fde68a] bg-gradient-to-r from-[#fff7e6] to-[#fffbeb] p-5">
            <p className="flex items-center gap-2 font-semibold text-[#92400e]">
              <AlertTriangle className="size-5" /> Unanswered questions this week ({unanswered.length})
            </p>
            <p className="text-sm text-[#92400e]/80">Callers asked these and Ava had no FAQ to answer from.</p>
            <ul className="flex flex-col gap-2">
              {unanswered.slice(0, 4).map((u) => (
                <li key={u.question} className="flex items-center justify-between gap-3 rounded-xl bg-white/70 px-3 py-2 text-sm">
                  <span>“{u.question}” {u.count > 1 ? <b className="text-[#92400e]">×{u.count}</b> : null}</span>
                  {isAdmin ? (
                    <Button
                      size="sm"
                      className="bg-[#b45309] text-white hover:bg-[#92400e]"
                      onClick={() => setDraft({ question: u.question, answer: "", tags: "", active: true })}
                    >
                      Answer it
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex gap-2">
          {(
            [
              ["faqs", `FAQs (${faqs?.length ?? 0})`],
              ["services", `Services & prices (${services?.length ?? 0})`],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium",
                tab === k ? "bg-primary text-white" : "bg-surface-container text-[#394761]",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "faqs" ? (
          <div className="flex flex-col gap-4">
            {!faqs ? <Skeleton className="h-64 rounded-2xl" /> : null}
            {faqs?.map((f) => (
              <article key={f.id} className={cn("surface-card flex flex-col gap-3 p-5", !f.active && "opacity-60")}>
                <h3 className="font-semibold">{f.question}</h3>
                <div className="rounded-xl bg-surface-low p-4">
                  <p className="label-caps mb-1.5 flex items-center gap-1 text-primary">
                    <Sparkles className="size-3" /> Ava&apos;s trained response
                  </p>
                  <p className="text-sm leading-relaxed">{f.answer}</p>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{f.tags ? `Keywords: ${f.tags}` : "No keywords"}</span>
                  {isAdmin ? (
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon-sm" aria-label="Edit" onClick={() => setDraft({ ...f })}>
                        <Pencil />
                      </Button>
                      <Button variant="ghost" size="icon-sm" aria-label="Delete" onClick={() => void remove(f)}>
                        <Trash2 />
                      </Button>
                      <Switch checked={f.active} onCheckedChange={(v) => void toggle(f, v)} aria-label="Active" />
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="surface-card divide-y">
            {services?.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-3 px-5 py-4">
                <div>
                  <p className="font-semibold">{s.name}</p>
                  <p className="text-sm text-muted-foreground">{s.description}</p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-semibold">{money(s.price, business.currency)}</p>
                  <p className="text-muted-foreground">
                    {s.duration_min} min{s.buffer_min ? ` + ${s.buffer_min} buffer` : ""}
                  </p>
                </div>
              </div>
            ))}
            <p className="px-5 py-3 text-xs text-muted-foreground">Edit services, durations and buffers in Settings.</p>
          </div>
        )}
      </div>

      <TestPanel />

      <Dialog open={draft !== null} onOpenChange={(o) => !o && setDraft(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{draft?.id ? "Edit FAQ" : "Add FAQ"}</DialogTitle>
          </DialogHeader>
          {draft ? (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="q">Question</Label>
                <Input id="q" value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="a">Answer Ava gives</Label>
                <Textarea id="a" rows={4} value={draft.answer} onChange={(e) => setDraft({ ...draft, answer: e.target.value })} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="t">Keywords (help matching)</Label>
                <Input id="t" value={draft.tags} placeholder="e.g. parking car" onChange={(e) => setDraft({ ...draft, tags: e.target.value })} />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDraft(null)}>Cancel</Button>
            <Button className="btn-gradient text-white" disabled={saving || !draft?.question || !draft?.answer} onClick={() => void save()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TestPanel() {
  const [q, setQ] = useState("");
  const [log, setLog] = useState<{ q: string; a: string; ok: boolean }[]>([]);
  const [busy, setBusy] = useState(false);
  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    try {
      const r = await api<{ status: string; data: { answer?: string } }>("/api/public/faq-test", {
        method: "POST",
        ...json({ question: q }),
      });
      setLog((l) => [
        ...l,
        r.status === "ok"
          ? { q, a: r.data.answer ?? "", ok: true }
          : { q, a: "No FAQ covers this — Ava would offer to take a message.", ok: false },
      ]);
      setQ("");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="surface-card flex h-fit flex-col gap-4 p-5 xl:sticky xl:top-24">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold">
          <Bot className="size-5 text-primary" /> Test Ava&apos;s knowledge
        </h3>
        <Pill className="bg-primary-fixed/60 text-[#00201b]">● Live answers</Pill>
      </div>
      <div className="flex min-h-48 flex-col gap-3 rounded-xl bg-surface-low p-3">
        {log.length === 0 ? (
          <p className="m-auto text-center text-sm text-muted-foreground">Ask anything a caller might ask.</p>
        ) : null}
        {log.map((m, i) => (
          <div key={i} className="flex flex-col gap-2">
            <p className="self-end rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-sm text-white">{m.q}</p>
            <p className={cn("max-w-[90%] rounded-2xl rounded-tl-sm px-3 py-2 text-sm", m.ok ? "bg-white" : "bg-[#fff7e6] text-[#92400e]")}>
              {m.a}
            </p>
          </div>
        ))}
      </div>
      <form onSubmit={ask} className="flex gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Do you take walk-ins?" className="h-10" />
        <Button type="submit" size="icon-lg" className="btn-gradient size-10 text-white" disabled={busy} aria-label="Ask">
          <Send />
        </Button>
      </form>
    </div>
  );
}
