"use client";

import * as React from "react";
import useSWR from "swr";
import { listUsers } from "@/lib/api";
import { useCurrentUser } from "@/lib/user";
import { User } from "@/lib/types";
import { Box, Typography, Menu, MenuItem, Divider } from "@mui/material";
import UserPicker from "./UserPicker";

export default function UserBadge() {
  const [currentUser, setUser] = useCurrentUser();
  const { data: users } = useSWR<User[]>("users", listUsers);
  const [anchor, setAnchor] = React.useState<HTMLElement | null>(null);
  const [pickerOpen, setPickerOpen] = React.useState(false);

  // Auto-prompt if no user selected (after first mount)
  React.useEffect(() => {
    const id = setTimeout(() => {
      if (typeof window !== "undefined" && !window.localStorage.getItem("chemocalendar_user")) {
        setPickerOpen(true);
      }
    }, 50);
    return () => clearTimeout(id);
  }, []);

  const me = users?.find(u => u.username === currentUser);
  const label = me?.display_name || me?.username || currentUser || "Not signed in";
  const initials = (me?.display_name || me?.username || currentUser || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <>
      <Box
        onClick={(e) => setAnchor(e.currentTarget)}
        sx={{ display: "inline-flex", alignItems: "center", gap: 1, px: 1.25, py: 0.5, borderRadius: "20px", border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", "&:hover": { background: "#f8fafc" } }}
      >
        <Box sx={{ width: 24, height: 24, borderRadius: "50%", background: currentUser ? "linear-gradient(135deg, #0f4c81 0%, #1a6bb5 100%)" : "#94a3b8", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.65rem", fontWeight: 700 }}>
          {initials}
        </Box>
        <Typography sx={{ fontSize: "0.78rem", fontWeight: 600, color: currentUser ? "#1e293b" : "#94a3b8" }}>{label}</Typography>
        <Box component="span" sx={{ fontSize: "0.6rem", color: "#94a3b8" }}>▾</Box>
      </Box>

      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }}>
        <Box sx={{ px: 2, py: 1 }}>
          <Typography sx={{ fontSize: "0.7rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>Signed in as</Typography>
          <Typography sx={{ fontSize: "0.875rem", fontWeight: 600, color: "#1e293b" }}>{label}</Typography>
          {me?.display_name && <Typography sx={{ fontSize: "0.72rem", color: "#94a3b8" }}>@{me.username}</Typography>}
        </Box>
        <Divider />
        <MenuItem onClick={() => { setAnchor(null); setPickerOpen(true); }} sx={{ fontSize: "0.85rem" }}>Switch user…</MenuItem>
        <MenuItem onClick={() => { setAnchor(null); setUser(null); setPickerOpen(true); }} sx={{ fontSize: "0.85rem", color: "#b91c1c" }}>Sign out</MenuItem>
      </Menu>

      <UserPicker
        open={pickerOpen}
        onClose={currentUser ? () => setPickerOpen(false) : undefined}
        onPicked={() => setPickerOpen(false)}
      />
    </>
  );
}
