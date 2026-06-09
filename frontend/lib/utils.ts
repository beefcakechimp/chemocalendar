import { RegimenMeta } from "@/lib/types";

export type SortBy = "status" | "name" | "date";

export function sortRegimenMeta(metas: RegimenMeta[], sortBy: SortBy): RegimenMeta[] {
  const sorted = [...metas];
  if (sortBy === "status") {
    // Group by disease state first, then on/off-study status, then name.
    sorted.sort((a, b) => {
      const ad = a.disease_state || "";
      const bd = b.disease_state || "";
      if (ad !== bd) {
        if (!ad) return 1; // regimens with no disease state sort last
        if (!bd) return -1;
        return ad.localeCompare(bd);
      }
      if (a.on_study !== b.on_study) return a.on_study ? -1 : 1;
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
