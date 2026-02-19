"use client";

import * as React from "react";
import useSWR from "swr";
import { listRegimens } from "@/lib/api";
import { Box, Card, CardContent, Typography, TextField, List, ListItemButton, ListItemText, Stack, Button } from "@mui/material";
import Link from "next/link";

export default function DashboardPage() {
  const { data: names, error, isLoading } = useSWR("regimens", listRegimens);
  const [q, setQ] = React.useState("");

  const filtered = React.useMemo(() => {
    const xs = names || [];
    const qq = q.trim().toLowerCase();
    if (!qq) return xs;
    return xs.filter((n) => n.toLowerCase().includes(qq));
  }, [names, q]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: "-0.03em" }}>
        Dashboard
      </Typography>

      <Card variant="outlined">
        <CardContent>
          <Typography sx={{ fontWeight: 800, mb: 1 }}>Quick actions</Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button component={Link} href="/calendar" variant="contained">Generate calendar</Button>
            <Button component={Link} href="/regimens" variant="outlined">Manage regimens</Button>
          </Stack>
        </CardContent>
      </Card>

      <Card variant="outlined">
        <CardContent>
          <Typography sx={{ fontWeight: 800, mb: 1 }}>Find a regimen</Typography>
          <TextField
            fullWidth
            placeholder="Search regimens…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            size="small"
          />

          <Box sx={{ mt: 1, border: "1px solid rgba(0,0,0,0.08)", borderRadius: 2, overflow: "hidden" }}>
            {isLoading && <Typography sx={{ p: 2, opacity: 0.7 }}>Loading…</Typography>}
            {error && <Typography sx={{ p: 2, color: "error.main" }}>{String((error as any)?.message || error)}</Typography>}
            {!isLoading && !error && filtered.length === 0 && (
              <Typography sx={{ p: 2, opacity: 0.7 }}>No matching regimens.</Typography>
            )}
            <List disablePadding dense>
              {filtered.slice(0, 12).map((n) => (
                <ListItemButton key={n} component={Link} href={`/calendar?regimen=${encodeURIComponent(n)}`}>
                  <ListItemText primary={n} />
                </ListItemButton>
              ))}
            </List>
          </Box>
        </CardContent>
      </Card>
    </Stack>
  );
}