"use client";

import * as React from "react";
import useSWR, { mutate } from "swr";
import { listRegimens, getRegimen } from "@/lib/api";
import { Regimen } from "@/lib/types";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  InputAdornment,
  List,
  ListItemButton,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import Link from "next/link";

function TherapyRow({ therapy }: { therapy: Regimen["therapies"][0] }) {
  const routeColor: Record<string, { bg: string; color: string }> = {
    IV: { bg: "#dbeafe", color: "#1d4ed8" },
    PO: { bg: "#d1fae5", color: "#065f46" },
    SQ: { bg: "#fce7f3", color: "#9d174d" },
    IM: { bg: "#ede9fe", color: "#5b21b6" },
    IT: { bg: "#fef3c7", color: "#92400e" },
  };
  const colors = routeColor[therapy.route?.toUpperCase()] ?? { bg: "#f1f5f9", color: "#475569" };

  return (
    <Box
      sx={{
        p: 1.5,
        border: "1px solid #e2e8f0",
        borderRadius: "6px",
        background: "#fafafa",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
        <Typography sx={{ fontWeight: 700, fontSize: "0.875rem", color: "#0f172a", flex: 1 }}>
          {therapy.name}
        </Typography>
        <Chip
          label={therapy.route}
          size="small"
          sx={{
            height: 20,
            fontSize: "0.68rem",
            fontWeight: 700,
            background: colors.bg,
            color: colors.color,
          }}
        />
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0.75 }}>
        {[
          { label: "Dose", value: therapy.dose },
          { label: "Frequency", value: therapy.frequency },
          { label: "Days", value: therapy.duration },
          { label: "Total doses", value: therapy.total_doses != null ? String(therapy.total_doses) : "—" },
        ].map((row) => (
          <Box key={row.label}>
            <Typography sx={{ fontSize: "0.65rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {row.label}
            </Typography>
            <Typography sx={{ fontSize: "0.8rem", color: "#334155", lineHeight: 1.4 }}>
              {row.value}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

export default function RegimensPage() {
  const { data: names, error, isLoading } = useSWR("regimens", listRegimens);
  const [selected, setSelected] = React.useState<string>("");
  const [q, setQ] = React.useState("");

  React.useEffect(() => {
    if (!selected && names && names.length) setSelected(names[0]);
  }, [names, selected]);

  const { data: regimen, isLoading: regLoading } = useSWR<Regimen>(
    selected ? ["regimen", selected] : null,
    () => getRegimen(selected)
  );

  const filtered = React.useMemo(() => {
    const xs = names || [];
    const qq = q.trim().toLowerCase();
    if (!qq) return xs;
    return xs.filter((n) => n.toLowerCase().includes(qq));
  }, [names, q]);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>
          Regimen Library
        </Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>
          Browse saved chemotherapy regimens and their treatment schedules
        </Typography>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
        {/* Regimen list */}
        <Card variant="outlined" sx={{ width: { xs: "100%", md: 280 }, flexShrink: 0 }}>
          <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
            <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search regimens…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Box component="span" sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>⌕</Box>
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            {isLoading && (
              <Box sx={{ px: 1.5, pb: 1.5 }}>
                {[...Array(6)].map((_, i) => (
                  <Skeleton key={i} height={44} sx={{ mb: 0.25, borderRadius: "5px" }} />
                ))}
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ m: 1.5 }}>
                {String((error as any)?.message || error)}
              </Alert>
            )}

            <Box sx={{ maxHeight: 520, overflowY: "auto" }}>
              <List disablePadding dense sx={{ px: 1, pb: 1 }}>
                {filtered.map((n) => (
                  <ListItemButton
                    key={n}
                    selected={selected === n}
                    onClick={() => setSelected(n)}
                    sx={{
                      borderRadius: "5px",
                      mb: 0.25,
                      px: 1.5,
                      py: 0.875,
                      "&.Mui-selected": {
                        background: "#eff6ff",
                        "&:hover": { background: "#eff6ff" },
                        "& .regimen-name": { color: "#0f4c81", fontWeight: 700 },
                      },
                      "&:hover": { background: "#f8fafc" },
                    }}
                  >
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography className="regimen-name" sx={{ fontSize: "0.875rem", fontWeight: 500, color: "#1e293b" }} noWrap>
                        {n}
                      </Typography>
                    </Box>
                    {selected === n && (
                      <Box component="span" sx={{ color: "#0f4c81", fontSize: "0.75rem", ml: 0.5 }}>→</Box>
                    )}
                  </ListItemButton>
                ))}
                {!isLoading && !error && filtered.length === 0 && (
                  <Box sx={{ textAlign: "center", py: 3 }}>
                    <Typography sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>No regimens found</Typography>
                  </Box>
                )}
              </List>
            </Box>

            {/* Count footer */}
            <Box sx={{ px: 2, py: 1, borderTop: "1px solid #e2e8f0" }}>
              <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                {names?.length ?? 0} regimen{(names?.length ?? 0) !== 1 ? "s" : ""} total
                {q && `, ${filtered.length} shown`}
              </Typography>
            </Box>
          </CardContent>
        </Card>

        {/* Detail panel */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {!selected && !isLoading && (
            <Card variant="outlined">
              <CardContent sx={{ py: 6, textAlign: "center" }}>
                <Typography sx={{ color: "#94a3b8" }}>Select a regimen to view details</Typography>
              </CardContent>
            </Card>
          )}

          {selected && (
            <Card variant="outlined">
              <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                {/* Header */}
                <Box sx={{ px: 2.5, py: 2, borderBottom: "1px solid #e2e8f0" }}>
                  {regLoading ? (
                    <>
                      <Skeleton width={200} height={28} />
                      <Skeleton width={120} height={20} sx={{ mt: 0.5 }} />
                    </>
                  ) : regimen ? (
                    <>
                      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2, mb: 0.75 }}>
                        <Typography sx={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>
                          {regimen.name}
                        </Typography>
                        <Box
                          component={Link}
                          href={`/calendar?regimen=${encodeURIComponent(regimen.name)}`}
                          sx={{
                            px: 1.5,
                            py: 0.625,
                            background: "#0f4c81",
                            color: "#fff",
                            borderRadius: "5px",
                            fontSize: "0.78rem",
                            fontWeight: 600,
                            textDecoration: "none",
                            whiteSpace: "nowrap",
                            flexShrink: 0,
                            transition: "background 0.15s",
                            "&:hover": { background: "#0a3460" },
                          }}
                        >
                          Generate calendar →
                        </Box>
                      </Box>
                      <Stack direction="row" spacing={0.75} flexWrap="wrap">
                        <Chip
                          label={regimen.on_study ? "On Study" : "Off Protocol"}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: "0.68rem",
                            fontWeight: 600,
                            background: regimen.on_study ? "#dbeafe" : "#f0fdf4",
                            color: regimen.on_study ? "#1d4ed8" : "#15803d",
                          }}
                        />
                        {regimen.disease_state && (
                          <Chip
                            label={regimen.disease_state}
                            size="small"
                            sx={{ height: 20, fontSize: "0.68rem", background: "#f1f5f9", color: "#475569" }}
                          />
                        )}
                        <Chip
                          label={`${regimen.therapies?.length ?? 0} agent${(regimen.therapies?.length ?? 0) !== 1 ? "s" : ""}`}
                          size="small"
                          sx={{ height: 20, fontSize: "0.68rem", background: "#f1f5f9", color: "#475569" }}
                        />
                      </Stack>
                    </>
                  ) : null}
                </Box>

                {regimen && (
                  <Box sx={{ p: 2.5 }}>
                    {/* Notes */}
                    {regimen.notes && (
                      <>
                        <Typography sx={{ fontSize: "0.72rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", mb: 0.75 }}>
                          Clinical Notes
                        </Typography>
                        <Box
                          sx={{
                            p: 1.5,
                            background: "#fffbeb",
                            border: "1px solid #fde68a",
                            borderRadius: "6px",
                            mb: 2,
                          }}
                        >
                          <Typography sx={{ fontSize: "0.85rem", color: "#92400e", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
                            {regimen.notes}
                          </Typography>
                        </Box>
                      </>
                    )}

                    {/* Therapies */}
                    <Typography sx={{ fontSize: "0.72rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", mb: 1 }}>
                      Therapies ({regimen.therapies?.length ?? 0})
                    </Typography>

                    {!regimen.therapies?.length ? (
                      <Typography sx={{ fontSize: "0.875rem", color: "#94a3b8", fontStyle: "italic" }}>
                        No therapies defined for this regimen.
                      </Typography>
                    ) : (
                      <Stack spacing={1}>
                        {regimen.therapies.map((t, i) => (
                          <TherapyRow key={`${t.name}-${i}`} therapy={t} />
                        ))}
                      </Stack>
                    )}
                  </Box>
                )}
              </CardContent>
            </Card>
          )}
        </Box>
      </Stack>
    </Box>
  );
}
