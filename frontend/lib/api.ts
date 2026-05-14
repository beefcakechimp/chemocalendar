import { CalendarPreviewRequest, CalendarPreviewResponse, Regimen, RegimenSummary } from "@/lib/types";

const API_BASE = "/api";

// 🛡️ The Cold Start Shield: Intercepts and silently handles dead database connections
async function apiFetch<T>(path: string, init?: RequestInit, retries = 3): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      if (res.status >= 500 && retries > 0) {
        console.warn(`Database connection stale (Status: ${res.status}). Retrying silently...`);
        await new Promise((resolve) => setTimeout(resolve, 1500));
        return apiFetch<T>(path, init, retries - 1);
      }
      
      let msg = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        msg = (j as any)?.detail || msg;
      } catch {}
      throw new Error(msg);
    }

    if (res.status === 204 || res.headers.get("content-length") === "0") {
        return {} as T;
    }

    return (await res.json()) as T;
  } catch (e: any) {
    if (retries > 0) {
      console.warn(`Network glitch detected. Retrying silently...`);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      return apiFetch<T>(path, init, retries - 1);
    }
    throw e;
  }
}

export function listRegimens(): Promise<string[]> {
  return apiFetch<string[]>("/regimens");
}

export function listRegimensDetailed(): Promise<RegimenSummary[]> {
  return apiFetch<Regimen[]>("/regimens/all").then(regs =>
    regs.map(r => ({ name: r.name, disease_state: r.disease_state ?? null, on_study: r.on_study }))
  );
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

export async function exportCalendarDocx(
  body: CalendarPreviewRequest
): Promise<{ blob: Blob; filename: string }> {
  let retries = 3;
  while (retries > 0) {
    try {
      const res = await fetch(`${API_BASE}/calendar/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        if (res.status >= 500) {
          retries--;
          await new Promise((resolve) => setTimeout(resolve, 1500));
          continue;
        }
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
    } catch (e) {
      retries--;
      if (retries === 0) throw e;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  }
  throw new Error("Export completely failed after retries.");
}