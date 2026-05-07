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
  return (
    <Typography sx={{ fontSize: "0.68rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", mb: 1, mt: 2, "&:first-of-type": { mt: 0 } }}>
      {children}
    </Typography>
  );
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8", mt: 0.5, lineHeight: 1.4 }}>{children}</Typography>;
}

function CalendarPageInner() {
  const params = useSearchParams();
  const preselected = params.get("regimen");

  const { data: names, isLoading: namesLoading } = useSWR("regimens", listRegimens);
  const [regimenName, setRegimenName] = React.useState<string>(preselected || "");
  const { data: regimen } = useSWR<Regimen>(regimenName ? ["regimen", regimenName] : null, () => getRegimen(regimenName));

  const [startDate, setStartDate] = React.useState<string>(dayjs().format("YYYY-MM-DD"));
  const [cycleLen, setCycleLen] = React.useState<number>(28);
  const [phase, setPhase] = React.useState<"Cycle" | "Induction">("Cycle");
  const [cycleNum, setCycleNum] = React.useState<number>(1);
  const [note, setNote] = React.useState<string>("");
  const [title, setTitle] = React.useState<string>("");
  const [titleDirty, setTitleDirty] = React.useState(false);
  
  const [customTherapies, setCustomTherapies] = React.useState<Chemo[]>([]);

  React.useEffect(() => {
    if (!regimenName && names && names.length) {
      setRegimenName(preselected && names.includes(preselected) ? preselected : names[0]);
    }
  }, [names, regimenName, preselected]);

  React.useEffect(() => { setTitleDirty(false); }, [regimenName]);
  React.useEffect(() => {
    if (regimen?.name && !titleDirty) setTitle(regimen.name);
  }, [regimen?.name, titleDirty]);

  // FIX: Tie the therapy building to regimenName so SWR background refresh doesn't wipe out your selected radio buttons
  React.useEffect(() => {
    if (regimen?.therapies) {
      setCustomTherapies(regimen.therapies.map(t => {
        const firstOpt = t.options && t.options.length > 0 ? t.options[0] : { dose: t.dose, duration: t.duration, total_doses: t.total_doses };
        return { ...t, dose: firstOpt.dose, duration: firstOpt.duration, total_doses: firstOpt.total_doses };
      }));
    } else {
      setCustomTherapies([]);
    }
  }, [regimenName, regimen?.therapies]);

  const [preview, setPreview] = React.useState<CalendarPreviewResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [exportBusy, setExportBusy] = React.useState(false);
  const [err, setErr] = React.useState<string>("");

  const buildRequest = () => ({
    regimen_name: regimenName,
    title_override: title.trim() || null,
    start_date: startDate,
    cycle_len: cycleLen,
    phase,
    cycle_num: phase === "Cycle" ? cycleNum : null,
    note: note.trim() || null,
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
    setErr(""); setExportBusy(true);
    try {
      const { blob, filename } = await exportCalendarDocx(buildRequest());
      downloadBlob(blob, filename);
    } catch (e: any) { setErr(e?.message || "Export failed"); } 
    finally { setExportBusy(false); }
  }

  React.useEffect(() => {
    if (regimenName) runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regimenName]);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>Calendar Generator</Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>Configure a treatment cycle and preview or export the calendar</Typography>
      </Box>

      {err && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>{err}</Alert>}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Box sx={{ width: { xs: "100%", lg: 320 }, flexShrink: 0 }}>
          <Card variant="outlined">
            <CardContent>
              <SectionLabel>1. Regimen</SectionLabel>
              <FormControl fullWidth size="small">
                <InputLabel>Select regimen</InputLabel>
                <Select label="Select regimen" value={regimenName} onChange={(e) => setRegimenName(e.target.value)} disabled={namesLoading}>
                  {(names || []).map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
                </Select>
              </FormControl>

              {regimen && (
                <Box sx={{ mt: 1.5, p: 1.25, background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                  <Stack direction="row" spacing={0.75} flexWrap="wrap">
                    <Chip label={regimen.on_study ? "On Study" : "Off Protocol"} size="small" sx={{ height: 20, fontSize: "0.68rem", fontWeight: 600, background: regimen.on_study ? "#dbeafe" : "#f0fdf4", color: regimen.on_study ? "#1d4ed8" : "#15803d" }} />
                    {regimen.disease_state && <Chip label={regimen.disease_state} size="small" sx={{ height: 20, fontSize: "0.68rem", background: "#e2e8f0", color: "#475569" }} />}
                  </Stack>
                </Box>
              )}

              <SectionLabel>2. Customize Dose & Days</SectionLabel>
              {customTherapies.map((t, idx) => (
                <Box key={idx} sx={{ mb: 1.5, p: 1.5, background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                  <Typography sx={{ fontWeight: 600, fontSize: "0.85rem", color: "#0f172a", mb: 0.5 }}>
                    {t.name} <Typography component="span" sx={{ fontSize: '0.75rem', color: '#64748b' }}>({t.route})</Typography>
                  </Typography>

                  {t.options && t.options.length > 1 ? (
                    <RadioGroup 
                      name={`therapy-${idx}`} // FIX: Name parameter so browser groups them correctly
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
              <TextField fullWidth size="small" label="Document title" value={title} onChange={(e) => { setTitle(e.target.value); setTitleDirty(true); }} sx={{ mb: 1.25 }} />

              <Stack direction="row" spacing={1} sx={{ mb: 1.25 }}>
                <TextField fullWidth size="small" label="Start date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} InputLabelProps={{ shrink: true }} />
                <Tooltip title="Total days in one treatment cycle" placement="top">
                  <TextField fullWidth size="small" label="Cycle length" type="number" value={cycleLen} onChange={(e) => setCycleLen(Math.max(1, Number(e.target.value)))} inputProps={{ min: 1 }} />
                </Tooltip>
              </Stack>

              <Stack direction="row" spacing={1}>
                <FormControl fullWidth size="small">
                  <InputLabel>Phase</InputLabel>
                  <Select label="Phase" value={phase} onChange={(e) => setPhase(e.target.value as any)}>
                    <MenuItem value="Cycle">Cycle</MenuItem>
                    <MenuItem value="Induction">Induction</MenuItem>
                  </Select>
                </FormControl>
                <TextField fullWidth size="small" label="Cycle #" type="number" value={cycleNum} disabled={phase !== "Cycle"} onChange={(e) => setCycleNum(Math.max(1, Number(e.target.value)))} inputProps={{ min: 1 }} />
              </Stack>

              <Divider sx={{ my: 2 }} />
              <SectionLabel>Optional Note</SectionLabel>
              <TextField fullWidth size="small" multiline rows={2} placeholder="e.g., Hold venetoclax if ANC < 500…" value={note} onChange={(e) => setNote(e.target.value)} />
              <FieldHint>Displayed on the calendar beneath the title</FieldHint>

              <Divider sx={{ my: 2 }} />
              <Stack spacing={1}>
                <Button variant="contained" fullWidth onClick={runPreview} disabled={busy || !regimenName} startIcon={busy ? <CircularProgress size={14} color="inherit" /> : null} sx={{ py: 1 }}>
                  {busy ? "Generating…" : "Generate Preview"}
                </Button>
                <Button variant="outlined" fullWidth onClick={runExport} disabled={exportBusy || !regimenName} startIcon={exportBusy ? <CircularProgress size={14} /> : null} sx={{ py: 1 }}>
                  {exportBusy ? "Exporting…" : "Export DOCX"}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Card variant="outlined" sx={{ minHeight: 480 }}>
            <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                <Box>
                  {preview ? (
                    <>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.25 }}>
                        <Typography sx={{ fontWeight: 700, fontSize: "1rem", color: "#0f172a" }}>{preview.regimen_title}</Typography>
                        <Chip label={preview.label} size="small" sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700, background: "#0f4c81", color: "#fff" }} />
                      </Box>
                      <Typography sx={{ fontSize: "0.8rem", color: "#64748b" }}>{preview.header}</Typography>
                      {note.trim() && <Typography sx={{ fontSize: "0.78rem", color: "#b45309", fontStyle: "italic", mt: 0.25 }}>{note.trim()}</Typography>}
                    </>
                  ) : <Typography sx={{ fontWeight: 600, color: "#1e293b" }}>Preview</Typography>}
                </Box>
                {preview && <Button size="small" variant="outlined" onClick={runExport} disabled={exportBusy} sx={{ whiteSpace: "nowrap", flexShrink: 0 }}>Export DOCX</Button>}
              </Box>

              <Box sx={{ p: 2, overflowX: "auto" }}>
                {!preview && !busy && (
                  <Box sx={{ textAlign: "center", py: 8 }}>
                    <Box sx={{ fontSize: "2.5rem", mb: 1.5, opacity: 0.2 }}>◫</Box>
                    <Typography sx={{ color: "#94a3b8", fontSize: "0.9rem" }}>{regimenName ? "Click 'Generate Preview' to see the calendar" : "Select a regimen to begin"}</Typography>
                  </Box>
                )}
                {busy && (
                  <Box sx={{ textAlign: "center", py: 8 }}>
                    <CircularProgress size={32} sx={{ color: "#0f4c81" }} />
                    <Typography sx={{ color: "#94a3b8", fontSize: "0.875rem", mt: 1.5 }}>Generating calendar…</Typography>
                  </Box>
                )}
                {preview && !busy && <CalendarGrid grid={preview.grid} />}
              </Box>

              {preview && (
                <Box sx={{ px: 2.5, pb: 2, pt: 0 }}>
                  <Divider sx={{ mb: 1.5 }} />
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
                    <LegendItem color="#eff6ff" border="#bfdbfe" text="Treatment day" />
                    <LegendItem color="#f0fdf4" border="#bbf7d0" text="Rest day" />
                    <LegendItem color="#f8fafc" border="#e2e8f0" text="Outside cycle" />
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>
      </Stack>
    </Box>
  );
}

function LegendItem({ color, border, text }: { color: string; border: string; text: string }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
      <Box sx={{ width: 14, height: 14, borderRadius: "3px", background: color, border: `1px solid ${border}` }} />
      <Typography sx={{ fontSize: "0.72rem", color: "#64748b" }}>{text}</Typography>
    </Box>
  );
}

function CalendarGrid({ grid }: { grid: CalendarPreviewResponse["grid"] }) {
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box component="table" sx={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, tableLayout: "fixed", fontSize: 13, border: "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden" }}>
        <thead>
          <tr>
            {DAYS.map((d) => (
              <Box component="th" key={d} sx={{ py: 1, px: 0.75, textAlign: "center", background: "#0f4c81", color: "white", fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.04em", borderRight: "1px solid rgba(255,255,255,0.1)", "&:last-child": { borderRight: "none" } }}>{d}</Box>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.map((week, wi) => (
            <tr key={wi}>
              {week.map((cell, ci) => {
                const isActive = cell.cycle_day != null;
                const hasLabels = cell.labels && cell.labels.length > 0;
                const isRest = hasLabels && cell.labels.every((l) => l.toLowerCase() === "rest");
                const isTreatment = isActive && hasLabels && !isRest;
                const isLast = wi === grid.length - 1;
                return (
                  <Box component="td" key={ci} sx={{ verticalAlign: "top", minWidth: 80, height: 100, p: 0.75, background: isTreatment ? "#eff6ff" : isRest ? "#f0fdf4" : isActive ? "#fafafa" : "#fff", borderRight: ci < 6 ? "1px solid #e2e8f0" : "none", borderBottom: !isLast ? "1px solid #e2e8f0" : "none", transition: "background 0.1s" }}>
                    <Typography sx={{ textAlign: "right", fontWeight: 700, fontSize: "0.8rem", color: isActive ? "#0f172a" : "#cbd5e1", lineHeight: 1, mb: 0.5 }}>{dayjs(cell.date).format("MMM D")}</Typography>
                    {isActive && (
                      <>
                        <Typography sx={{ fontSize: "0.68rem", color: "#94a3b8", fontStyle: "italic", lineHeight: 1, mb: 0.5 }}>Day {cell.cycle_day}</Typography>
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.3 }}>
                          {(cell.labels || []).map((lab, idx) => {
                            const rest = lab.toLowerCase() === "rest";
                            return (
                              <Box key={idx} sx={{ px: 0.5, py: 0.2, borderRadius: "3px", background: rest ? "#dcfce7" : "#dbeafe", display: "inline-flex" }}>
                                <Typography sx={{ fontSize: "0.68rem", fontWeight: rest ? 500 : 700, color: rest ? "#15803d" : "#1d4ed8", lineHeight: 1.3 }}>{lab}</Typography>
                              </Box>
                            );
                          })}
                        </Box>
                      </>
                    )}
                  </Box>
                );
              })}
            </tr>
          ))}
        </tbody>
      </Box>
    </Box>
  );
}

export default function CalendarPage() {
  return (
    <React.Suspense fallback={<Box sx={{ p: 4, textAlign: "center" }}><CircularProgress /></Box>}>
      <CalendarPageInner />
    </React.Suspense>
  );
}