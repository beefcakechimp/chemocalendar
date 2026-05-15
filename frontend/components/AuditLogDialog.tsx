"use client";

import * as React from "react";
import useSWR from "swr";
import dayjs from "dayjs";
import { getAuditLog } from "@/lib/api";
import { AuditEntry } from "@/lib/types";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Box, Typography,
  Chip, Stack, Divider, CircularProgress, Alert,
} from "@mui/material";

const ACTION_COLORS: Record<string, { bg: string; color: string }> = {
  create: { bg: "#dcfce7", color: "#166534" },
  update: { bg: "#dbeafe", color: "#1d4ed8" },
  delete: { bg: "#fee2e2", color: "#b91c1c" },
};

function FieldDiff({ field, before, after }: { field: string; before: any; after: any }) {
  const sameLine = field !== "therapies" && field !== "notes";
  const fmt = (v: any) => {
    if (v === null || v === undefined || v === "") return <span style={{ color: "#94a3b8", fontStyle: "italic" }}>(empty)</span>;
    if (typeof v === "boolean") return v ? "Yes" : "No";
    if (typeof v === "object") return <pre style={{ margin: 0, fontSize: "0.7rem", whiteSpace: "pre-wrap" }}>{JSON.stringify(v, null, 2)}</pre>;
    return String(v);
  };

  return (
    <Box sx={{ py: 0.5 }}>
      <Typography sx={{ fontSize: "0.7rem", fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.05em", mb: 0.25 }}>{field}</Typography>
      {sameLine ? (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, fontSize: "0.8rem" }}>
          <Box sx={{ px: 0.75, py: 0.1, background: "#fef2f2", color: "#b91c1c", borderRadius: "3px", textDecoration: "line-through", maxWidth: "45%", overflow: "hidden", textOverflow: "ellipsis" }}>{fmt(before)}</Box>
          <Box component="span" sx={{ color: "#94a3b8" }}>→</Box>
          <Box sx={{ px: 0.75, py: 0.1, background: "#f0fdf4", color: "#166534", borderRadius: "3px", maxWidth: "45%", overflow: "hidden", textOverflow: "ellipsis" }}>{fmt(after)}</Box>
        </Box>
      ) : (
        <Stack spacing={0.5}>
          <Box sx={{ p: 0.75, background: "#fef2f2", color: "#b91c1c", borderRadius: "4px", fontSize: "0.78rem" }}>{fmt(before)}</Box>
          <Box sx={{ p: 0.75, background: "#f0fdf4", color: "#166534", borderRadius: "4px", fontSize: "0.78rem" }}>{fmt(after)}</Box>
        </Stack>
      )}
    </Box>
  );
}

function EntryCard({ e }: { e: AuditEntry }) {
  const c = ACTION_COLORS[e.action] || { bg: "#f1f5f9", color: "#475569" };
  const fields = e.diff?.fields_changed || [];
  const before = e.diff?.before ?? {};
  const after = e.diff?.after ?? {};

  return (
    <Box sx={{ border: "1px solid #e2e8f0", borderRadius: "6px", p: 1.5, mb: 1, background: "#fff" }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.75 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip label={e.action.toUpperCase()} size="small" sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700, background: c.bg, color: c.color }} />
          <Typography sx={{ fontSize: "0.85rem", fontWeight: 600, color: "#1e293b" }}>{e.regimen_name}</Typography>
        </Stack>
        <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }} title={e.timestamp}>
          {dayjs(e.timestamp).format("MMM D, YYYY h:mm A")}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: "0.75rem", color: "#64748b", mb: fields.length ? 1 : 0 }}>
        by <strong>{e.username}</strong>
      </Typography>
      {fields.length > 0 && (
        <>
          <Divider sx={{ my: 0.75 }} />
          <Stack spacing={0.25} divider={<Divider sx={{ my: 0.25 }} />}>
            {fields.map(f => <FieldDiff key={f} field={f} before={(before as any)[f]} after={(after as any)[f]} />)}
          </Stack>
        </>
      )}
    </Box>
  );
}

export default function AuditLogDialog({ open, onClose, regimenName }: { open: boolean; onClose: () => void; regimenName?: string }) {
  const key = open ? ["audit", regimenName || "__all__"] : null;
  const { data, error, isLoading } = useSWR<AuditEntry[]>(key, () => getAuditLog({ regimen_name: regimenName, limit: 200 }));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>
        {regimenName ? `History: ${regimenName}` : "All regimen changes"}
      </DialogTitle>
      <DialogContent sx={{ background: "#f8fafc" }}>
        {isLoading && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress size={24} /></Box>}
        {error && <Alert severity="error">{String((error as any)?.message || error)}</Alert>}
        {!isLoading && !error && (!data || data.length === 0) && (
          <Box sx={{ textAlign: "center", py: 4 }}>
            <Typography sx={{ fontSize: "0.85rem", color: "#94a3b8" }}>No changes recorded yet.</Typography>
          </Box>
        )}
        {data?.map(e => <EntryCard key={e.id} e={e} />)}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
