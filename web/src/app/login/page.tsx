"use client";

import { Loader2, LockKeyhole } from "lucide-react";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";

import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, json } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/login", { method: "POST", ...json({ email, password }) });
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="surface-card flex w-full max-w-sm flex-col gap-5 p-7">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-bold">Sign in</h1>
        <p className="text-sm text-muted-foreground">Receptionist dashboard for your team.</p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="username" required value={email}
               onChange={(e) => setEmail(e.target.value)} className="h-10" />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoComplete="current-password" required minLength={8}
               value={password} onChange={(e) => setPassword(e.target.value)} className="h-10" />
      </div>
      {error ? (
        <p role="alert" className="rounded-lg bg-[#ffdad6] px-3 py-2 text-sm text-[#93000a]">{error}</p>
      ) : null}
      <Button type="submit" disabled={busy} className="btn-gradient h-10 rounded-lg text-white">
        {busy ? <Loader2 className="animate-spin" /> : <LockKeyhole />} Sign in
      </Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-gradient-to-b from-mint/60 to-background px-5">
      <Brand subtitle="AI Receptionist" />
      <Suspense>
        <LoginForm />
      </Suspense>
      <p className="text-xs text-muted-foreground">Accounts are created by an admin (make create-admin).</p>
    </div>
  );
}
