"use client";

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { CheckCircle2, Loader2, MessageSquareText, Mic, MicOff, PhoneOff, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { TOOL_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";

type Phase = "idle" | "connecting" | "live" | "ended" | "error";
interface TokenResponse {
  token: string;
  url: string;
  room: string;
  identity: string;
  expires_in: number;
}
interface ToolEvent {
  tool: string;
  status: string;
  at: number;
}

export function LiveCall({
  businessName,
  maxMinutes,
  demoMode,
  compact = false,
  onEnded,
}: {
  businessName: string;
  maxMinutes: number;
  demoMode: boolean;
  compact?: boolean;
  onEnded?: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [conn, setConn] = useState<TokenResponse | null>(null);
  const [error, setError] = useState<string>("");

  async function start() {
    setPhase("connecting");
    setError("");
    try {
      const t = await api<TokenResponse>("/api/web-call/token", { method: "POST" });
      setConn(t);
    } catch (e) {
      const err = e as ApiError;
      setError(
        err.status === 503 || err.status === 429
          ? err.message
          : "Could not reach the receptionist. The demo server may be waking up, try again in a moment.",
      );
      setPhase("error");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {demoMode ? (
        <div className="flex items-start gap-2.5 rounded-xl bg-surface-container px-3.5 py-2.5 text-sm text-[#394761]">
          <span className="mt-0.5 inline-block size-2 rounded-full bg-[#505f7a]" />
          <p>
            <b>Demo mode:</b> calls are limited to {maxMinutes} minutes and bookings go to a demo
            calendar that resets nightly.
          </p>
        </div>
      ) : null}

      {conn ? (
        <LiveKitRoom
          serverUrl={conn.url}
          token={conn.token}
          connect
          audio
          video={false}
          onConnected={() => setPhase("live")}
          onDisconnected={() => {
            setPhase("ended");
            setConn(null);
            onEnded?.();
          }}
          onError={(e) => {
            setError(e.message);
            setPhase("error");
          }}
          onMediaDeviceFailure={() => {
            setError("Microphone access was blocked. Allow the microphone and try again.");
            setPhase("error");
          }}
        >
          <RoomAudioRenderer />
          <InCall businessName={businessName} identity={conn.identity} compact={compact} />
        </LiveKitRoom>
      ) : (
        <IdleCard phase={phase} error={error} businessName={businessName} onStart={start} />
      )}
    </div>
  );
}

function IdleCard({
  phase,
  error,
  businessName,
  onStart,
}: {
  phase: Phase;
  error: string;
  businessName: string;
  onStart: () => void;
}) {
  return (
    <div className="surface-card flex flex-col items-center gap-5 px-6 py-10 text-center">
      <p className="label-caps text-primary">{businessName} · Line 01</p>
      <Orb active={phase === "connecting"} />
      {phase === "ended" ? (
        <p className="text-sm text-muted-foreground">
          Call ended. The transcript and summary appear in the dashboard within a few seconds.
        </p>
      ) : (
        <p className="max-w-sm text-sm text-muted-foreground">
          Talk to Ava, the receptionist. Ask about prices or opening hours, book a haircut, or ask
          for a person.
        </p>
      )}
      {error ? (
        <p role="alert" className="max-w-sm rounded-lg bg-[#ffdad6] px-3 py-2 text-sm text-[#93000a]">
          {error}
        </p>
      ) : null}
      <Button
        size="lg"
        className="btn-gradient h-12 rounded-xl px-6 text-base text-white"
        onClick={onStart}
        disabled={phase === "connecting"}
        data-testid="start-call"
      >
        {phase === "connecting" ? <Loader2 className="animate-spin" /> : <Mic />}
        {phase === "connecting" ? "Connecting…" : phase === "ended" ? "Call again" : "Talk to the receptionist"}
      </Button>
      <p className="text-xs text-muted-foreground">This call may be recorded and transcribed.</p>
    </div>
  );
}

function Orb({ active, speaking = false }: { active: boolean; speaking?: boolean }) {
  return (
    <div className="relative flex size-44 items-center justify-center">
      {active ? (
        <>
          <span className="orb-ring absolute inset-0 rounded-full bg-primary-fixed/60" />
          <span className="orb-ring orb-ring-delay absolute inset-0 rounded-full bg-primary-fixed/40" />
        </>
      ) : null}
      <span className="absolute inset-4 rounded-full bg-mint" />
      <span
        className={cn(
          "relative flex size-28 items-center justify-center rounded-full bg-gradient-to-b from-primary-container to-primary text-white shadow-[0_12px_30px_-10px_rgb(0_104_91/0.7)] transition-transform",
          speaking && "scale-105",
        )}
      >
        <svg viewBox="0 0 24 24" className="size-10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <path d="M6 10v4M10 6v12M14 8v8M18 10v4" />
        </svg>
      </span>
    </div>
  );
}

function useElapsed(running: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const t = setInterval(() => setS(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(t);
  }, [running]);
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

function InCall({ businessName, identity, compact }: { businessName: string; identity: string; compact: boolean }) {
  const room = useRoomContext();
  const { state, audioTrack } = useVoiceAssistant();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const transcriptions = useTranscriptions();
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const elapsed = useElapsed(true);
  const scroller = useRef<HTMLDivElement>(null);

  useDataChannel("receptionist.events", (msg) => {
    try {
      const ev = JSON.parse(new TextDecoder().decode(msg.payload)) as { tool: string; status: string };
      setEvents((prev) => [...prev, { ...ev, at: Date.now() }]);
    } catch {
      /* ignore malformed */
    }
  });

  const lines = useMemo(
    () =>
      transcriptions
        .filter((t) => t.text.trim())
        .map((t) => ({
          id: t.streamInfo.id,
          text: t.text,
          ts: t.streamInfo.timestamp,
          caller: t.participantInfo.identity === identity,
        }))
        .sort((a, b) => a.ts - b.ts),
    [transcriptions, identity],
  );

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [lines.length]);

  const status =
    state === "speaking" ? "Speaking" : state === "thinking" ? "Thinking" : state === "listening" ? "Listening" : "Connecting";

  return (
    <div className={cn("grid gap-5", compact ? "grid-cols-1" : "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]")}>
      <div className="surface-card flex flex-col items-center gap-4 px-6 py-8">
        <p className="label-caps text-primary">{businessName} · Line 01</p>
        <span className="inline-flex items-center gap-2 rounded-full bg-surface-low px-3 py-1 text-sm font-medium">
          <span className="size-2 rounded-full bg-success" />
          Connected — {status}…
          <span className="tabular-nums text-primary" data-testid="call-timer">{elapsed}</span>
        </span>
        <Orb active speaking={state === "speaking"} />
        <div className="h-10 w-48 text-primary">
          {audioTrack ? (
            <BarVisualizer state={state} trackRef={audioTrack} barCount={9} className="h-full w-full [&>span]:bg-primary/80 [&>span]:rounded-full" />
          ) : null}
        </div>
        <div className="flex items-center gap-6">
          <RoundButton
            label={isMicrophoneEnabled ? "Mute" : "Unmute"}
            onClick={() => void localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
          >
            {isMicrophoneEnabled ? <MicOff /> : <Mic />}
          </RoundButton>
          <RoundButton label="End call" danger onClick={() => void room.disconnect()}>
            <PhoneOff />
          </RoundButton>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        <div className="surface-card flex min-h-64 flex-col">
          <div className="flex items-center justify-between border-b px-5 py-3.5">
            <h3 className="flex items-center gap-2 font-semibold">
              <MessageSquareText className="size-4 text-primary" /> Live transcript
            </h3>
            <span className="rounded-full bg-mint px-2 py-0.5 text-xs font-semibold text-primary">● Real-time</span>
          </div>
          <div ref={scroller} className="flex max-h-80 flex-col gap-3 overflow-y-auto p-5" data-testid="live-transcript">
            {lines.length === 0 ? (
              <p className="text-sm text-muted-foreground">Ava is joining the call…</p>
            ) : (
              lines.map((l) => (
                <div key={l.id} className={cn("flex flex-col gap-1", l.caller ? "items-end" : "items-start")}>
                  {!l.caller ? (
                    <span className="inline-flex items-center gap-1 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      <Sparkles className="size-3" /> AI Agent
                    </span>
                  ) : null}
                  <p
                    className={cn(
                      "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
                      l.caller ? "rounded-tr-sm bg-surface-low" : "rounded-tl-sm bg-mint",
                    )}
                  >
                    {l.text}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="surface-card p-5">
          <h3 className="mb-3 flex items-center gap-2 font-semibold">
            <Sparkles className="size-4 text-primary" /> What the AI is doing
          </h3>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">Listening. Actions appear here as Ava uses her tools.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {events.map((e, i) => (
                <li key={i} className="flex items-start gap-3">
                  <CheckCircle2 className={cn("mt-0.5 size-5", e.status === "ok" ? "text-primary" : "text-warning")} />
                  <div>
                    <p className="text-sm font-medium">{TOOL_LABELS[e.tool] ?? e.tool}</p>
                    <p className="text-xs text-muted-foreground">
                      {e.status === "ok" ? "Done" : e.status.replace("_", " ")}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function RoundButton({
  label,
  danger,
  onClick,
  children,
}: {
  label: string;
  danger?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} className="flex flex-col items-center gap-1.5 text-xs font-medium">
      <span
        className={cn(
          "flex size-12 items-center justify-center rounded-full transition-colors [&_svg]:size-5",
          danger ? "bg-destructive text-white hover:bg-destructive/90" : "bg-surface-container text-foreground hover:bg-secondary",
        )}
      >
        {children}
      </span>
      {label}
    </button>
  );
}
