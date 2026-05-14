"use client";

import * as React from "react";
import useSWR from "swr";
import { listRegimensDetailed } from "@/lib/api";
import { RegimenSummary } from "@/lib/types";
import {
  Box, Card, CardContent, Typography, TextField, List, ListItemButton,
  Stack, InputAdornment, Skeleton, Alert,
} from "@mui/material";
import Link from "next/link";

function StatCard({ label, value, sub, color = "#0f4c81" }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <Card variant="outlined" sx={{ flex: 1, minWidth: 160, background: "#fff", transition: "box-shadow 0.15s", "&:hover": { boxShadow: "0 4px 12px rgba(0,0,0,0.08)" } }}>
      <CardContent sx={{ py: 2, px: 2.5, "&:last-child": { pb: 2 } }}>
        <Typography sx={{ fontSize: "0.72rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.75 }}>{label}</Typography>
        <Typography sx={{ fontSize: "2rem", fontWeight: 700, color, lineHeight: 1, letterSpacing: "-0.03em" }}>{value}</Typography>
        {sub && <Typography sx={{ fontSize: "0.75rem", color: "#94a3b8", mt: 0.5 }}>{sub}</Typography>}
      </CardContent>
    </Card>
  );
}

function RegimenRow({ r }: { r: RegimenSummary }) {
  return (
    <ListItemButton
      component={Link}
      href={`/calendar?regimen=${encodeURIComponent(r.name)}`}
      sx={{ borderRadius: "6px", mb: 0.25, px: 1.5, py: 0.875, border: "1px solid transparent", transition: "all 0.15s", "&:hover": { background: "#f0f7ff", border: "1px solid #bfdbfe" } }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }} noWrap>{r.name}</Typography>
        {r.disease_state && <Typography sx={{ fontSize: "0.72rem", color: "#64748b", mt: 0.1 }} noWrap>{r.disease_state}</Typography>}
      </Box>
      <Box sx={{ ml: 1, color: "#94a3b8", fontSize: "0.75rem" }}>→</Box>
    </ListItemButton>
  );
}

export default function DashboardPage() {
  const { data: summaries, error, isLoading } = useSWR("regimens-detailed", listRegimensDetailed);
  const [q, setQ] = React.useState("");
  const [folderOpen, setFolderOpen] = React.useState({ onStudy: true, offProtocol: true });
  const [dsOpen, setDsOpen] = React.useState<Record<string, boolean>>({});

  const grouped = React.useMemo(() => {
    if (!summaries) return null;
    const onStudy: Record<string, RegimenSummary[]> = {};
    const offProtocol: Record<string, RegimenSummary[]> = {};
    for (const r of [...summaries].sort((a, b) => a.name.localeCompare(b.name))) {
      const ds = r.disease_state?.trim() || "(None)";
      const bucket = r.on_study ? onStudy : offProtocol;
      (bucket[ds] ??= []).push(r);
    }
    return { onStudy, offProtocol };
  }, [summaries]);

  const searchResults = React.useMemo(() => {
    const qq = q.trim().toLowerCase();
    return qq ? (summaries ?? []).filter(r => r.name.toLowerCase().includes(qq)).sort((a, b) => a.name.localeCompare(b.name)) : [];
  }, [summaries, q]);

  const totalCount = summaries?.length ?? 0;
  const onStudyCount = summaries?.filter(r => r.on_study).length ?? 0;

  const toggleDs = (key: string) => setDsOpen(p => ({ ...p, [key]: !(p[key] ?? true) }));

  const DsGroup = ({ folderKey, ds, items }: { folderKey: string; ds: string; items: RegimenSummary[] }) => {
    const gKey = `${folderKey}:${ds}`;
    const isOpen = dsOpen[gKey] ?? true;
    return (
      <Box sx={{ mb: 0.25 }}>
        <Box
          onClick={() => toggleDs(gKey)}
          sx={{ display: "flex", alignItems: "center", px: 1.5, py: 0.5, cursor: "pointer", userSelect: "none", borderRadius: "5px", "&:hover": { background: "#f1f5f9" } }}
        >
          <Box component="span" sx={{ fontSize: "0.55rem", mr: 0.75, color: "#94a3b8", display: "inline-block", transition: "transform 0.15s", transform: isOpen ? "rotate(90deg)" : "none" }}>▶</Box>
          <Typography sx={{ fontWeight: 600, fontSize: "0.75rem", color: "#64748b", flex: 1, fontStyle: ds === "(None)" ? "italic" : "normal" }}>{ds}</Typography>
          <Typography sx={{ fontSize: "0.68rem", color: "#94a3b8" }}>{items.length}</Typography>
        </Box>
        {isOpen && (
          <List disablePadding dense sx={{ pl: 1.5 }}>
            {items.map(r => <RegimenRow key={r.name} r={r} />)}
          </List>
        )}
      </Box>
    );
  };

  const FolderSection = ({ title, fKey, groups, dotColor }: { title: string; fKey: "onStudy" | "offProtocol"; groups: Record<string, RegimenSummary[]>; dotColor: string }) => {
    const count = Object.values(groups).reduce((s, a) => s + a.length, 0);
    if (count === 0) return null;
    const isOpen = folderOpen[fKey];
    const sortedDs = Object.keys(groups).sort((a, b) => a === "(None)" ? 1 : b === "(None)" ? -1 : a.localeCompare(b));
    return (
      <Box sx={{ mb: 1 }}>
        <Box
          onClick={() => setFolderOpen(p => ({ ...p, [fKey]: !p[fKey] }))}
          sx={{ display: "flex", alignItems: "center", px: 1.5, py: 0.875, cursor: "pointer", userSelect: "none", borderRadius: "6px", "&:hover": { background: "#f1f5f9" } }}
        >
          <Box component="span" sx={{ fontSize: "0.6rem", mr: 0.75, color: "#475569", display: "inline-block", transition: "transform 0.15s", transform: isOpen ? "rotate(90deg)" : "none" }}>▶</Box>
          <Box sx={{ width: 8, height: 8, borderRadius: "50%", background: dotColor, mr: 1, flexShrink: 0 }} />
          <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", color: "#1e293b", flex: 1 }}>{title}</Typography>
          <Box sx={{ px: 0.75, py: 0.1, borderRadius: "10px", background: dotColor + "20" }}>
            <Typography sx={{ fontSize: "0.68rem", color: dotColor, fontWeight: 700 }}>{count}</Typography>
          </Box>
        </Box>
        {isOpen && (
          <Box sx={{ ml: 1 }}>
            {sortedDs.map(ds => <DsGroup key={ds} folderKey={fKey} ds={ds} items={groups[ds]} />)}
          </Box>
        )}
      </Box>
    );
  };

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>Dashboard</Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>Chemotherapy regimen scheduling and calendar generation</Typography>
      </Box>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        <StatCard label="Regimens saved" value={isLoading ? "—" : totalCount} sub="in database" />
        <StatCard label="On Study" value={isLoading ? "—" : onStudyCount} sub="active protocols" color="#1d4ed8" />
        <Card variant="outlined" sx={{ flex: 2, background: "linear-gradient(135deg, #0f4c81 0%, #1a6bb5 100%)", border: "none" }}>
          <CardContent sx={{ py: 2, px: 2.5, "&:last-child": { pb: 2 }, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Box>
              <Typography sx={{ fontSize: "0.72rem", fontWeight: 600, color: "rgba(255,255,255,0.7)", textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.5 }}>Generate a calendar</Typography>
              <Typography sx={{ fontSize: "0.95rem", color: "#fff", fontWeight: 500, lineHeight: 1.4 }}>Select a regimen and export a print-ready DOCX calendar</Typography>
            </Box>
            <Box component={Link} href="/calendar" sx={{ ml: 2, px: 2, py: 0.875, background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)", borderRadius: "6px", color: "#fff", fontSize: "0.85rem", fontWeight: 600, textDecoration: "none", whiteSpace: "nowrap", transition: "all 0.15s", "&:hover": { background: "rgba(255,255,255,0.25)" } }}>
              Open →
            </Box>
          </CardContent>
        </Card>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        {[
          { href: "/calendar", label: "Generate Calendar", desc: "Schedule a chemo cycle and export", icon: "◫" },
          { href: "/regimens", label: "Manage Regimens", desc: "View and browse saved regimens", icon: "≡" },
        ].map((item) => (
          <Card key={item.href} component={Link} href={item.href} variant="outlined" sx={{ flex: 1, textDecoration: "none", transition: "all 0.15s", "&:hover": { boxShadow: "0 4px 12px rgba(0,0,0,0.08)", borderColor: "#0f4c81", "& .action-icon": { background: "#0f4c81", color: "#fff" } } }}>
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, py: 1.75, px: 2.5, "&:last-child": { pb: 1.75 } }}>
              <Box className="action-icon" sx={{ width: 38, height: 38, borderRadius: "8px", background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.1rem", color: "#475569", transition: "all 0.15s", flexShrink: 0 }}>{item.icon}</Box>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b", mb: 0.15 }}>{item.label}</Typography>
                <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>{item.desc}</Typography>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Box sx={{ px: 2.5, pt: 2.25, pb: 1.5, borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography sx={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>Regimen Library</Typography>
              <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>Click any regimen to open in the calendar generator</Typography>
            </Box>
            <TextField
              placeholder="Search regimens…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              size="small"
              sx={{ width: 220 }}
              InputProps={{ startAdornment: <InputAdornment position="start"><Box component="span" sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>⌕</Box></InputAdornment> }}
            />
          </Box>

          <Box sx={{ px: 1.5, py: 1.5, maxHeight: 480, overflowY: "auto" }}>
            {error && <Alert severity="error" sx={{ mx: 1, mb: 1 }}>{String((error as any)?.message || error)}</Alert>}

            {isLoading && (
              <Box sx={{ px: 1 }}>
                {[...Array(5)].map((_, i) => <Skeleton key={i} height={52} sx={{ mb: 0.5, borderRadius: "6px" }} />)}
              </Box>
            )}

            {!isLoading && !error && (
              q.trim() ? (
                searchResults.length > 0 ? (
                  <List disablePadding dense>
                    {searchResults.map(r => <RegimenRow key={r.name} r={r} />)}
                  </List>
                ) : (
                  <Box sx={{ textAlign: "center", py: 4 }}>
                    <Typography sx={{ color: "#94a3b8", fontSize: "0.875rem" }}>No regimens match your search.</Typography>
                  </Box>
                )
              ) : grouped ? (
                <Box>
                  <FolderSection title="On Study" fKey="onStudy" groups={grouped.onStudy} dotColor="#1d4ed8" />
                  <FolderSection title="Off Protocol" fKey="offProtocol" groups={grouped.offProtocol} dotColor="#15803d" />
                  {totalCount === 0 && (
                    <Box sx={{ textAlign: "center", py: 4 }}>
                      <Typography sx={{ color: "#94a3b8", fontSize: "0.875rem" }}>No regimens yet. Add one to get started.</Typography>
                      <Box component={Link} href="/regimens" sx={{ display: "inline-block", mt: 1.5, fontSize: "0.8rem", color: "#0f4c81", textDecoration: "none", fontWeight: 500 }}>Add regimens →</Box>
                    </Box>
                  )}
                </Box>
              ) : null
            )}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
