"use client";

import * as React from "react";
import useSWR from "swr";
import dayjs from "dayjs";
import { useSearchParams } from "next/navigation";
import { listRegimens, getRegimen, previewCalendar, exportCalendarDocx } from "@/lib/api";
import { Regimen, CalendarPreviewResponse, Chemo } from "@/lib/types";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, FormControl,
  InputLabel, MenuItem, Select, Stack, TextField, Tooltip, Typography, RadioGroup, FormControlLabel, Radio
} from "@mui/material";

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); window.URL.revokeObjectURL(url);
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <Typography sx={{ fontSize: "0.68rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", mb: 1, mt: 2.5, "&:first-of-type": { mt: 0 } }}>{children}</Typography>;
}

// 1. Rename the main function to CalendarContent (no longer the default export)
function CalendarContent() {
  const params = useSearchParams();
  const preselected = params.get("regimen");

  const { data: names, isLoading: namesLoading } = useSWR("regimens", listRegimens);
  const [regimenName, setRegimenName] = React.useState<string>(preselected || "");
  const { data: regimen } = useSWR<Regimen>(regimenName ? ["regimen", regimenName] : null, () => getRegimen(regimenName));

  const [startDate, setStartDate] = React.useState<string>(dayjs().format("YYYY-MM-DD"));
  const [cycleLen, setCycleLen] = React.useState<number>(28);
  const [phase, setPhase] = React.useState<"Cycle" | "Induction">("Cycle");
  const [cycleNum, setCycleNum] = React.useState<number>(1);
  
  // State for radio buttons
  const [customTherapies, setCustomTherapies] = React.useState<Chemo[]>([]);

  React.useEffect(() => {
    if (!regimenName && names && names.length) {
      setRegimenName(preselected && names.includes(preselected) ? preselected : names[0]);
    }
  }, [names, regimenName, preselected]);

  // Load options into local state for radio button selection
  React.useEffect(() => {
    if (regimen?.therapies) {
      setCustomTherapies(regimen.therapies.map(t => {
        const firstOpt = t.options && t.options.length > 0 ? t.options[0] : { dose: t.dose, duration: t.duration, total_doses: t.total_doses };
        return { ...t, dose: firstOpt.dose, duration: firstOpt.duration, total_doses: firstOpt.total_doses };
      }));
    } else {
      setCustomTherapies([]);
    }
  }, [regimen]);

  const [preview, setPreview] = React.useState<CalendarPreviewResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string>("");

  const buildRequest = () => ({
    regimen_name: regimenName,
    start_date: startDate,
    cycle_len: cycleLen,
    phase,
    cycle_num: phase === "Cycle" ? cycleNum : null,
    therapies_override: customTherapies, 
  });

  async function runPreview() {
    if (!regimenName) return;
    setErr(""); setBusy(true);
    try { setPreview(await previewCalendar(buildRequest())); } 
    catch (e: any) { setErr(e?.message || "Preview failed"); setPreview(null); } 
    finally { setBusy(false); }
  }

  async function runExport() {
    if (!regimenName) return;
    try {
      const { blob, filename } = await exportCalendarDocx(buildRequest());
      downloadBlob(blob, filename);
    } catch (e: any) { setErr(e?.message || "Export failed"); }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 3 }}>Calendar Generator</Typography>
      {err && <Alert severity="error" sx={{ mb: 2 }}>{err}</Alert>}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Box sx={{ width: { xs: "100%", lg: 320 }, flexShrink: 0 }}>
          <Card variant="outlined">
            <CardContent>
              <SectionLabel>1. Regimen</SectionLabel>
              <FormControl fullWidth size="small">
                <InputLabel>Select regimen</InputLabel>
                <Select label="Select regimen" value={regimenName} onChange={(e) => setRegimenName(e.target.value)}>
                  {(names || []).map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
                </Select>
              </FormControl>

              <SectionLabel>2. Customize Dose & Days</SectionLabel>
              {customTherapies.map((t, idx) => (
                <Box key={idx} sx={{ mb: 1.5, p: 1.5, background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                  <Typography sx={{ fontWeight: 600, fontSize: "0.85rem", color: "#0f172a", mb: 0.5 }}>
                    {t.name} <Typography component="span" sx={{ fontSize: '0.75rem', color: '#64748b' }}>({t.route})</Typography>
                  </Typography>

                  {t.options && t.options.length > 1 ? (
                    <RadioGroup 
                      value={`${t.dose}|${t.duration}`} 
                      onChange={(e) => {
                        const [selDose, selDur] = e.target.value.split('|');
                        const selOpt = t.options!.find(o => o.dose === selDose && o.duration === selDur);
                        const updated = [...customTherapies];
                        updated[idx] = { ...updated[idx], dose: selDose, duration: selDur, total_doses: selOpt?.total_doses || null };
                        setCustomTherapies(updated);
                      }}
                    >
                      {t.options.map((opt, i) => (
                        <FormControlLabel key={i} value={`${opt.dose}|${opt.duration}`} control={<Radio size="small" sx={{ py: 0.5 }} />} label={<Typography sx={{fontSize: "0.85rem"}}>{opt.dose} for {opt.duration}</Typography>} />
                      ))}
                    </RadioGroup>
                  ) : (
                    <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                      <TextField fullWidth size="small" label="Dose" value={t.dose} onChange={(e) => { const updated = [...customTherapies]; updated[idx].dose = e.target.value; setCustomTherapies(updated); }} />
                      <TextField fullWidth size="small" label="Days" value={t.duration} onChange={(e) => { const updated = [...customTherapies]; updated[idx].duration = e.target.value; updated[idx].total_doses = null; setCustomTherapies(updated); }} />
                    </Stack>
                  )}
                </Box>
              ))}

              <SectionLabel>3. Schedule</SectionLabel>
              <Stack direction="row" spacing={1} sx={{ mb: 1.25 }}>
                <TextField fullWidth size="small" label="Start date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField fullWidth size="small" label="Cycle length" type="number" value={cycleLen} onChange={(e) => setCycleLen(Math.max(1, Number(e.target.value)))} />
              </Stack>

              <Divider sx={{ my: 2 }} />
              <Stack spacing={1}>
                <Button variant="contained" fullWidth onClick={runPreview} disabled={busy || !regimenName}>{busy ? "Generating…" : "Generate Preview"}</Button>
                <Button variant="outlined" fullWidth onClick={runExport} disabled={!preview}>Export DOCX</Button>
              </Stack>
            </CardContent>
          </Card>
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Card variant="outlined" sx={{ minHeight: 480 }}>
            <CardContent>
              {preview ? (
                <Box>
                  <Typography sx={{ fontWeight: 700, fontSize: "1.2rem", mb: 2 }}>{preview.regimen_title}</Typography>
                  <Box sx={{ overflowX: "auto" }}>
                    <Box component="table" sx={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, fontSize: 13, border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                      <thead>
                        <tr>{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(d => <Box component="th" key={d} sx={{ py: 1, background: "#0f4c81", color: "white" }}>{d}</Box>)}</tr>
                      </thead>
                      <tbody>
                        {preview.grid.map((week, wi) => (
                          <tr key={wi}>
                            {week.map((cell, ci) => (
                              <Box component="td" key={ci} sx={{ verticalAlign: "top", height: 80, p: 1, borderRight: "1px solid #e2e8f0", borderBottom: "1px solid #e2e8f0", background: cell.cycle_day ? "#fff" : "#fafafa" }}>
                                <Typography sx={{ textAlign: "right", fontWeight: 700, fontSize: "0.8rem", color: cell.cycle_day ? "#0f172a" : "#cbd5e1" }}>{dayjs(cell.date).format("MMM D")}</Typography>
                                {cell.cycle_day && <Typography sx={{ fontSize: "0.68rem", color: "#94a3b8" }}>Day {cell.cycle_day}</Typography>}
                                {(cell.labels || []).map((lab, idx) => <Box key={idx} sx={{ px: 0.5, py: 0.2, mt: 0.5, borderRadius: "3px", background: lab === "Rest" ? "#dcfce7" : "#dbeafe" }}><Typography sx={{ fontSize: "0.68rem", color: lab === "Rest" ? "#15803d" : "#1d4ed8" }}>{lab}</Typography></Box>)}
                              </Box>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </Box>
                  </Box>
                </Box>
              ) : (
                <Box sx={{ textAlign: "center", py: 8 }}>
                  <Typography sx={{ color: "#94a3b8" }}>Click 'Generate Preview' to see the calendar</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>
      </Stack>
    </Box>
  );
}

// 2. Create a new default export that wraps CalendarContent in a Suspense boundary
export default function CalendarPage() {
  return (
    <React.Suspense fallback={<Box sx={{ p: 4, textAlign: 'center', color: '#64748b' }}>Loading calendar generator...</Box>}>
      <CalendarContent />
    </React.Suspense>
  );
}