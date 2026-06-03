import { RegimenMeta } from "@/lib/types";

export type SortBy = "status" | "name" | "date";

export function sortRegimenMeta(metas: RegimenMeta[], sortBy: SortBy): RegimenMeta[] {
  const sorted = [...metas];
  if (sortBy === "status") {
    sorted.sort((a, b) => {
      if (a.on_study !== b.on_study) return a.on_study ? -1 : 1;
      const ds = (a.disease_state || "").localeCompare(b.disease_state || "");
      if (ds !== 0) return ds;
      return a.name.localeCompare(b.name);
    });
  } else if (sortBy === "name") {
    sorted.sort((a, b) => a.name.localeCompare(b.name));
  } else {
    sorted.sort((a, b) => {
      if (!a.updated_at && !b.updated_at) return 0;
      if (!a.updated_at) return 1;
      if (!b.updated_at) return -1;
      return b.updated_at.localeCompare(a.updated_at);
    });
  }
  return sorted;
}
