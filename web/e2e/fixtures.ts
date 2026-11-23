// Local test account for end-to-end tests only (created by `make e2e-user`, never used in
// production). Override with E2E_EMAIL / E2E_PASSWORD.
export const E2E_EMAIL = process.env.E2E_EMAIL ?? "owner@luma.example.com";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "luma-e2e-owner-pass";
export const AGENT_TOKEN = process.env.AGENT_SERVICE_TOKEN ?? "dev-agent-token";
export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8010";
