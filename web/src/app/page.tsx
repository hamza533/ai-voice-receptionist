"use client";

import {
  ArrowRight,
  BookOpenText,
  CalendarCheck2,
  CalendarSync,
  CheckCircle2,
  Clock3,
  Headset,
  Mail,
  Mic,
  PhoneCall,
  PhoneIncoming,
  ShieldCheck,
  Sparkles,
  Volume2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Brand } from "@/components/brand";
import { Button, buttonVariants } from "@/components/ui/button";
import { WakingBanner } from "@/components/waking-banner";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { PublicBusiness } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const SAMPLE_QUESTIONS = [
  { icon: "🅿️", q: "Is there parking nearby?" },
  { icon: "💳", q: "What payment methods do you accept?" },
  { icon: "🎨", q: "How long does a hair colour take?" },
];

export default function Landing() {
  const { data: biz, error } = useApi<PublicBusiness>("/api/public/business");
  const name = biz?.name ?? "Luma Hair Studio";

  return (
    <div className="min-h-screen bg-background">
      <WakingBanner ready={Boolean(biz) || Boolean(error)} />
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Brand subtitle="Voice Agent 2.0" />
          <nav className="hidden items-center gap-7 text-sm font-medium text-muted-foreground md:flex">
            <a href="#how" className="hover:text-foreground">How it works</a>
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#salon" className="hover:text-foreground">Demo salon</a>
          </nav>
          <Link href="/dashboard" className={cn(buttonVariants(), "btn-gradient h-9 rounded-lg px-3.5 text-white")}>
            Open dashboard <ArrowRight />
          </Link>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-16 pt-14 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
          <div className="flex flex-col items-start gap-6">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-fixed/70 px-3 py-1 text-xs font-semibold text-[#00201b]">
              <CheckCircle2 className="size-3.5" /> Tailored for {name}
            </span>
            <h1 className="text-4xl font-bold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-[56px]">
              Never miss a call again
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
              Your AI receptionist answers every call, answers questions and books appointments
              straight into your Google Calendar — 24/7. When a caller needs a person, your team is
              alerted instantly.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/call"
                className={cn(buttonVariants({ size: "lg" }), "btn-gradient h-12 rounded-xl px-6 text-base text-white")}
                data-testid="hero-talk"
              >
                <Mic /> Talk to the receptionist
              </Link>
              <a
                href="#how"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-12 rounded-xl bg-card px-6 text-base")}
              >
                See how it works
              </a>
            </div>
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="size-4 text-primary" /> Works in the browser — no phone or app
              needed.
            </p>
          </div>
          <CallPreview name={name} />
        </section>

        {/* Value strip */}
        <section className="mx-auto max-w-6xl px-5">
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { k: "24/7", v: "Answers every call, nights and weekends" },
              { k: "Live calendar", v: "Books only real free slots — never double-books" },
              { k: "Human handoff", v: "Urgent callers reach your team in seconds" },
            ].map((s) => (
              <div key={s.k} className="surface-card px-6 py-5">
                <p className="text-2xl font-bold tracking-tight text-primary">{s.k}</p>
                <p className="mt-1 text-sm text-muted-foreground">{s.v}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-20">
          <p className="label-caps flex items-center gap-1.5 text-primary">
            <Sparkles className="size-3.5" /> Effortless workflow
          </p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">How it works</h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Connect your phone number or add a “Talk to us” button to your website. That’s it.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {[
              {
                n: 1,
                t: "Caller calls",
                tag: "Instant pickup",
                d: "Ava answers by phone or from your website with your salon's greeting — no hold music, no voicemail.",
                icon: PhoneIncoming,
              },
              {
                n: 2,
                t: "Ava answers & schedules",
                tag: "Natural voice",
                d: "Answers questions from your FAQ, checks live availability and books, moves or cancels appointments.",
                icon: Volume2,
              },
              {
                n: 3,
                t: "Booked & confirmed",
                tag: "Email sent",
                d: "The event appears in Google Calendar, the caller gets a confirmation email and you get a summary.",
                icon: CalendarCheck2,
              },
            ].map((s) => (
              <div key={s.n} className="surface-card surface-card-hover flex flex-col gap-3 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-primary-fixed/70 font-bold text-[#00201b]">
                    {s.n}
                  </span>
                  <span className="rounded-full bg-mint px-2 py-0.5 text-xs font-semibold text-primary">{s.tag}</span>
                </div>
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                  <s.icon className="size-5 text-primary" /> {s.t}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{s.d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Try sample questions */}
        <section className="mx-auto max-w-6xl px-5">
          <SampleQuestions />
        </section>

        {/* Features */}
        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-20">
          <p className="label-caps flex items-center gap-1.5 text-primary">
            <ShieldCheck className="size-3.5" /> Built for appointment businesses
          </p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Everything a front desk does</h2>
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: Clock3, t: "24/7 answering", d: "Captures after-hours calls, weekend bookings and lunch-hour rushes without overtime." },
              { icon: BookOpenText, t: "FAQ knowledge base", d: "Trained on your services, prices, parking and policies. Update it from the dashboard." },
              { icon: CalendarSync, t: "Google Calendar booking", d: "Real-time free/busy, service durations and buffers. Never offers a time that isn't free." },
              { icon: CalendarCheck2, t: "Reschedule & cancel", d: "Finds the booking by the caller's phone or email — nobody else's booking is ever revealed." },
              { icon: Headset, t: "Warm human handoff", d: "Asks for a person? Your team gets an urgent alert, or the call transfers to your number." },
              { icon: Mail, t: "Transcripts & summaries", d: "Every call saved with a transcript, summary, outcome and response-time metrics." },
            ].map((f) => (
              <div key={f.t} className="surface-card surface-card-hover flex gap-4 p-5">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-mint text-primary">
                  <f.icon className="size-5" />
                </span>
                <div>
                  <h3 className="font-semibold">{f.t}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{f.d}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Demo salon */}
        <section id="salon" className="mx-auto max-w-6xl scroll-mt-20 px-5 pb-20">
          <div className="surface-card grid gap-8 p-7 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <p className="label-caps text-primary">Demo business</p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight">{name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{biz?.address ?? "24 Market Street"}</p>
              <div className="mt-5 divide-y rounded-xl border">
                {(biz?.services ?? []).map((s) => (
                  <div key={s.name} className="flex items-center justify-between px-4 py-3 text-sm">
                    <span className="font-medium">{s.name}</span>
                    <span className="text-muted-foreground">
                      {s.duration_min} min · <b className="text-foreground">{money(s.price, biz?.currency)}</b>
                    </span>
                  </div>
                ))}
                {!biz ? <div className="h-40 animate-pulse bg-muted/60" /> : null}
              </div>
            </div>
            <div>
              <p className="label-caps text-primary">Opening hours</p>
              <ul className="mt-3 space-y-1.5 text-sm">
                {Object.entries(biz?.hours ?? {}).map(([day, spans]) => (
                  <li key={day} className="flex justify-between">
                    <span className="text-muted-foreground">{day}</span>
                    <span className={cn("font-medium", spans.length === 0 && "text-destructive")}>
                      {spans.length ? spans.join(", ") : "Closed"}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="label-caps mt-6 text-primary">Team</p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {(biz?.staff ?? []).map((s) => (
                  <li key={s.name} className="rounded-full bg-surface-low px-3 py-1 text-sm">
                    <b>{s.name}</b> <span className="text-muted-foreground">· {s.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-5 pb-20">
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-[#004d43] px-8 py-14 text-center text-white">
            <PhoneCall className="mx-auto size-8 opacity-90" />
            <h2 className="mx-auto mt-4 max-w-xl text-3xl font-bold tracking-tight">
              Ready to stop losing bookings to missed calls?
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-white/80">
              Hear it for yourself: ask Ava about prices, then book a haircut.
            </p>
            <Link
              href="/call"
              className={cn(buttonVariants({ size: "lg" }), "mt-7 h-12 rounded-xl bg-white px-6 text-base text-primary hover:bg-white/90")}
            >
              <Mic /> Talk to the receptionist
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-5 py-6 text-sm text-muted-foreground sm:flex-row">
          <Brand />
          <p>Demo business and data are fictional. Calls may be recorded and transcribed.</p>
        </div>
      </footer>
    </div>
  );
}

function CallPreview({ name }: { name: string }) {
  return (
    <div className="surface-card relative overflow-hidden p-5 shadow-[0_24px_60px_-30px_rgb(11_27_51/0.35)]">
      <div className="mb-4 flex items-center justify-between">
        <span className="label-caps text-primary">Example call</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-low px-2.5 py-1 text-xs text-muted-foreground">
          <PhoneCall className="size-3.5" /> {name}
        </span>
      </div>
      <div className="mb-4 flex items-center justify-between rounded-xl bg-surface-low px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Volume2 className="size-4 text-primary" /> Caller audio stream
        </span>
        <span className="flex h-6 items-center gap-[3px] text-primary" aria-hidden>
          {[0.5, 0.9, 0.6, 1, 0.7, 0.85, 0.45, 0.75].map((h, i) => (
            <span
              key={i}
              className="wave-bar w-[3px] rounded-full bg-primary"
              style={{ height: `${h * 100}%`, animationDelay: `${i * 0.11}s` }}
            />
          ))}
        </span>
      </div>
      <div className="flex flex-col gap-3">
        <Bubble caller>Can I book a haircut with Sara on Tuesday afternoon?</Bubble>
        <Bubble>
          Sure! Sara has 2:30 PM or 4:00 PM on Tuesday. Which works best for you?
        </Bubble>
        <Bubble caller>2:30, please.</Bubble>
        <Bubble>
          Just to confirm: a haircut with Sara on Tuesday at 2:30 PM for Ayesha Khan.
          Shall I book it?
        </Bubble>
      </div>
      <div className="mt-4 flex items-center gap-3 rounded-xl bg-mint px-4 py-3">
        <CheckCircle2 className="size-5 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">Appointment booked — Tuesday, 2:30 PM</p>
          <p className="text-xs text-primary">Confirmation email sent · with Sara</p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-white px-2 py-1 text-[11px] font-semibold text-foreground">
          <CalendarSync className="size-3.5 text-primary" /> Google Sync
        </span>
      </div>
    </div>
  );
}

function Bubble({ children, caller }: { children: React.ReactNode; caller?: boolean }) {
  return (
    <div className={cn("flex items-end gap-2", caller ? "justify-start" : "justify-end")}>
      {caller ? (
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-container text-[#394761]">
          <PhoneCall className="size-3.5" />
        </span>
      ) : null}
      <p
        className={cn(
          "max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
          caller ? "rounded-bl-sm border bg-card" : "rounded-br-sm bg-mint",
        )}
      >
        {children}
      </p>
      {!caller ? (
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-white">
          <Sparkles className="size-3.5" />
        </span>
      ) : null}
    </div>
  );
}

function SampleQuestions() {
  const [answer, setAnswer] = useState<{ q: string; a: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function ask(q: string) {
    setBusy(true);
    try {
      const r = await api<{ status: string; data: { answer?: string } }>("/api/public/faq-test", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      setAnswer({ q, a: r.data.answer ?? "I'm not sure about that one — I'd take a message for the team." });
    } catch {
      setAnswer({ q, a: "The demo server is waking up — try again in a few seconds." });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid gap-6 rounded-3xl bg-gradient-to-br from-mint to-surface-low p-7 lg:grid-cols-[1fr_1.1fr]">
      <div>
        <h3 className="flex items-center gap-2 text-xl font-bold">
          <Sparkles className="size-5 text-primary" /> Try sample questions
          <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-semibold text-white">Live answers</span>
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Tap a question: Ava answers from the salon&apos;s real FAQ, the same way she does on a call.
        </p>
        <div className="mt-4 flex flex-col items-start gap-2">
          {SAMPLE_QUESTIONS.map((s) => (
            <Button
              key={s.q}
              variant="outline"
              className="h-auto rounded-xl bg-card px-3 py-2 text-left text-sm font-medium"
              disabled={busy}
              onClick={() => void ask(s.q)}
            >
              <span aria-hidden>{s.icon}</span> “{s.q}”
            </Button>
          ))}
        </div>
      </div>
      <div className="surface-card flex min-h-40 flex-col justify-center gap-3 p-5">
        {answer ? (
          <>
            <p className="self-end rounded-2xl rounded-tr-sm bg-surface-low px-3.5 py-2 text-sm">{answer.q}</p>
            <div className="flex flex-col items-start gap-1">
              <span className="inline-flex items-center gap-1 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-white">
                <Sparkles className="size-3" /> Ava
              </span>
              <p className="rounded-2xl rounded-tl-sm bg-mint px-3.5 py-2 text-sm leading-relaxed">{answer.a}</p>
            </div>
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm italic text-muted-foreground">
            <Volume2 className="size-4" /> Select a question to hear how the receptionist replies…
          </p>
        )}
      </div>
    </div>
  );
}
