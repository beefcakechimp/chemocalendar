"use client";

import * as React from "react";
import useSWR from "swr";
import { listUsers, createUser } from "@/lib/api";
import { setCurrentUser } from "@/lib/user";
import { User } from "@/lib/types";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
  Stack, Typography, Box, List, ListItemButton, Divider, Alert,
} from "@mui/material";

export default function UserPicker({ open, onClose, onPicked }: { open: boolean; onClose?: () => void; onPicked?: (username: string) => void }) {
  const { data: users, mutate, isLoading } = useSWR<User[]>(open ? "users" : null, listUsers);
  const [newName, setNewName] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState("");

  const handlePick = (username: string) => {
    setCurrentUser(username);
    onPicked?.(username);
    onClose?.();
  };

  const handleCreate = async () => {
    const u = newName.trim().toLowerCase();
    if (!u) { setErr("Username is required"); return; }
    setBusy(true); setErr("");
    try {
      const created = await createUser(u, displayName.trim() || null);
      await mutate();
      handlePick(created.username);
    } catch (e: any) {
      setErr(e?.message || "Failed to create user");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth disableEscapeKeyDown={!onClose}>
      <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>Who are you?</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: "0.85rem", color: "#64748b", mb: 2 }}>
          Your name is attached to every regimen change in the audit log. Pick from your team or add yourself.
        </Typography>

        {err && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>{err}</Alert>}

        {(users && users.length > 0) && (
          <>
            <Typography sx={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", mb: 0.75 }}>Existing team members</Typography>
            <List dense disablePadding sx={{ mb: 2, maxHeight: 220, overflowY: "auto" }}>
              {users.map(u => (
                <ListItemButton key={u.username} onClick={() => handlePick(u.username)} sx={{ borderRadius: "5px", mb: 0.25, "&:hover": { background: "#f0f7ff" } }}>
                  <Box>
                    <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: "#1e293b" }}>{u.display_name || u.username}</Typography>
                    {u.display_name && <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }}>@{u.username}</Typography>}
                  </Box>
                </ListItemButton>
              ))}
            </List>
            <Divider sx={{ mb: 2 }}>
              <Typography sx={{ fontSize: "0.7rem", color: "#94a3b8" }}>or add yourself</Typography>
            </Divider>
          </>
        )}

        {!isLoading && (
          <Stack spacing={1.5}>
            <TextField size="small" label="Username *" placeholder="e.g., jsmith" value={newName} onChange={e => setNewName(e.target.value)} helperText="Lowercase, no spaces. Used internally." />
            <TextField size="small" label="Display name" placeholder="e.g., Jane Smith" value={displayName} onChange={e => setDisplayName(e.target.value)} />
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {onClose && <Button color="inherit" onClick={onClose}>Cancel</Button>}
        <Button variant="contained" onClick={handleCreate} disabled={busy || !newName.trim()}>
          {busy ? "Adding…" : "Add & continue"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
