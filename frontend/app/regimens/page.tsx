"use client";

import * as React from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { listRegimens, getRegimen, upsertRegimen, deleteRegimen } from "@/lib/api";
import { Regimen, Chemo, RegimenVariant } from "@/lib/types";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputAdornment,
  InputLabel,
  List,
  ListItemButton,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import Link from "next/link";

// ── Constants ─────────────────────────────────────────────────────────────────
const ROUTES = ["IV", "PO", "SQ", "IM", "IT"];

const ROUTE_COLORS: Record<string, { bg: string; color: string }> = {
  IV: { bg: "#dbeafe", color: "#1d4ed8" },
  PO: { bg: "#d1fae5", color: "#065f46" },
  SQ: { bg: "#fce7f3", color: "#9d174d" },
  IM: { bg: "#ede9fe", color: "#5b21b6" },
  IT: { bg: "#fef3c7", color: "#92400e" },
};

const EMPTY_THERAPY: Chemo = {
  name: "", route: "IV", dose: "", frequency: "", duration: "", total_doses: null,
};

const EMPTY_REGIMEN: Regimen = {
  name: "", disease_state: "", on_study: false, notes: "", therapies: [], variants: [],
};

// ── Helpers ───────────────────────────────────────────────────────────────────
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

// ── Therapy dialog ────────────────────────────────────────────────────────────
function TherapyDialog({ open, initial, onSave, onClose }: {
  open: boolean; initial: Chemo;
  onSave: (t: Chemo) => void; onClose: () => void;
}) {
  const [t, setT] = React.useState<Chemo>(initial);
  React.useEffect(() => { setT(initial); }, [initial, open]);

  const str = (key: keyof Chemo) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setT((p) => ({ ...p, [key]: e.target.value }));

  const valid = t.name.trim() && t.dose.trim() && t.frequency.trim() && t.duration.trim();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>
        {initial.name ? `Edit: ${initial.name}` : "Add Agent"}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <TextField label="Agent name *" size="small" fullWidth value={t.name} onChange={str("name")} placeholder="e.g., Cytarabine" />
          <Stack direction="row" spacing={1.5}>
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Route *</InputLabel>
              <Select label="Route *" value={t.route} onChange={(e) => setT((p) => ({ ...p, route: e.target.value }))}>
                {ROUTES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="Dose *" size="small" fullWidth value={t.dose} onChange={str("dose")} placeholder="e.g., 100 mg/m²" />
          </Stack>
          <TextField
            label="Frequency *" size="small" fullWidth value={t.frequency} onChange={str("frequency")}
            placeholder="e.g., once daily, BID, weekly"
            helperText="Free text — describe how often within a dosing day"
          />
          <TextField
            label="Day map *" size="small" fullWidth value={t.duration} onChange={str("duration")}
            placeholder="e.g., Days 1-7  or  Days 1,8,15"
            helperText="Controls which calendar cells are highlighted"
          />
          <TextField
            label="Total doses (optional)" size="small" fullWidth type="number"
            value={t.total_doses ?? ""}
            onChange={(e) => setT((p) => ({ ...p, total_doses: e.target.value === "" ? null : Number(e.target.value) }))}
            inputProps={{ min: 1 }}
            helperText="Leave blank to auto-calculate from the day map"
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button variant="contained" disabled={!valid} onClick={() => { onSave(t); onClose(); }}>
          Save Agent
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Confirm dialog ────────────────────────────────────────────────────────────
function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onClose }: {
  open: boolean; title: string; message: string;
  confirmLabel?: string; onConfirm: () => void; onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>{title}</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: "0.9rem", color: "#475569" }}>{message}</Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button variant="contained" color="error" onClick={() => { onConfirm(); onClose(); }}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Therapy list sub-component (reused for base + each variant) ───────────────
function TherapyList({
  therapies,
  onEdit,
  onDelete,
  onMove,
  onAdd,
  emptyLabel = "No agents yet — click to add one",
}: {
  therapies: Chemo[];
  onEdit: (index: number) => void;
  onDelete: (index: number) => void;
  onMove: (index: number, dir: -1 | 1) => void;
  onAdd: () => void;
  emptyLabel?: string;
}) {
  if (therapies.length === 0) {
    return (
      <Box
        onClick={onAdd}
        sx={{
          border: "1px dashed #cbd5e1", borderRadius: "6px", py: 3,
          textAlign: "center", cursor: "pointer",
          "&:hover": { borderColor: "#0f4c81", background: "#f8fafc" },
        }}
      >
        <Typography sx={{ fontSize: "0.82rem", color: "#94a3b8" }}>{emptyLabel}</Typography>
      </Box>
    );
  }

  return (
    <Stack spacing={0.75}>
      {therapies.map((t, i) => {
        const colors = ROUTE_COLORS[t.route?.toUpperCase()] ?? { bg: "#f1f5f9", color: "#475569" };
        return (
          <Box key={i} sx={{ p: 1.25, border: "1px solid #e2e8f0", borderRadius: "6px", background: "#fafafa", display: "flex", gap: 1.25, alignItems: "flex-start" }}>
            {/* Reorder */}
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25, pt: 0.25 }}>
              {([-1, 1] as const).map((dir) => (
                <Box key={dir} component="button"
                  onClick={() => onMove(i, dir)}
                  disabled={(dir === -1 && i === 0) || (dir === 1 && i === therapies.length - 1)}
                  sx={{
                    border: "1px solid #e2e8f0", borderRadius: "3px", background: "#fff",
                    cursor: "pointer", fontSize: "0.65rem", px: 0.5, py: 0.15, lineHeight: 1, color: "#475569",
                    "&:disabled": { opacity: 0.25, cursor: "default" },
                  }}>
                  {dir === -1 ? "▲" : "▼"}
                </Box>
              ))}
            </Box>

            {/* Info */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.4 }}>
                <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", color: "#0f172a" }}>{t.name}</Typography>
                <Chip label={t.route} size="small" sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700, background: colors.bg, color: colors.color }} />
              </Box>
              <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0.5 }}>
                {[{ l: "Dose", v: t.dose }, { l: "Frequency", v: t.frequency }, { l: "Days", v: t.duration }].map(({ l, v }) => (
                  <Box key={l}>
                    <Typography sx={{ fontSize: "0.6rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>{l}</Typography>
                    <Typography sx={{ fontSize: "0.75rem", color: "#334155" }}>{v}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Actions */}
            <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
              <Button size="small" variant="outlined"
                onClick={() => onEdit(i)}
                sx={{ fontSize: "0.72rem", minWidth: 0, px: 1 }}>Edit</Button>
              <Button size="small" color="error" variant="outlined"
                onClick={() => onDelete(i)}
                sx={{ fontSize: "0.72rem", minWidth: 0, px: 1 }}>✕</Button>
            </Stack>
          </Box>
        );
      })}
    </Stack>
  );
}

// ── Regimen editor ────────────────────────────────────────────────────────────
function RegimenEditor({ initial, onSaved, onDeleted, isNew }: {
  initial: Regimen; onSaved: (name: string) => void;
  onDeleted: () => void; isNew: boolean;
}) {
  const [reg, setReg] = React.useState<Regimen>(initial);
  const [saving, setSaving] = React.useState(false);
  const [err, setErr] = React.useState("");
  const [success, setSuccess] = React.useState("");
  const [dirty, setDirty] = React.useState(false);

  // Which variant accordions are expanded
  const [expandedVariants, setExpandedVariants] = React.useState<Set<number>>(new Set());

  // Therapy dialog state — tracks whether we're editing base or a variant
  const [therapyDialog, setTherapyDialog] = React.useState<{
    open: boolean;
    therapyIndex: number | null;   // null = adding new
    variantIndex: number | null;   // null = base therapies
    initial: Chemo;
  }>({ open: false, therapyIndex: null, variantIndex: null, initial: EMPTY_THERAPY });

  // Confirm dialogs
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [confirmTherapyDel, setConfirmTherapyDel] = React.useState<{
    variantIndex: number | null;
    therapyIndex: number;
  } | null>(null);
  const [confirmVariantDel, setConfirmVariantDel] = React.useState<number | null>(null);

  // New variant label input
  const [newVariantLabel, setNewVariantLabel] = React.useState("");
  const [showAddVariant, setShowAddVariant] = React.useState(false);

  React.useEffect(() => {
    setReg({ ...initial, variants: initial.variants ?? [] });
    setDirty(false);
    setErr("");
    setSuccess("");
    setExpandedVariants(new Set());
    setShowAddVariant(false);
    setNewVariantLabel("");
  }, [initial]);

  function update<K extends keyof Regimen>(key: K, value: Regimen[K]) {
    setReg((p) => ({ ...p, [key]: value }));
    setDirty(true);
  }

  // ── Therapy CRUD helpers ──────────────────────────────────────────────────

  function openTherapyDialog(variantIndex: number | null, therapyIndex: number | null) {
    const therapies = variantIndex === null
      ? reg.therapies
      : reg.variants[variantIndex].therapies;
    const initial = therapyIndex !== null ? { ...therapies[therapyIndex] } : EMPTY_THERAPY;
    setTherapyDialog({ open: true, therapyIndex, variantIndex, initial });
  }

  function handleTherapySave(t: Chemo) {
    const { therapyIndex, variantIndex } = therapyDialog;
    setReg((p) => {
      if (variantIndex === null) {
        const therapies = [...p.therapies];
        if (therapyIndex === null) therapies.push(t);
        else therapies[therapyIndex] = t;
        return { ...p, therapies };
      } else {
        const variants = [...p.variants];
        const variant = { ...variants[variantIndex], therapies: [...variants[variantIndex].therapies] };
        if (therapyIndex === null) variant.therapies.push(t);
        else variant.therapies[therapyIndex] = t;
        variants[variantIndex] = variant;
        return { ...p, variants };
      }
    });
    setDirty(true);
  }

  function handleTherapyDelete() {
    if (!confirmTherapyDel) return;
    const { variantIndex, therapyIndex } = confirmTherapyDel;
    setReg((p) => {
      if (variantIndex === null) {
        return { ...p, therapies: p.therapies.filter((_, i) => i !== therapyIndex) };
      } else {
        const variants = [...p.variants];
        const variant = { ...variants[variantIndex], therapies: variants[variantIndex].therapies.filter((_, i) => i !== therapyIndex) };
        variants[variantIndex] = variant;
        return { ...p, variants };
      }
    });
    setDirty(true);
  }

  function moveTherapy(variantIndex: number | null, i: number, dir: -1 | 1) {
    setReg((p) => {
      if (variantIndex === null) {
        const therapies = [...p.therapies];
        const j = i + dir;
        if (j < 0 || j >= therapies.length) return p;
        [therapies[i], therapies[j]] = [therapies[j], therapies[i]];
        return { ...p, therapies };
      } else {
        const variants = [...p.variants];
        const variant = { ...variants[variantIndex], therapies: [...variants[variantIndex].therapies] };
        const j = i + dir;
        if (j < 0 || j >= variant.therapies.length) return p;
        [variant.therapies[i], variant.therapies[j]] = [variant.therapies[j], variant.therapies[i]];
        variants[variantIndex] = variant;
        return { ...p, variants };
      }
    });
    setDirty(true);
  }

  // ── Variant CRUD helpers ──────────────────────────────────────────────────

  function addVariant() {
    const label = newVariantLabel.trim();
    if (!label) return;
    setReg((p) => ({
      ...p,
      variants: [...(p.variants ?? []), { label, therapies: [] }],
    }));
    const newIndex = (reg.variants?.length ?? 0);
    setExpandedVariants((s) => new Set([...s, newIndex]));
    setNewVariantLabel("");
    setShowAddVariant(false);
    setDirty(true);
  }

  function updateVariantLabel(index: number, label: string) {
    setReg((p) => {
      const variants = [...p.variants];
      variants[index] = { ...variants[index], label };
      return { ...p, variants };
    });
    setDirty(true);
  }

  function deleteVariant(index: number) {
    setReg((p) => ({
      ...p,
      variants: p.variants.filter((_, i) => i !== index),
    }));
    setExpandedVariants((s) => {
      const next = new Set<number>();
      s.forEach((vi) => { if (vi < index) next.add(vi); else if (vi > index) next.add(vi - 1); });
      return next;
    });
    setDirty(true);
  }

  function toggleVariant(index: number) {
    setExpandedVariants((s) => {
      const next = new Set(s);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  // ── Save / Delete ──────────────────────────────────────────────────────────

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

  return (
    <>
      <TherapyDialog
        open={therapyDialog.open}
        initial={therapyDialog.initial}
        onSave={handleTherapySave}
        onClose={() => setTherapyDialog((s) => ({ ...s, open: false }))}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="Delete regimen?"
        message={`"${initial.name}" and all its agents and variants will be permanently deleted.`}
        onConfirm={handleDelete}
        onClose={() => setConfirmDelete(false)}
      />
      <ConfirmDialog
        open={confirmTherapyDel !== null}
        title="Remove agent?"
        message={`Remove "${confirmTherapyDel !== null
          ? (confirmTherapyDel.variantIndex === null
            ? reg.therapies[confirmTherapyDel.therapyIndex]?.name
            : reg.variants[confirmTherapyDel.variantIndex]?.therapies[confirmTherapyDel.therapyIndex]?.name)
          : ""}" from this regimen?`}
        confirmLabel="Remove"
        onConfirm={handleTherapyDelete}
        onClose={() => setConfirmTherapyDel(null)}
      />
      <ConfirmDialog
        open={confirmVariantDel !== null}
        title="Delete variant?"
        message={`Delete variant "${confirmVariantDel !== null ? reg.variants[confirmVariantDel]?.label : ""}" and all its agents?`}
        onConfirm={() => { if (confirmVariantDel !== null) deleteVariant(confirmVariantDel); }}
        onClose={() => setConfirmVariantDel(null)}
      />

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>

          {/* Header */}
          <Box sx={{ px: 2.5, py: 2, borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: "1rem", color: "#0f172a" }}>
                {isNew ? "New Regimen" : reg.name || "Edit Regimen"}
              </Typography>
              {dirty && <Typography sx={{ fontSize: "0.72rem", color: "#b45309", mt: 0.25 }}>● Unsaved changes</Typography>}
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {!isNew && (
                <Button size="small" color="error" variant="outlined" onClick={() => setConfirmDelete(true)} sx={{ fontSize: "0.78rem" }}>
                  Delete
                </Button>
              )}
              {!isNew && (
                <Button size="small" variant="outlined" component={Link} href={`/calendar?regimen=${encodeURIComponent(initial.name)}`} sx={{ fontSize: "0.78rem", whiteSpace: "nowrap" }}>
                  Open in calendar →
                </Button>
              )}
              <Button size="small" variant="contained" onClick={handleSave} disabled={saving || !dirty} sx={{ fontSize: "0.78rem" }}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </Stack>
          </Box>

          {/* Body */}
          <Box sx={{ p: 2.5 }}>
            {err && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>{err}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess("")}>{success}</Alert>}

            <SectionLabel>Identity</SectionLabel>
            <Stack spacing={1.5}>
              <TextField label="Regimen name *" size="small" fullWidth value={reg.name}
                onChange={(e) => update("name", e.target.value)} placeholder="e.g., Azacitidine + Venetoclax" />
              <TextField label="Disease state" size="small" fullWidth value={reg.disease_state ?? ""}
                onChange={(e) => update("disease_state", e.target.value)} placeholder="e.g., AML, ALL, MDS" />
            </Stack>

            <SectionLabel>Classification</SectionLabel>
            <Box sx={{ p: 1.5, border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }}>On Study (IRB / CIRB)</Typography>
                <Typography sx={{ fontSize: "0.75rem", color: "#64748b" }}>
                  {reg.on_study ? "Active research protocol" : "Standard of care / off protocol"}
                </Typography>
              </Box>
              <Switch checked={reg.on_study} onChange={(e) => update("on_study", e.target.checked)} />
            </Box>

            <SectionLabel>Clinical Notes</SectionLabel>
            <TextField label="Notes" size="small" fullWidth multiline rows={3} value={reg.notes ?? ""}
              onChange={(e) => update("notes", e.target.value)}
              placeholder="Dose modifications, references, selection aids…"
              helperText="Shown in the regimen browser as a selection hint" />

            <Divider sx={{ my: 2.5 }} />

            {/* ── Base Agents ── */}
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.25 }}>
              <Box>
                <Typography sx={{ fontWeight: 700, fontSize: "0.875rem", color: "#1e293b" }}>
                  Base Agents ({reg.therapies.length})
                </Typography>
                <Typography sx={{ fontSize: "0.72rem", color: "#64748b" }}>
                  Default therapy list — used when no variant is selected
                </Typography>
              </Box>
              <Button size="small" variant="outlined"
                onClick={() => openTherapyDialog(null, null)}
                sx={{ fontSize: "0.78rem" }}>
                + Add agent
              </Button>
            </Box>

            <TherapyList
              therapies={reg.therapies}
              onEdit={(i) => openTherapyDialog(null, i)}
              onDelete={(i) => setConfirmTherapyDel({ variantIndex: null, therapyIndex: i })}
              onMove={(i, dir) => moveTherapy(null, i, dir)}
              onAdd={() => openTherapyDialog(null, null)}
            />

            <Divider sx={{ my: 2.5 }} />

            {/* ── Variants ── */}
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.25 }}>
              <Box>
                <Typography sx={{ fontWeight: 700, fontSize: "0.875rem", color: "#1e293b" }}>
                  Dose Variants ({reg.variants?.length ?? 0})
                </Typography>
                <Typography sx={{ fontSize: "0.72rem", color: "#64748b" }}>
                  Named alternatives — e.g., different venetoclax dose levels
                </Typography>
              </Box>
              <Button size="small" variant="outlined"
                onClick={() => setShowAddVariant((v) => !v)}
                sx={{ fontSize: "0.78rem" }}>
                + Add variant
              </Button>
            </Box>

            {/* Add variant input */}
            <Collapse in={showAddVariant}>
              <Box sx={{ mb: 1.5, p: 1.5, border: "1px solid #e2e8f0", borderRadius: "6px", background: "#f8fafc" }}>
                <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "#475569", mb: 1 }}>
                  New variant label
                </Typography>
                <Stack direction="row" spacing={1}>
                  <TextField
                    size="small" fullWidth
                    placeholder="e.g., 400 mg venetoclax, Reduced dose"
                    value={newVariantLabel}
                    onChange={(e) => setNewVariantLabel(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") addVariant(); }}
                    autoFocus
                  />
                  <Button variant="contained" size="small" onClick={addVariant} disabled={!newVariantLabel.trim()}>
                    Add
                  </Button>
                  <Button size="small" color="inherit" onClick={() => { setShowAddVariant(false); setNewVariantLabel(""); }}>
                    Cancel
                  </Button>
                </Stack>
              </Box>
            </Collapse>

            {/* Variant list */}
            {(reg.variants?.length ?? 0) === 0 && !showAddVariant && (
              <Box
                onClick={() => setShowAddVariant(true)}
                sx={{
                  border: "1px dashed #cbd5e1", borderRadius: "6px", py: 3,
                  textAlign: "center", cursor: "pointer",
                  "&:hover": { borderColor: "#0f4c81", background: "#f8fafc" },
                }}
              >
                <Typography sx={{ fontSize: "0.82rem", color: "#94a3b8" }}>
                  No variants — click to add one (e.g. different dose levels for the same regimen)
                </Typography>
              </Box>
            )}

            <Stack spacing={1}>
              {(reg.variants ?? []).map((variant, vi) => {
                const isExpanded = expandedVariants.has(vi);
                return (
                  <Box key={vi} sx={{ border: "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden" }}>
                    {/* Variant header */}
                    <Box
                      sx={{
                        px: 2, py: 1.25,
                        background: isExpanded ? "#f0f7ff" : "#fafafa",
                        borderBottom: isExpanded ? "1px solid #e2e8f0" : "none",
                        display: "flex", alignItems: "center", gap: 1.5,
                        cursor: "pointer",
                        "&:hover": { background: "#f0f7ff" },
                      }}
                      onClick={() => toggleVariant(vi)}
                    >
                      <Box
                        component="span"
                        sx={{
                          fontSize: "0.7rem",
                          color: "#94a3b8",
                          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                          transition: "transform 0.15s",
                          display: "inline-block",
                          userSelect: "none",
                        }}
                      >
                        ▶
                      </Box>
                      <Chip
                        label="variant"
                        size="small"
                        sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, background: "#fef3c7", color: "#92400e" }}
                      />
                      <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#0f172a", flex: 1 }}>
                        {variant.label}
                      </Typography>
                      <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8", mr: 1 }}>
                        {variant.therapies.length} agent{variant.therapies.length !== 1 ? "s" : ""}
                      </Typography>
                      <Stack direction="row" spacing={0.5} onClick={(e) => e.stopPropagation()}>
                        <Button
                          size="small" variant="outlined"
                          onClick={() => setConfirmVariantDel(vi)}
                          color="error"
                          sx={{ fontSize: "0.7rem", minWidth: 0, px: 1, py: 0.25 }}
                        >
                          Delete
                        </Button>
                      </Stack>
                    </Box>

                    {/* Variant body */}
                    <Collapse in={isExpanded}>
                      <Box sx={{ p: 2 }}>
                        {/* Editable label */}
                        <TextField
                          size="small" fullWidth label="Variant label"
                          value={variant.label}
                          onChange={(e) => updateVariantLabel(vi, e.target.value)}
                          sx={{ mb: 1.5 }}
                          onClick={(e) => e.stopPropagation()}
                        />

                        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
                          <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "#475569" }}>
                            Agents
                          </Typography>
                          <Button
                            size="small" variant="outlined"
                            onClick={() => openTherapyDialog(vi, null)}
                            sx={{ fontSize: "0.72rem" }}
                          >
                            + Add agent
                          </Button>
                        </Box>

                        <TherapyList
                          therapies={variant.therapies}
                          onEdit={(i) => openTherapyDialog(vi, i)}
                          onDelete={(i) => setConfirmTherapyDel({ variantIndex: vi, therapyIndex: i })}
                          onMove={(i, dir) => moveTherapy(vi, i, dir)}
                          onAdd={() => openTherapyDialog(vi, null)}
                          emptyLabel="No agents — click to add one"
                        />
                      </Box>
                    </Collapse>
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

// ── Main page ─────────────────────────────────────────────────────────────────
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
  const editorInitial = selected === "__new__"
    ? EMPTY_REGIMEN
    : (selectedRegimen ?? null);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>Regimen Editor</Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>Create, edit, and manage chemotherapy regimens and dose variants</Typography>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">

        {/* List panel */}
        <Card variant="outlined" sx={{ width: { xs: "100%", md: 260 }, flexShrink: 0 }}>
          <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
            <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
              <TextField fullWidth size="small" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)}
                InputProps={{ startAdornment: <InputAdornment position="start"><Box component="span" sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>⌕</Box></InputAdornment> }} />
            </Box>

            <Box sx={{ px: 1.5, pb: 0.75 }}>
              <Button fullWidth size="small" variant={selected === "__new__" ? "contained" : "outlined"}
                onClick={() => setSelected("__new__")} sx={{ justifyContent: "flex-start", fontSize: "0.8rem", py: 0.75 }}>
                + New regimen
              </Button>
            </Box>

            <Divider />

            {isLoading && (
              <Box sx={{ px: 1.5, py: 1 }}>
                {[...Array(5)].map((_, i) => <Skeleton key={i} height={40} sx={{ mb: 0.25, borderRadius: "5px" }} />)}
              </Box>
            )}
            {error && <Alert severity="error" sx={{ m: 1.5 }}>{String((error as any)?.message || error)}</Alert>}

            <Box sx={{ maxHeight: 500, overflowY: "auto" }}>
              <List disablePadding dense sx={{ px: 1, py: 0.75 }}>
                {filtered.map((n) => (
                  <ListItemButton key={n} selected={selected === n} onClick={() => setSelected(n)}
                    sx={{
                      borderRadius: "5px", mb: 0.25, px: 1.5, py: 0.875,
                      "&.Mui-selected": { background: "#eff6ff", "& .rn": { color: "#0f4c81", fontWeight: 700 } },
                    }}>
                    <Typography className="rn" sx={{ fontSize: "0.875rem", fontWeight: 500, color: "#1e293b" }} noWrap>{n}</Typography>
                  </ListItemButton>
                ))}
                {!isLoading && filtered.length === 0 && (
                  <Box sx={{ textAlign: "center", py: 3 }}>
                    <Typography sx={{ fontSize: "0.8rem", color: "#94a3b8" }}>No regimens found</Typography>
                  </Box>
                )}
              </List>
            </Box>

            <Box sx={{ px: 2, py: 1, borderTop: "1px solid #e2e8f0" }}>
              <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                {names?.length ?? 0} regimen{(names?.length ?? 0) !== 1 ? "s" : ""} total
              </Typography>
            </Box>
          </CardContent>
        </Card>

        {/* Editor panel */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {regLoading && selected !== "__new__" ? (
            <Card variant="outlined">
              <CardContent sx={{ p: 2.5 }}>
                {[...Array(4)].map((_, i) => <Skeleton key={i} height={i === 0 ? 28 : 44} sx={{ mb: 1, borderRadius: "5px" }} />)}
              </CardContent>
            </Card>
          ) : editorInitial !== null ? (
            <RegimenEditor
              key={editorKey}
              initial={editorInitial}
              isNew={selected === "__new__"}
              onSaved={(name) => { setSelected(name); globalMutate(["regimen", name]); }}
              onDeleted={() => setSelected(names?.find((n) => n !== selected) ?? "__new__")}
            />
          ) : null}
        </Box>
      </Stack>
    </Box>
  );
}
