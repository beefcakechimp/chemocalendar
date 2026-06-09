"use client";

import * as React from "react";
import useSWR from "swr";
import { listRegimensMeta } from "@/lib/api";
import { RegimenMeta } from "@/lib/types";
import { sortRegimenMeta } from "@/lib/utils";
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  ListItemButton,
  Stack,
  Chip,
  InputAdornment,
  Skeleton,
  Alert,
  Collapse,
  Button,
} from "@mui/material";
import Link from "next/link";

const UNSPECIFIED = "Unspecified disease state";

const HOW_TO_STEPS: { title: string; body: string }[] = [
  {
    title: "Find a regimen",
    body: "Browse the library below — regimens are grouped by disease state. Expand a group or search by name to locate the protocol you need.",
  },
  {
    title: "Open the calendar generator",
    body: "Click a regimen to load it into the calendar generator, or use the Generate Calendar action to start and pick a regimen there.",
  },
  {
    title: "Configure the cycle",
    body: "Set the start date, cycle length, and phase or cycle number. Adjust each agent's dose and treatment days, and choose a dosing variant where alternatives are offered.",
  },
  {
    title: "Preview & export",
    body: "Generate a live preview to check the schedule, then export a print-ready DOCX calendar with per-drug administration instructions.",
  },
  {
    title: "Manage regimens",
    body: "Add, edit, rename, or remove regimens and their agents on the Regimens page so the library stays current.",
  },
];

function ActionCard({
  href,
  icon,
  title,
  desc,
  primary = false,
}: {
  href: string;
  icon: string;
  title: string;
  desc: string;
  primary?: boolean;
}) {
  return (
    <Card
      component={Link}
      href={href}
      variant="outlined"
      sx={{
        flex: 1,
        textDecoration: "none",
        ...(primary
          ? { background: "linear-gradient(135deg, #0f4c81 0%, #1a6bb5 100%)", border: "none" }
          : {}),
        transition: "all 0.15s",
        "&:hover": {
          boxShadow: "0 4px 12px rgba(0,0,0,0.10)",
          ...(primary ? {} : { borderColor: "#0f4c81", "& .action-icon": { background: "#0f4c81", color: "#fff" } }),
        },
      }}
    >
      <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, py: 2, px: 2.5, "&:last-child": { pb: 2 } }}>
        <Box
          className="action-icon"
          sx={{
            width: 42,
            height: 42,
            borderRadius: "9px",
            background: primary ? "rgba(255,255,255,0.18)" : "#f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "1.2rem",
            color: primary ? "#fff" : "#475569",
            transition: "all 0.15s",
            flexShrink: 0,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.95rem", color: primary ? "#fff" : "#1e293b", mb: 0.2 }}>
            {title}
          </Typography>
          <Typography sx={{ fontSize: "0.78rem", color: primary ? "rgba(255,255,255,0.8)" : "#64748b" }}>
            {desc}
          </Typography>
        </Box>
        <Box sx={{ ml: 1, color: primary ? "#fff" : "#94a3b8", fontSize: "0.9rem", flexShrink: 0 }}>→</Box>
      </CardContent>
    </Card>
  );
}

function InstructionsCard() {
  const [open, setOpen] = React.useState(true);
  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent sx={{ p: 0, "&:last-child": { pb: open ? 2.5 : 0 } }}>
        <Box
          onClick={() => setOpen((o) => !o)}
          sx={{
            px: 2.5,
            py: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            borderBottom: open ? "1px solid #e2e8f0" : "none",
            "&:hover": { background: "#f8fafc" },
          }}
        >
          <Box>
            <Typography sx={{ fontWeight: 600, fontSize: "0.95rem", color: "#1e293b" }}>
              How to use ChemoCalendar
            </Typography>
            <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>
              Build a treatment-cycle calendar in a few steps
            </Typography>
          </Box>
          <Box
            sx={{
              color: "#94a3b8",
              fontSize: "0.8rem",
              transform: open ? "rotate(90deg)" : "none",
              transition: "transform 0.15s",
            }}
          >
            ▸
          </Box>
        </Box>
        <Collapse in={open}>
          <Box sx={{ px: 2.5, pt: 2.25 }}>
            <Stack spacing={1.75}>
              {HOW_TO_STEPS.map((step, i) => (
                <Box key={i} sx={{ display: "flex", gap: 1.5, alignItems: "flex-start" }}>
                  <Box
                    sx={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      background: "#e8f2fc",
                      color: "#0f4c81",
                      fontSize: "0.78rem",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      mt: 0.1,
                    }}
                  >
                    {i + 1}
                  </Box>
                  <Box>
                    <Typography sx={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b", mb: 0.15 }}>
                      {step.title}
                    </Typography>
                    <Typography sx={{ fontSize: "0.8rem", color: "#64748b", lineHeight: 1.5 }}>
                      {step.body}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Stack>
            <Box
              sx={{
                mt: 2.25,
                px: 1.75,
                py: 1.25,
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "6px",
              }}
            >
              <Typography sx={{ fontSize: "0.78rem", color: "#92400e", lineHeight: 1.5 }}>
                <Box component="span" sx={{ fontWeight: 700 }}>Clinical support tool.</Box>{" "}
                Generated calendars are aids for scheduling only. Always verify doses, days, and
                supportive care against the source protocol and order set before use.
              </Typography>
            </Box>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}

function RegimenCard({ meta }: { meta: RegimenMeta }) {
  return (
    <ListItemButton
      component={Link}
      href={`/calendar?regimen=${encodeURIComponent(meta.name)}`}
      sx={{
        borderRadius: "6px",
        mb: 0.25,
        px: 1.5,
        py: 1,
        border: "1px solid transparent",
        transition: "all 0.15s",
        "&:hover": {
          background: "#f0f7ff",
          border: "1px solid #bfdbfe",
        },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }} noWrap>
            {meta.name}
          </Typography>
          <Chip
            label={meta.on_study ? "On Study" : "Off Protocol"}
            size="small"
            sx={{
              height: 18,
              fontSize: "0.65rem",
              fontWeight: 600,
              background: meta.on_study ? "#dbeafe" : "#f0fdf4",
              color: meta.on_study ? "#1d4ed8" : "#15803d",
              border: "none",
              flexShrink: 0,
            }}
          />
        </Box>
      </Box>
      <Box sx={{ ml: 1, color: "#94a3b8", fontSize: "0.75rem" }}>→</Box>
    </ListItemButton>
  );
}

function DiseaseGroup({
  disease,
  items,
  expanded,
  onToggle,
}: {
  disease: string;
  items: RegimenMeta[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const unspecified = disease === UNSPECIFIED;
  return (
    <Box sx={{ mb: 0.5 }}>
      <Box
        onClick={onToggle}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          px: 1.5,
          py: 1,
          borderRadius: "6px",
          cursor: "pointer",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          "&:hover": { background: "#f1f5f9" },
        }}
      >
        <Box
          sx={{
            color: "#64748b",
            fontSize: "0.75rem",
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform 0.15s",
            width: 12,
            textAlign: "center",
          }}
        >
          ▸
        </Box>
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: "0.8rem",
            color: unspecified ? "#94a3b8" : "#0f4c81",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            flex: 1,
          }}
          noWrap
        >
          {disease}
        </Typography>
        <Chip
          label={items.length}
          size="small"
          sx={{ height: 20, minWidth: 28, fontSize: "0.68rem", fontWeight: 600, background: "#e2e8f0", color: "#475569" }}
        />
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ pt: 0.5, pl: 1.5 }}>
          {items.map((m) => (
            <RegimenCard key={m.name} meta={m} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export default function DashboardPage() {
  const { data: metas, error, isLoading } = useSWR("regimens/meta", listRegimensMeta);
  const [q, setQ] = React.useState("");
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());

  // Group regimens by disease state, ordered disease → on/off-study → name.
  const groups = React.useMemo<[string, RegimenMeta[]][]>(() => {
    const sorted = sortRegimenMeta(metas || [], "status");
    const qq = q.trim().toLowerCase();
    const filtered = qq
      ? sorted.filter((m) => m.name.toLowerCase().includes(qq) || (m.disease_state || "").toLowerCase().includes(qq))
      : sorted;
    const map = new Map<string, RegimenMeta[]>();
    for (const m of filtered) {
      const key = m.disease_state?.trim() || UNSPECIFIED;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(m);
    }
    return Array.from(map.entries());
  }, [metas, q]);

  const totalCount = metas?.length ?? 0;
  const searching = q.trim().length > 0;
  // While searching, force every matching group open so results are never hidden.
  const isExpanded = (disease: string) => searching || !collapsed.has(disease);

  const toggleGroup = (disease: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(disease)) next.delete(disease);
      else next.add(disease);
      return next;
    });

  const collapseAll = () => setCollapsed(new Set(groups.map(([d]) => d)));
  const expandAll = () => setCollapsed(new Set());

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>
          Dashboard
        </Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>
          Chemotherapy regimen scheduling and calendar generation
        </Typography>
      </Box>

      {/* Primary actions */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        <ActionCard
          href="/calendar"
          icon="◫"
          title="Generate Calendar"
          desc="Schedule a chemo cycle and export a print-ready DOCX"
          primary
        />
        <ActionCard
          href="/regimens"
          icon="≡"
          title="Manage Regimens"
          desc={isLoading ? "View and edit saved regimens" : `Edit the ${totalCount} saved regimen${totalCount !== 1 ? "s" : ""}`}
        />
      </Stack>

      {/* How to use */}
      <InstructionsCard />

      {/* Regimen browser */}
      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          {/* Header */}
          <Box sx={{ px: 2.5, pt: 2.25, pb: 1.5, borderBottom: "1px solid #e2e8f0" }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, mb: 1.25 }}>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>
                  Regimen Library
                </Typography>
                <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>
                  Grouped by disease state — click a group to expand, or a regimen to open it in the calendar generator
                </Typography>
              </Box>
              <TextField
                placeholder="Search regimens…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                size="small"
                sx={{ width: 220 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Box component="span" sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>⌕</Box>
                    </InputAdornment>
                  ),
                }}
              />
            </Box>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Button
                size="small"
                onClick={expandAll}
                disabled={searching}
                sx={{ fontSize: "0.72rem", color: "#0f4c81", minWidth: 0, px: 1 }}
              >
                Expand all
              </Button>
              <Button
                size="small"
                onClick={collapseAll}
                disabled={searching}
                sx={{ fontSize: "0.72rem", color: "#0f4c81", minWidth: 0, px: 1 }}
              >
                Collapse all
              </Button>
              {searching && (
                <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                  Showing search results
                </Typography>
              )}
            </Stack>
          </Box>

          {/* List */}
          <Box sx={{ px: 1.5, py: 1.5, maxHeight: 520, overflowY: "auto" }}>
            {error && (
              <Alert severity="error" sx={{ mx: 1, mb: 1 }}>
                {String((error as any)?.message || error)}
              </Alert>
            )}
            {isLoading && (
              <Box sx={{ px: 1 }}>
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} height={52} sx={{ mb: 0.5, borderRadius: "6px" }} />
                ))}
              </Box>
            )}
            {!isLoading && !error && groups.length === 0 && (
              <Box sx={{ textAlign: "center", py: 4 }}>
                <Typography sx={{ color: "#94a3b8", fontSize: "0.875rem" }}>
                  {q ? "No regimens match your search." : "No regimens yet. Add one to get started."}
                </Typography>
                {!q && (
                  <Box
                    component={Link}
                    href="/regimens"
                    sx={{ display: "inline-block", mt: 1.5, fontSize: "0.8rem", color: "#0f4c81", textDecoration: "none", fontWeight: 500 }}
                  >
                    Add regimens →
                  </Box>
                )}
              </Box>
            )}
            {!isLoading && !error && groups.map(([disease, items]) => (
              <DiseaseGroup
                key={disease}
                disease={disease}
                items={items}
                expanded={isExpanded(disease)}
                onToggle={() => toggleGroup(disease)}
              />
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
