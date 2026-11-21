"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { LiveCall } from "@/components/call/live-call";
import { WakingBanner } from "@/components/waking-banner";
import type { PublicBusiness } from "@/lib/types";
import { useApi } from "@/lib/use-api";

export default function CallPage() {
  const { data: biz, error } = useApi<PublicBusiness>("/api/public/business");
  return (
    <div className="min-h-screen bg-background">
      <WakingBanner ready={Boolean(biz) || Boolean(error)} />
      <header className="border-b bg-background/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-3 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" /> Back
          </Link>
          <Brand />
          <span className="w-12" />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10">
        <h1 className="mb-6 text-2xl font-bold tracking-tight">Live demo call</h1>
        <LiveCall
          businessName={biz?.name ?? "Luma Hair Studio"}
          maxMinutes={biz?.max_call_minutes ?? 3}
          demoMode={biz?.demo_mode ?? false}
        />
      </main>
    </div>
  );
}
