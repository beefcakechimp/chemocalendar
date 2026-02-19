"use client";

import * as React from "react";
import useSWR from "swr";
import dayjs from "dayjs";
import { useSearchParams } from "next/navigation";
import { listRegimens, getRegimen, previewCalendar, exportCalendarDocx } from "@/lib/api";
import { Regimen, CalendarPreviewResponse } from "@/lib/types";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}

export default function CalendarPage() {
  const params = useSearchParams();
  const preselected = params.get("regimen");

  const { data: names } = useSWR("regimens", listRegimens);

  const [regimenName, setRegimenName] = React.useState<string>(preselected || "");
  const { data: regimen, error: regimenErr } = useSWR<Regimen>(
    regimenName ? ["regimen", regimenName] : null,
    () => getRegimen(regimenName)
  );

  // schedule inputs
  const [startDate, setStartDate] = React.useState<string>(dayjs().format("YYYY-MM-DD"));
  const [cycleLen, setCycleLen] = React.useState<number>(28);
  const [phase, setPhase] = React.useState<"Cycle" | "Induction">("Cycle");
  const [cycleNum, setCycleNum] = React.useState<number>(1);
  const [note, setNote] = React.useState<string>("");

  // title auto-populate (seed from regimen, editable)
  const [title, setTitle] = React.useState<string>("");
  const [titleDirty, setTitleDirty] = React.useState(false);

  React.useEffect(() => {
    if (!regimenName && names && names.length) {
      setRegimenName(preselected && names.includes(preselected) ? preselected : names[0]);
    }
  }, [names, regimenName, preselected]);

  // when regimen changes, reset dirty so it reseeds
  React.useEffect(() => {
    setTitleDirty(false);
  }, [regimenName]);

  // seed title from regimen name unless user edited it
  React.useEffect(() => {
    if (regimen?.name && !titleDirty) setTitle(regimen.name);
  }, [regimen?.name, titleDirty]);

  const [preview, setPreview] = React.useState<CalendarPreviewResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string>("");

  async function runPreview() {
    if (!regimenName) return;
    setErr("");
    setBusy(true);
    try {
      const resp = await previewCalendar({
        regimen_name: regimenName,
        title_override: title.trim() || null,
        start_date: startDate,
        cycle_len: cycleLen,
        phase,
        cycle_num: phase === "Cycle" ? cycleNum : null,
        note: note.trim() || null,
      });
      setPreview(resp);
    } catch (e: any) {
      setErr(e?.message || "Preview failed");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  async function runExport() {
    if (!regimenName) return;
    setErr("");
    setBusy(true);
    try {
      const { blob, filename } = await exportCalendarDocx({
        regimen_name: regimenName,
        title_override: title.trim() || null,
        start_date: startDate,
        cycle_len: cycleLen,
        phase,
        cycle_num: phase === "Cycle" ? cycleNum : null,
        note: note.trim() || null,
      });
      downloadBlob(blob, filename);
    } catch (e: any) {
      setErr(e?.message || "Export failed");
    } finally {
      setBusy(false);
    }
  }

  // auto-preview after regimen load or parameter change
  React.useEffect(() => {
    if (regimenName) runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regimenName]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: "-0.03em" }}>
        Calendar Generator
      </Typography>

      {err && <Alert severity="error">{err}</Alert>}
      {regimenErr && <Alert severity="error">{String((regimenErr as any)?.message || regimenErr)}</Alert>}

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
        <Card variant="outlined" sx={{ flex: 1, minWidth: 320 }}>
          <CardContent>
            <Typography sx={{ fontWeight: 800, mb: 1 }}>Inputs</Typography>

            <FormControl fullWidth size="small">
              <InputLabel>Regimen</InputLabel>
              <Select label="Regimen" value={regimenName} onChange={(e) => setRegimenName(e.target.value)}>
                {(names || []).map((n) => (
                  <MenuItem key={n} value={n}>{n}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <Typography sx={{ opacity: 0.75, fontSize: 13, mt: 1 }}>
              {regimen
                ? `${regimen.on_study ? "On study" : "Off protocol"}${regimen.disease_state ? ` • ${regimen.disease_state}` : ""}`
                : " "}
            </Typography>

            <Divider sx={{ my: 2 }} />

            <TextField
              fullWidth
              size="small"
              label="Document title"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setTitleDirty(true);
              }}
              helperText="Auto-filled from regimen name. Edit if you want a nicer title."
            />

            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField
                fullWidth
                size="small"
                label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                fullWidth
                size="small"
                label="Cycle length"
                type="number"
                value={cycleLen}
                onChange={(e) => setCycleLen(Number(e.target.value))}
                inputProps={{ min: 1 }}
              />
            </Stack>

            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Phase</InputLabel>
                <Select label="Phase" value={phase} onChange={(e) => setPhase(e.target.value as any)}>
                  <MenuItem value="Cycle">Cycle</MenuItem>
                  <MenuItem value="Induction">Induction</MenuItem>
                </Select>
              </FormControl>

              <TextField
                fullWidth
                size="small"
                label="Cycle #"
                type="number"
                value={cycleNum}
                disabled={phase !== "Cycle"}
                onChange={(e) => setCycleNum(Number(e.target.value))}
                inputProps={{ min: 1 }}
              />
            </Stack>

            <TextField
              fullWidth
              size="small"
              sx={{ mt: 1 }}
              label="Optional note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g., Hold venetoclax if ANC < …"
            />

            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button variant="contained" onClick={runPreview} disabled={busy || !regimenName}>
                Preview
              </Button>
              <Button variant="outlined" onClick={runExport} disabled={busy || !regimenName}>
                Export DOCX
              </Button>
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 2 }}>
          <CardContent>
            <Typography sx={{ fontWeight: 800 }}>Preview</Typography>

            {!preview ? (
              <Typography sx={{ opacity: 0.7, mt: 1 }}>No preview yet.</Typography>
            ) : (
              <>
                <Typography sx={{ mt: 1, fontWeight: 900 }}>
                  {preview.regimen_title} — {preview.label}
                </Typography>
                <Typography sx={{ opacity: 0.75 }}>{preview.header}</Typography>
                {note.trim() && (
                  <Typography sx={{ fontStyle: "italic", opacity: 0.85, mt: 0.5 }}>
                    {note.trim()}
                  </Typography>
                )}

                <Divider sx={{ my: 2 }} />
                <CalendarTable grid={preview.grid} />
              </>
            )}
          </CardContent>
        </Card>
      </Stack>
    </Stack>
  );
}

function CalendarTable({ grid }: { grid: CalendarPreviewResponse["grid"] }) {
  const header = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed", fontSize: 13 }}>
        <thead>
          <tr>
            {header.map((h) => (
              <Box
                component="th"
                key={h}
                sx={{
                  border: "1px solid rgba(0,0,0,0.12)",
                  padding: 1,
                  textAlign: "center",
                  background: "#111827",
                  color: "white",
                  fontWeight: 800,
                }}
              >
                {h}
              </Box>
            ))}
          </tr>
        </thead>

        <tbody>
          {grid.map((week, wi) => (
            <tr key={wi}>
              {week.map((cell, ci) => (
                <Box
                  component="td"
                  key={ci}
                  sx={{
                    border: "1px solid rgba(0,0,0,0.12)",
                    verticalAlign: "top",
                    padding: 1,
                    height: 120,
                  }}
                >
                  <Typography sx={{ textAlign: "right", fontWeight: 900 }}>
                    {dayjs(cell.date).format("MMM D")}
                  </Typography>

                  {cell.cycle_day != null && (
                    <>
                      <Typography sx={{ fontStyle: "italic", opacity: 0.8 }}>
                        Day {cell.cycle_day}
                      </Typography>
                      <Stack spacing={0.3} sx={{ mt: 0.5 }}>
                        {(cell.labels || []).map((lab, idx) => (
                          <Typography
                            key={idx}
                            sx={{
                              fontWeight: lab.toLowerCase() === "rest" ? 500 : 800,
                              opacity: lab.toLowerCase() === "rest" ? 0.6 : 1,
                              lineHeight: 1.15,
                            }}
                          >
                            {lab}
                          </Typography>
                        ))}
                      </Stack>
                    </>
                  )}
                </Box>
              ))}
            </tr>
          ))}
        </tbody>
      </Box>
    </Box>
  );
}