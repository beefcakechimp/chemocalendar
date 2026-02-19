"use client";

import * as React from "react";
import useSWR from "swr";
import { listRegimens, getRegimen } from "@/lib/api";
import { Regimen } from "@/lib/types";
import { Box, Card, CardContent, Divider, List, ListItemButton, ListItemText, Stack, Typography } from "@mui/material";

export default function RegimensPage() {
  const { data: names, error, isLoading } = useSWR("regimens", listRegimens);
  const [selected, setSelected] = React.useState<string>("");

  React.useEffect(() => {
    if (!selected && names && names.length) setSelected(names[0]);
  }, [names, selected]);

  const { data: regimen } = useSWR<Regimen>(
    selected ? ["regimen", selected] : null,
    () => getRegimen(selected)
  );

  return (
    <Stack spacing={2}>
      <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: "-0.03em" }}>
        Regimens
      </Typography>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <Card variant="outlined" sx={{ flex: 1, minWidth: 320 }}>
          <CardContent>
            <Typography sx={{ fontWeight: 800, mb: 1 }}>All regimens</Typography>

            <Box sx={{ border: "1px solid rgba(0,0,0,0.08)", borderRadius: 2, overflow: "hidden" }}>
              {isLoading && <Typography sx={{ p: 2, opacity: 0.7 }}>Loading…</Typography>}
              {error && <Typography sx={{ p: 2, color: "error.main" }}>{String((error as any)?.message || error)}</Typography>}

              <List disablePadding dense>
                {(names || []).map((n) => (
                  <ListItemButton key={n} selected={selected === n} onClick={() => setSelected(n)}>
                    <ListItemText primary={n} />
                  </ListItemButton>
                ))}
              </List>
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 2 }}>
          <CardContent>
            <Typography sx={{ fontWeight: 800, mb: 1 }}>Details</Typography>

            {!regimen ? (
              <Typography sx={{ opacity: 0.7 }}>Select a regimen to view details.</Typography>
            ) : (
              <>
                <Typography sx={{ fontWeight: 900 }}>{regimen.name}</Typography>
                <Typography sx={{ opacity: 0.75, mb: 1 }}>
                  {regimen.on_study ? "On study" : "Off protocol"}
                  {regimen.disease_state ? ` • ${regimen.disease_state}` : ""}
                </Typography>

                {regimen.notes ? (
                  <>
                    <Typography sx={{ fontWeight: 800, mt: 1 }}>Notes</Typography>
                    <Typography sx={{ whiteSpace: "pre-wrap" }}>{regimen.notes}</Typography>
                  </>
                ) : (
                  <Typography sx={{ opacity: 0.65 }}>No notes.</Typography>
                )}

                <Divider sx={{ my: 2 }} />

                <Typography sx={{ fontWeight: 800, mb: 1 }}>Therapies</Typography>
                {(regimen.therapies || []).length === 0 ? (
                  <Typography sx={{ opacity: 0.65 }}>No therapies.</Typography>
                ) : (
                  <Stack spacing={1}>
                    {regimen.therapies.map((t, i) => (
                      <Box key={`${t.name}-${i}`} sx={{ p: 1, border: "1px solid rgba(0,0,0,0.08)", borderRadius: 2 }}>
                        <Typography sx={{ fontWeight: 900 }}>{t.name}</Typography>
                        <Typography sx={{ opacity: 0.8, fontSize: 14 }}>
                          {t.route} • {t.dose} • {t.frequency} • {t.duration}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </Stack>
    </Stack>
  );
}