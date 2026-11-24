"use client";

import {
  Bell,
  BookOpenText,
  CalendarDays,
  LayoutDashboard,
  ListChecks,
  LogOut,
  MessageSquareMore,
  Mic,
  PhoneCall,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AiActivePill, Brand } from "@/components/brand";
import { LiveCall } from "@/components/call/live-call";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { WakingBanner } from "@/components/waking-banner";
import { api, ApiError } from "@/lib/api";
import { initials } from "@/lib/format";
import type { Business, Me, Overview, PublicBusiness } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

import { DashboardContext } from "./context";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/calls", label: "Calls", icon: PhoneCall },
  { href: "/dashboard/appointments", label: "Appointments", icon: CalendarDays },
  { href: "/dashboard/waitlist", label: "Waitlist", icon: ListChecks },
  { href: "/dashboard/messages", label: "Messages", icon: MessageSquareMore },
  { href: "/dashboard/team", label: "Team", icon: Users },
  { href: "/dashboard/knowledge", label: "Knowledge", icon: BookOpenText },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

// The mobile bar has room for five.
const MOBILE_NAV = ["/dashboard", "/dashboard/calls", "/dashboard/appointments", "/dashboard/team", "/dashboard/settings"];

const TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/calls": "Calls",
  "/dashboard/appointments": "Appointments",
  "/dashboard/messages": "Messages & callbacks",
  "/dashboard/waitlist": "Waitlist",
  "/dashboard/team": "Team & schedules",
  "/dashboard/knowledge": "Knowledge",
  "/dashboard/settings": "Settings",
  "/dashboard/setup": "Set up Receptly",
};

const BLANK_BUSINESS: Business = {
  name: "",
  timezone: "UTC",
  address: "",
  phone: "",
  website: "",
  currency: "USD",
  greeting: "",
  recording_notice: "This call may be recorded and transcribed.",
  voice: "Aoede",
  language: "en-US",
  handoff_number: "",
  staff_notify_email: "",
  email_signature: "",
  extra_instructions: "",
  sms_confirmations: true,
  sms_reminders: true,
  reminder_hours: 24,
  waitlist_enabled: true,
  waitlist_hold_minutes: 30,
  setup_completed: false,
};

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [business, setBusiness] = useState<Business | null>(null);
  const [callOpen, setCallOpen] = useState(false);
  const { data: pub } = useApi<PublicBusiness>("/api/public/business");
  const { data: stats } = useApi<Overview>(me ? "/api/stats/overview?days=7" : null, { refreshMs: 30000 });

  const reloadBusiness = useCallback(async () => {
    setBusiness(await api<Business>("/api/settings/business"));
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const m = await api<Me>("/api/me");
        if (!alive) return;
        setMe(m);
        try {
          setBusiness(await api<Business>("/api/settings/business"));
        } catch (e) {
          // A brand-new install has no business yet: start the setup wizard.
          if (e instanceof ApiError && e.status === 404) {
            setBusiness(BLANK_BUSINESS);
            if (!window.location.pathname.startsWith("/dashboard/setup")) router.replace("/dashboard/setup");
          } else throw e;
        }
      } catch {
        /* api() redirects to /login on 401 */
      }
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  }

  if (!me || !business) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <WakingBanner ready={false} />
        <div className="flex flex-col items-center gap-3 text-sm text-muted-foreground">
          <span className="size-10 animate-pulse rounded-xl bg-primary/20" />
          Loading dashboard…
        </div>
      </div>
    );
  }

  const title =
    TITLES[pathname] ?? (pathname.startsWith("/dashboard/calls/") ? "Call detail" : "Dashboard");
  const urgent = stats?.messages_urgent ?? 0;
  const openMessages = stats?.messages_open ?? 0;

  return (
    <DashboardContext.Provider
      value={{ me, business, tz: business.timezone, reloadBusiness, openCall: () => setCallOpen(true) }}
    >
      <div className="flex min-h-screen bg-background">
        {/* Sidebar (desktop) */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-sidebar px-4 py-5 lg:flex">
          <Link href="/" className="px-2">
            <Brand subtitle="Voice Agent 2.0" />
          </Link>
          <nav className="mt-8 flex flex-col gap-1">
            {NAV.map((item) => {
              const active = item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-mint text-primary" : "text-muted-foreground hover:bg-surface-low hover:text-foreground",
                  )}
                >
                  <item.icon className="size-[18px]" />
                  {item.label}
                  {item.href === "/dashboard/messages" && openMessages > 0 ? (
                    <span className="ml-auto rounded-full bg-warning/20 px-2 text-xs font-semibold text-[#92400e]">
                      {openMessages}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto rounded-2xl bg-gradient-to-br from-primary to-[#004d43] p-4 text-white">
            <p className="text-sm font-semibold">Test your receptionist</p>
            <p className="mt-1 text-xs text-white/75">Call Ava from the browser to hear changes live.</p>
            <Button
              onClick={() => setCallOpen(true)}
              className="mt-3 h-9 w-full rounded-lg bg-white text-primary hover:bg-white/90"
              data-testid="sidebar-talk"
            >
              <Mic /> Talk to receptionist
            </Button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
          <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur-xl">
            <div className="flex h-[72px] items-center justify-between gap-3 px-5 lg:px-8">
              <div className="flex min-w-0 flex-col">
                <div className="flex items-center gap-2">
                  <span className="label-caps truncate text-primary">{business.name}</span>
                  <AiActivePill />
                </div>
                <h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={() => setCallOpen(true)}
                  className="btn-gradient hidden h-9 rounded-lg px-3.5 text-white sm:inline-flex"
                  data-testid="header-talk"
                >
                  <Mic /> Talk to receptionist
                </Button>
                <Link
                  href="/dashboard/messages"
                  aria-label="Messages"
                  className="relative flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-surface-low"
                >
                  <Bell className="size-5" />
                  {urgent > 0 ? (
                    <span className="absolute right-2.5 top-2.5 size-2 rounded-full bg-destructive ring-2 ring-background" />
                  ) : null}
                </Link>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className="flex size-9 items-center justify-center rounded-full bg-primary-fixed/70 text-sm font-semibold text-[#00201b] ring-2 ring-primary/15"
                    aria-label="Account"
                  >
                    {initials(me.name || me.email)}
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel>
                      <div className="text-sm font-semibold">{me.name || me.email}</div>
                      <div className="text-xs font-normal capitalize text-muted-foreground">{me.role}</div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => void logout()}>
                      <LogOut /> Sign out
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </header>

          <main className="flex-1 px-5 pb-24 pt-6 lg:px-8 lg:pb-10">
            {me.role === "admin" && business.setup_completed === false && !pathname.startsWith("/dashboard/setup") ? (
              <Link
                href="/dashboard/setup"
                className="mx-auto mb-5 flex max-w-6xl items-center gap-3 rounded-2xl border border-primary/25 bg-mint px-4 py-3 text-sm"
                data-testid="setup-banner"
              >
                <Sparkles className="size-4 text-primary" />
                <span className="font-semibold text-primary">Finish setting up Receptly</span>
                <span className="hidden text-muted-foreground sm:inline">
                  Business, hours, team and services, about 15 minutes.
                </span>
                <span className="ml-auto font-semibold text-primary">Continue →</span>
              </Link>
            ) : null}
            {children}
          </main>
        </div>

        {/* Bottom nav (mobile), as in the Stitch mobile screens */}
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t bg-background/95 backdrop-blur lg:hidden">
          {NAV.filter((n) => MOBILE_NAV.includes(n.href)).map((item) => {
            const active = item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn("flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium",
                  active ? "text-primary" : "text-muted-foreground")}
              >
                <item.icon className="size-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <Sheet open={callOpen} onOpenChange={setCallOpen}>
        <SheetContent side="right" className="w-full overflow-y-auto bg-background p-5 sm:max-w-xl">
          <SheetHeader className="px-0">
            <SheetTitle className="text-lg">Talk to receptionist</SheetTitle>
            <SheetDescription>
              A real call with Ava using your current settings. It appears under Calls when you hang up.
            </SheetDescription>
          </SheetHeader>
          {callOpen ? (
            <LiveCall
              compact
              businessName={business.name}
              maxMinutes={pub?.max_call_minutes ?? 10}
              demoMode={pub?.demo_mode ?? false}
            />
          ) : null}
        </SheetContent>
      </Sheet>
    </DashboardContext.Provider>
  );
}
