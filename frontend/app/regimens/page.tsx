"use client";

import * as React from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { listRegimens, getRegimen, upsertRegimen, deleteRegimen } from "@/lib/api";
import { Regimen, Chemo, TherapyOption } from "@/lib/types";
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, Divider, FormControl, InputAdornment, InputLabel, List, ListItemButton,
  MenuItem, Select, Skeleton, Stack, Switch, TextField, Typography,
} from "@mui/material";
import Link from "next/link";

const ROUTES = ["IV", "PO", "SQ", "IM", "IT"];

const ROUTE_COLORS: Record<string, { bg: string; color: string }> = {
  IV: { bg: "#dbeafe", color: "#1d4ed8" },
  PO: { bg: "#d1fae5", color: "#065f46" },
  SQ: { bg: "#fce7f3", color: "#9d174d" },
  IM: { bg: "#ede9fe", color: "#5b21b6" },
  IT: { bg: "#fef3c7", color: "#92400e" },
};

const EMPTY_THERAPY: Chemo = {
  name: "", 
  route: "IV", 
  frequency: "", 
  options: [{ dose: "", duration: "", total_doses: null }],
  dose: "", 
  duration: "", 
  total_doses: null
};

const EMPTY_REGIMEN: Regimen = {
  name: "", disease_state: "", on_study: false, notes: "", therapies: [],
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <Typography sx={{
      fontSize: "0.68rem", fontWeight: 700, color: "#94a3b8",
      textTransform: "uppercase", letterSpacing: "0.08em",
      mb: 1, mt: 2.5, "&:first-of-type": { mt: 0 },
    }}>
      {children}
    </Typography>
  );
}

function TherapyDialog({ open, initial, onSave, onClose }: {
  open: boolean; initial: Chemo;
  onSave: (t: Chemo) => void; onClose: () => void;
}) {
  const [t, setT] = React.useState<Chemo>(initial);
  const [options, setOptions] = React.useState<TherapyOption[]>([]);

  React.useEffect(() => { 
    setT(initial); 
    // Fallback for older flat data that might not have the options array yet
    if (initial.options && initial.options.length > 0) {
      setOptions(initial.options);
    } else {
      setOptions([{ dose: initial.dose || "", duration: initial.duration || "", total_doses: initial.total_doses || null }]);
    }
  }, [initial, open]);

  const updateOpt = (i: number, field: keyof TherapyOption, val: any) => {
    const newOpts = [...options];
    newOpts[i] = { ...newOpts[i], [field]: val };
    setOptions(newOpts);
  };

  const addOption = () => setOptions([...options, { dose: "", duration: "", total_doses: null }]);
  const remOption = (i: number) => setOptions(options.filter((_, idx) => idx !== i));

  const valid = t.name.trim() && t.frequency.trim() && options.every(o => o.dose.trim() && o.duration.trim());

  const handleSave = () => {
    // Save the flat fields as the first option just as a fallback
    const firstOpt = options[0];
    onSave({ 
      ...t, 
      options,
      dose: firstOpt.dose,
      duration: firstOpt.duration,
      total_doses: firstOpt.total_doses
    });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>{initial.name ? `Edit: ${initial.name}` : "Add Agent"}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <Stack direction="row" spacing={1.5}>
            <TextField label="Agent name *" size="small" fullWidth value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} placeholder="e.g., Venetoclax" />
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Route *</InputLabel>
              <Select label="Route *" value={t.route} onChange={(e) => setT({ ...t, route: e.target.value })}>
                {ROUTES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
          <TextField label="Frequency *" size="small" fullWidth value={t.frequency} onChange={(e) => setT({ ...t, frequency: e.target.value })} placeholder="e.g., once daily" />

          <Box sx={{ mt: 2, p: 2, background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
            <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", color: "#1e293b", mb: 0.5 }}>Dosage Variants *</Typography>
            <Typography sx={{ fontSize: "0.72rem", color: "#64748b", mb: 1.5 }}>Add multiple alternative doses if you want the user to choose from a list.</Typography>
            
            <Stack spacing={1.5}>
              {options.map((opt, i) => (
                <Stack direction="row" spacing={1} key={i} alignItems="center">
                  <TextField size="small" label="Dose" value={opt.dose} onChange={(e) => updateOpt(i, "dose", e.target.value)} placeholder="e.g., 100 mg" sx={{ flex: 1 }} />
                  <TextField size="small" label="Days" value={opt.duration} onChange={(e) => updateOpt(i, "duration", e.target.value)} placeholder="e.g., Days 1-7" sx={{ flex: 1 }} />
                  {options.length > 1 && <Button color="error" variant="outlined" onClick={() => remOption(i)} sx={{ minWidth: 0, px: 1.5 }}>✕</Button>}
                </Stack>
              ))}
              <Button size="small" variant="outlined" onClick={addOption} sx={{ alignSelf: "flex-start", mt: 1 }}>+ Add alternative dose</Button>
            </Stack>
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button variant="contained" disabled={!valid} onClick={handleSave}>Save Agent</Button>
      </DialogActions>
    </Dialog>
  );
}

function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onClose }: {
  open: boolean; title: string; message: string;
  confirmLabel?: string; onConfirm: () => void; onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>{title}</DialogTitle>
      <DialogContent><Typography sx={{ fontSize: "0.9rem", color: "#475569" }}>{message}</Typography></DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button variant="contained" color="error" onClick={() => { onConfirm(); onClose(); }}>{confirmLabel}</Button>
      </DialogActions>
    </Dialog>
  );
}

function RegimenEditor({ initial, onSaved, onDeleted, isNew }: {
  initial: Regimen; onSaved: (name: string) => void;
  onDeleted: () => void; isNew: boolean;
}) {
  const [reg, setReg] = React.useState<Regimen>(initial);
  const [saving, setSaving] = React.useState(false);
  const [err, setErr] = React.useState("");
  const [success, setSuccess] = React.useState("");
  const [dirty, setDirty] = React.useState(false);

  const [therapyDialog, setTherapyDialog] = React.useState<{ open: boolean; index: number | null; initial: Chemo }>({ open: false, index: null, initial: EMPTY_THERAPY });
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [confirmTherapyDel, setConfirmTherapyDel] = React.useState<number | null>(null);

  React.useEffect(() => { setReg(initial); setDirty(false); setErr(""); setSuccess(""); }, [initial]);

  function update<K extends keyof Regimen>(key: K, value: Regimen[K]) {
    setReg((p) => ({ ...p, [key]: value }));
    setDirty(true);
  }

  async function handleSave() {
    if (!reg.name.trim()) { setErr("Regimen name is required."); return; }
    setSaving(true); setErr(""); setSuccess("");
    try {
      await upsertRegimen({ ...reg, name: reg.name.trim() });
      await globalMutate("regimens");
      setSuccess("Saved successfully.");
      setDirty(false);
      onSaved(reg.name.trim());
    } catch (e: any) { setErr(e?.message || "Save failed."); }
    finally { setSaving(false); }
  }

  async function handleDelete() {
    try {
      await deleteRegimen(initial.name);
      await globalMutate("regimens");
      onDeleted();
    } catch (e: any) { setErr(e?.message || "Delete failed."); }
  }

  function handleTherapySave(t: Chemo) {
    setReg((p) => {
      const therapies = [...p.therapies];
      if (therapyDialog.index === null) therapies.push(t);
      else therapies[therapyDialog.index] = t;
      return { ...p, therapies };
    });
    setDirty(true);
  }

  function moveTherapy(i: number, dir: -1 | 1) {
    setReg((p) => {
      const therapies = [...p.therapies];
      const j = i + dir;
      if (j < 0 || j >= therapies.length) return p;
      [therapies[i], therapies[j]] = [therapies[j], therapies[i]];
      return { ...p, therapies };
    });
    setDirty(true);
  }

  return (
    <>
      <TherapyDialog open={therapyDialog.open} initial={therapyDialog.initial} onSave={handleTherapySave} onClose={() => setTherapyDialog((s) => ({ ...s, open: false }))} />
      <ConfirmDialog open={confirmDelete} title="Delete regimen?" message={`"${initial.name}" and all its agents will be permanently deleted.`} onConfirm={handleDelete} onClose={() => setConfirmDelete(false)} />
      <ConfirmDialog open={confirmTherapyDel !== null} title="Remove agent?" message={`Remove "${confirmTherapyDel !== null ? reg.therapies[confirmTherapyDel]?.name : ""}" from this regimen?`} confirmLabel="Remove" onConfirm={() => { if (confirmTherapyDel !== null) { setReg((p) => ({ ...p, therapies: p.therapies.filter((_, i) => i !== confirmTherapyDel) })); setDirty(true); } }} onClose={() => setConfirmTherapyDel(null)} />

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Box sx={{ px: 2.5, py: 2, borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: "1rem", color: "#0f172a" }}>{isNew ? "New Regimen" : reg.name || "Edit Regimen"}</Typography>
              {dirty && <Typography sx={{ fontSize: "0.72rem", color: "#b45309", mt: 0.25 }}>● Unsaved changes</Typography>}
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {!isNew && <Button size="small" color="error" variant="outlined" onClick={() => setConfirmDelete(true)} sx={{ fontSize: "0.78rem" }}>Delete</Button>}
              {!isNew && <Button size="small" variant="outlined" component={Link} href={`/calendar?regimen=${encodeURIComponent(initial.name)}`} sx={{ fontSize: "0.78rem", whiteSpace: "nowrap" }}>Open in calendar →</Button>}
              <Button size="small" variant="contained" onClick={handleSave} disabled={saving || !dirty} sx={{ fontSize: "0.78rem" }}>{saving ? "Saving…" : "Save"}</Button>
            </Stack>
          </Box>

          <Box sx={{ p: 2.5 }}>
            {err && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>{err}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess("")}>{success}</Alert>}

            <SectionLabel>Identity</SectionLabel>
            <Stack spacing={1.5}>
              <TextField label="Regimen name *" size="small" fullWidth value={reg.name} onChange={(e) => update("name", e.target.value)} placeholder="e.g., Azacitidine + Venetoclax" />
              <TextField label="Disease state" size="small" fullWidth value={reg.disease_state ?? ""} onChange={(e) => update("disease_state", e.target.value)} placeholder="e.g., AML, ALL, MDS" />
            </Stack>

            <SectionLabel>Classification</SectionLabel>
            <Box sx={{ p: 1.5, border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }}>On Study (IRB / CIRB)</Typography>
                <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>{reg.on_study ? "Active research protocol" : "Standard of care / off protocol"}</Typography>
              </Box>
              <Switch checked={reg.on_study} onChange={(e) => update("on_study", e.target.checked)} />
            </Box>

            <SectionLabel>Clinical Notes</SectionLabel>
            <TextField label="Notes" size="small" fullWidth multiline rows={3} value={reg.notes ?? ""} onChange={(e) => update("notes", e.target.value)} placeholder="Dose modifications, references, selection aids…" helperText="Shown in the regimen browser as a selection hint" />

            <Divider sx={{ my: 2.5 }} />

            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.25 }}>
              <Box>
                <Typography sx={{ fontWeight: 700, fontSize: "0.875rem", color: "#1e293b" }}>Agents ({reg.therapies.length})</Typography>
                <Typography sx={{ fontSize: "0.72rem", color: "#64748b" }}>Order sets calendar label stacking</Typography>
              </Box>
              <Button size="small" variant="outlined" onClick={() => setTherapyDialog({ open: true, index: null, initial: EMPTY_THERAPY })} sx={{ fontSize: "0.78rem" }}>+ Add agent</Button>
            </Box>

            {reg.therapies.length === 0 && (
              <Box onClick={() => setTherapyDialog({ open: true, index: null, initial: EMPTY_THERAPY })} sx={{ border: "1px dashed #cbd5e1", borderRadius: "6px", py: 4, textAlign: "center", cursor: "pointer", "&:hover": { borderColor: "#0f4c81", background: "#f8fafc" } }}>
                <Typography sx={{ fontSize: "0.85rem", color: "#94a3b8" }}>No agents yet — click to add one</Typography>
              </Box>
            )}

            <Stack spacing={1}>
              {reg.therapies.map((t, i) => {
                const colors = ROUTE_COLORS[t.route?.toUpperCase()] ?? { bg: "#f1f5f9", color: "#475569" };
                const optsList = t.options && t.options.length > 0 ? t.options : [{ dose: t.dose, duration: t.duration }];

                return (
                  <Box key={i} sx={{ p: 1.5, border: "1px solid #e2e8f0", borderRadius: "6px", background: "#fafafa", display: "flex", gap: 1.5, alignItems: "flex-start" }}>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25, pt: 0.25 }}>
                      {([-1, 1] as const).map((dir) => (
                        <Box key={dir} component="button" onClick={() => moveTherapy(i, dir)} disabled={(dir === -1 && i === 0) || (dir === 1 && i === reg.therapies.length - 1)} sx={{ border: "1px solid #e2e8f0", borderRadius: "3px", background: "#fff", cursor: "pointer", fontSize: "0.65rem", px: 0.5, py: 0.15, lineHeight: 1, color: "#475569", "&:disabled": { opacity: 0.25, cursor: "default" } }}>{dir === -1 ? "▲" : "▼"}</Box>
                      ))}
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                        <Typography sx={{ fontWeight: 700, fontSize: "0.875rem", color: "#0f172a" }}>{t.name}</Typography>
                        <Chip label={t.route} size="small" sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700, background: colors.bg, color: colors.color }} />
                        <Typography sx={{ fontSize: "0.72rem", color: "#64748b", ml: 0.5 }}>({t.frequency})</Typography>
                      </Box>
                      
                      <Box sx={{ mt: 0.5 }}>
                        {optsList.map((o, oIdx) => (
                          <Typography key={oIdx} sx={{ fontSize: "0.78rem", color: "#334155", mb: 0.25 }}>
                            <span style={{color: "#94a3b8", marginRight: 4}}>•</span> 
                            <strong>{o.dose}</strong> for {o.duration}
                          </Typography>
                        ))}
                      </Box>
                    </Box>
                    <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
                      <Button size="small" variant="outlined" onClick={() => setTherapyDialog({ open: true, index: i, initial: t })} sx={{ fontSize: "0.72rem", minWidth: 0, px: 1 }}>Edit</Button>
                      <Button size="small" color="error" variant="outlined" onClick={() => setConfirmTherapyDel(i)} sx={{ fontSize: "0.72rem", minWidth: 0, px: 1 }}>✕</Button>
                    </Stack>
                  </Box>
                );
              })}
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </>
  );
}

export default function RegimensPage() {
  const { data: names, error, isLoading } = useSWR("regimens", listRegimens);
  const [selected, setSelected] = React.useState<string | "__new__">("__new__");
  const [q, setQ] = React.useState("");

  const { data: selectedRegimen, isLoading: regLoading } = useSWR<Regimen>(
    selected && selected !== "__new__" ? ["regimen", selected] : null,
    () => getRegimen(selected as string)
  );

  const filtered = React.useMemo(() => {
    const xs = names || [];
    const qq = q.trim().toLowerCase();
    return qq ? xs.filter((n) => n.toLowerCase().includes(qq)) : xs;
  }, [names, q]);

  const editorKey = selected;
  const editorInitial = selected === "__new__" ? EMPTY_REGIMEN : (selectedRegimen ?? null);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>Regimen Editor</Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>Create, edit, and manage chemotherapy regimens</Typography>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
        <Card variant="outlined" sx={{ width: { xs: "100%", md: 260 }, flexShrink: 0 }}>
          <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
            <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
              <TextField fullWidth size="small" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} InputProps={{ startAdornment: <InputAdornment position="start"><Box component="span" sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>⌕</Box></InputAdornment> }} />
            </Box>
            <Box sx={{ px: 1.5, pb: 0.75 }}>
              <Button fullWidth size="small" variant={selected === "__new__" ? "contained" : "outlined"} onClick={() => setSelected("__new__")} sx={{ justifyContent: "flex-start", fontSize: "0.8rem", py: 0.75 }}>+ New regimen</Button>
            </Box>
            <Divider />
            {isLoading && <Box sx={{ px: 1.5, py: 1 }}>{[...Array(5)].map((_, i) => <Skeleton key={i} height={40} sx={{ mb: 0.25, borderRadius: "5px" }} />)}</Box>}
            {error && <Alert severity="error" sx={{ m: 1.5 }}>{String((error as any)?.message || error)}</Alert>}
            <Box sx={{ maxHeight: 500, overflowY: "auto" }}>
              <List disablePadding dense sx={{ px: 1, py: 0.75 }}>
                {filtered.map((n) => (
                  <ListItemButton key={n} selected={selected === n} onClick={() => setSelected(n)} sx={{ borderRadius: "5px", mb: 0.25, px: 1.5, py: 0.875, "&.Mui-selected": { background: "#eff6ff", "& .rn": { color: "#0f4c81", fontWeight: 700 } } }}>
                    <Typography className="rn" sx={{ fontSize: "0.875rem", fontWeight: 500, color: "#1e293b" }} noWrap>{n}</Typography>
                  </ListItemButton>
                ))}
              </List>
            </Box>
          </CardContent>
        </Card>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {regLoading && selected !== "__new__" ? (
            <Card variant="outlined"><CardContent sx={{ p: 2.5 }}>{[...Array(4)].map((_, i) => <Skeleton key={i} height={i === 0 ? 28 : 44} sx={{ mb: 1, borderRadius: "5px" }} />)}</CardContent></Card>
          ) : editorInitial !== null ? (
            <RegimenEditor key={editorKey} initial={editorInitial} isNew={selected === "__new__"} onSaved={(name) => { setSelected(name); globalMutate(["regimen", name]); }} onDeleted={() => setSelected(names?.find((n) => n !== selected) ?? "__new__")} />
          ) : null}
        </Box>
      </Stack>
    </Box>
  );
}