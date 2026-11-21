"use client";

import { createContext, useContext } from "react";

import type { Business, Me } from "@/lib/types";

export interface DashboardCtx {
  me: Me;
  business: Business;
  tz: string;
  reloadBusiness: () => Promise<void>;
  openCall: () => void;
}

export const DashboardContext = createContext<DashboardCtx | null>(null);

export function useDashboard(): DashboardCtx {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used inside the dashboard layout");
  return ctx;
}
