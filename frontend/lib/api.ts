import { CalendarPreviewRequest, CalendarPreviewResponse, Regimen } from "@/lib/types";

/**
 * All requests go to /api/* on the same origin (port 3000).
 * Next.js rewrites these server-side to http://localhost:8000/*
 */
const API_BASE = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = (j as any)?.detail || msg;
    } catch {}
    throw new Error(msg);
  }

  return (await res.json()) as T;
}

export function listRegimens(): Promise<string[]> {
  return apiFetch<string[]>("/regimens");
}

export function getRegimen(name: string): Promise<Regimen> {
  return apiFetch<Regimen>(`/regimens/${encodeURIComponent(name)}`);
}

export function upsertRegimen(body: Regimen): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/regimens", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteRegimen(name: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/regimens/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export function renameRegimen(old_name: string, new_name: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/regimens/rename", {
    method: "POST",
    body: JSON.stringify({ old_name, new_name }),
  });
}

export function previewCalendar(body: CalendarPreviewRequest): Promise<CalendarPreviewResponse> {
  return apiFetch<CalendarPreviewResponse>("/calendar/preview", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listAllRegimensDetailed(): Promise<Regimen[]> {
  return apiFetch<Regimen[]>("/regimens/all");
}

export async function exportCalendarDocx(
  body: CalendarPreviewRequest
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/calendar/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = (j as any)?.detail || msg;
    } catch {}
    throw new Error(msg);
  }

  const cd = res.headers.get("content-disposition") || "";
  let filename = "calendar.docx";
  const m = cd.match(/filename="([^"]+)"/i);
  if (m?.[1]) filename = m[1];

  const blob = await res.blob();
  return { blob, filename };
}