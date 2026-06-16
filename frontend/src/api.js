import { supabase } from "./supabase.js";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function request(path, opts = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  const headers = { ...opts.headers };
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

export async function uploadMedia(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/media", { method: "POST", body: form });
  // returns { url, media_type }
}

export async function createCast({ caption, media, targets, scheduled_at }) {
  return request("/casts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caption, media, targets, scheduled_at: scheduled_at ?? null }),
  });
  // returns CastOut with jobs[]
}

export async function getCast(id) {
  return request(`/casts/${id}`);
}

export async function getCasts(limit = 10) {
  return request(`/casts?limit=${limit}`);
}

export async function getCastInsights(id) {
  return request(`/casts/${id}/insights`);
}

export async function getAccounts() {
  return request("/accounts");
}

export async function connectAccount(platform) {
  return request(`/accounts/${platform}/connect`, { method: "POST" });
}
