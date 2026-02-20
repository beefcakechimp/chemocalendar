"use client";

import * as React from "react";
import useSWR from "swr";
import { listRegimens, getRegimen } from "@/lib/api";
import { Regimen } from "@/lib/types";
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  List,
  ListItemButton,
  Stack,
  Chip,
  InputAdornment,
  Skeleton,
  Alert,
} from "@mui/material";
import Link from "next/link";

function StatCard({ label, value, sub, color = "#0f4c81" }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <Card
      variant="outlined"
      sx={{
        flex: 1,
        minWidth: 160,
        background: "#fff",
        transition: "box-shadow 0.15s",
        "&:hover": { boxShadow: "0 4px 12px rgba(0,0,0,0.08)" },
      }}
    >
      <CardContent sx={{ py: 2, px: 2.5, "&:last-child": { pb: 2 } }}>
        <Typography sx={{ fontSize: "0.72rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.75 }}>
          {label}
        </Typography>
        <Typography sx={{ fontSize: "2rem", fontWeight: 700, color, lineHeight: 1, letterSpacing: "-0.03em" }}>
          {value}
        </Typography>
        {sub && (
          <Typography sx={{ fontSize: "0.75rem", color: "#94a3b8", mt: 0.5 }}>
            {sub}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function RegimenCard({ name, onClick }: { name: string; onClick?: () => void }) {
  const { data: reg } = useSWR<Regimen>(["regimen", name], () => getRegimen(name));
  return (
    <ListItemButton
      component={Link}
      href={`/calendar?regimen=${encodeURIComponent(name)}`}
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
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.25 }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }} noWrap>
            {name}
          </Typography>
          {reg && (
            <Chip
              label={reg.on_study ? "On Study" : "Off Protocol"}
              size="small"
              sx={{
                height: 18,
                fontSize: "0.65rem",
                fontWeight: 600,
                background: reg.on_study ? "#dbeafe" : "#f0fdf4",
                color: reg.on_study ? "#1d4ed8" : "#15803d",
                border: "none",
              }}
            />
          )}
        </Box>
        {reg?.disease_state && (
          <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }} noWrap>
            {reg.disease_state}
          </Typography>
        )}
      </Box>
      <Box sx={{ ml: 1, color: "#94a3b8", fontSize: "0.75rem" }}>→</Box>
    </ListItemButton>
  );
}

export default function DashboardPage() {
  const { data: names, error, isLoading } = useSWR("regimens", listRegimens);
  const [q, setQ] = React.useState("");

  const filtered = React.useMemo(() => {
    const xs = names || [];
    const qq = q.trim().toLowerCase();
    if (!qq) return xs;
    return xs.filter((n) => n.toLowerCase().includes(qq));
  }, [names, q]);

  const totalCount = names?.length ?? 0;

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

      {/* Stats row */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        <StatCard
          label="Regimens saved"
          value={isLoading ? "—" : totalCount}
          sub="in database"
        />
        <StatCard
          label="Quick actions"
          value="2"
          sub="available"
          color="#0369a1"
        />
        <Card
          variant="outlined"
          sx={{
            flex: 2,
            background: "linear-gradient(135deg, #0f4c81 0%, #1a6bb5 100%)",
            border: "none",
          }}
        >
          <CardContent sx={{ py: 2, px: 2.5, "&:last-child": { pb: 2 }, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Box>
              <Typography sx={{ fontSize: "0.72rem", fontWeight: 600, color: "rgba(255,255,255,0.7)", textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.5 }}>
                Generate a calendar
              </Typography>
              <Typography sx={{ fontSize: "0.95rem", color: "#fff", fontWeight: 500, lineHeight: 1.4 }}>
                Select a regimen and export a print-ready DOCX calendar
              </Typography>
            </Box>
            <Box
              component={Link}
              href="/calendar"
              sx={{
                ml: 2,
                px: 2,
                py: 0.875,
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.25)",
                borderRadius: "6px",
                color: "#fff",
                fontSize: "0.85rem",
                fontWeight: 600,
                textDecoration: "none",
                whiteSpace: "nowrap",
                transition: "all 0.15s",
                "&:hover": { background: "rgba(255,255,255,0.25)" },
              }}
            >
              Open →
            </Box>
          </CardContent>
        </Card>
      </Stack>

      {/* Quick action buttons */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 3 }}>
        {[
          { href: "/calendar", label: "Generate Calendar", desc: "Schedule a chemo cycle and export", icon: "◫" },
          { href: "/regimens", label: "Manage Regimens", desc: "View and browse saved regimens", icon: "≡" },
        ].map((item) => (
          <Card
            key={item.href}
            component={Link}
            href={item.href}
            variant="outlined"
            sx={{
              flex: 1,
              textDecoration: "none",
              transition: "all 0.15s",
              "&:hover": {
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                borderColor: "#0f4c81",
                "& .action-icon": { background: "#0f4c81", color: "#fff" },
              },
            }}
          >
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, py: 1.75, px: 2.5, "&:last-child": { pb: 1.75 } }}>
              <Box
                className="action-icon"
                sx={{
                  width: 38,
                  height: 38,
                  borderRadius: "8px",
                  background: "#f1f5f9",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "1.1rem",
                  color: "#475569",
                  transition: "all 0.15s",
                  flexShrink: 0,
                }}
              >
                {item.icon}
              </Box>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b", mb: 0.15 }}>
                  {item.label}
                </Typography>
                <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>
                  {item.desc}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>

      {/* Regimen browser */}
      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          {/* Header */}
          <Box sx={{ px: 2.5, pt: 2.25, pb: 1.5, borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography sx={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>
                Regimen Library
              </Typography>
              <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>
                Click any regimen to open in the calendar generator
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

          {/* List */}
          <Box sx={{ px: 1.5, py: 1.5, maxHeight: 420, overflowY: "auto" }}>
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
            {!isLoading && !error && filtered.length === 0 && (
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
            {!isLoading && !error && filtered.map((n) => (
              <RegimenCard key={n} name={n} />
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
