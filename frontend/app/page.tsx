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
import CalendarMonthRoundedIcon from "@mui/icons-material/CalendarMonthRounded";
import MedicationRoundedIcon from "@mui/icons-material/MedicationRounded";
import MenuBookRoundedIcon from "@mui/icons-material/MenuBookRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";

const UNSPECIFIED = "Unspecified disease state";

function ActionCard({
  href,
  icon,
  title,
  desc,
  primary = false,
}: {
  href: string;
  icon: React.ReactNode;
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
            color: primary ? "#fff" : "#475569",
            transition: "all 0.15s",
            flexShrink: 0,
            "& svg": { fontSize: "1.3rem" },
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
        <Box sx={{ ml: 1, color: primary ? "#fff" : "#94a3b8", display: "flex", flexShrink: 0 }}>
          <ArrowForwardRoundedIcon sx={{ fontSize: "1rem" }} />
        </Box>
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
      <Box sx={{ ml: 1, color: "#94a3b8", display: "flex" }}>
        <ChevronRightRoundedIcon sx={{ fontSize: "1rem" }} />
      </Box>
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
            display: "flex",
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform 0.15s",
          }}
        >
          <ChevronRightRoundedIcon sx={{ fontSize: "1rem" }} />
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
        <Box
          component={Link}
          href="/guide"
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.5,
            mt: 0.75,
            fontSize: "0.8rem",
            fontWeight: 500,
            color: "#0f4c81",
            textDecoration: "none",
            "&:hover": { textDecoration: "underline" },
          }}
        >
          <MenuBookRoundedIcon sx={{ fontSize: "0.95rem" }} />
          New here? Read the how-to guide
          <ArrowForwardRoundedIcon sx={{ fontSize: "0.85rem" }} />
        </Box>
      </Box>

      {/* Primary actions */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        <ActionCard
          href="/calendar"
          icon={<CalendarMonthRoundedIcon />}
          title="Generate Calendar"
          desc="Schedule a chemo cycle and export a print-ready DOCX"
          primary
        />
        <ActionCard
          href="/regimens"
          icon={<MedicationRoundedIcon />}
          title="Manage Regimens"
          desc={isLoading ? "View and edit saved regimens" : `Edit the ${totalCount} saved regimen${totalCount !== 1 ? "s" : ""}`}
        />
      </Stack>

      {/* Regimen browser */}
      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          {/* Header */}
          <Box sx={{ px: 2.5, pt: 2.25, pb: 1.5, borderBottom: "1px solid #e2e8f0" }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, mb: 1.25, flexWrap: "wrap" }}>
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
                sx={{ width: { xs: "100%", sm: 220 } }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchRoundedIcon sx={{ fontSize: "1rem", color: "#94a3b8" }} />
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
