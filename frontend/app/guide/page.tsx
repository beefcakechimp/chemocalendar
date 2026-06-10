"use client";

import * as React from "react";
import Link from "next/link";
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import CalendarMonthRoundedIcon from "@mui/icons-material/CalendarMonthRounded";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import MedicationRoundedIcon from "@mui/icons-material/MedicationRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";

const STEPS: { icon: React.ReactNode; title: string; body: string; href?: string; linkLabel?: string }[] = [
  {
    icon: <SearchRoundedIcon />,
    title: "Find a regimen",
    body: "Browse the regimen library on the Dashboard — regimens are grouped by disease state. Expand a group, or type in the search box to filter by regimen name or disease.",
    href: "/",
    linkLabel: "Open Dashboard",
  },
  {
    icon: <CalendarMonthRoundedIcon />,
    title: "Open the calendar generator",
    body: "Click any regimen in the library to load it straight into the Calendar page, or open the Calendar page first and pick a regimen from the dropdown there.",
    href: "/calendar",
    linkLabel: "Open Calendar",
  },
  {
    icon: <TuneRoundedIcon />,
    title: "Configure the cycle",
    body: "Set the start date, cycle length, and phase or cycle number. Adjust each agent's dose and treatment days, and where a regimen offers dosing variants, choose one with the radio buttons. You can also add an optional note (e.g., hold parameters) that prints beneath the calendar title.",
  },
  {
    icon: <DownloadRoundedIcon />,
    title: "Preview & export",
    body: "Generate a live preview to check the schedule and the patient instructions that will print at the bottom of the document. When everything looks right, export a print-ready DOCX calendar.",
  },
  {
    icon: <MedicationRoundedIcon />,
    title: "Manage regimens",
    body: "Add, edit, rename, or remove regimens and their agents on the Regimens page so the library stays current. Agent order controls how drug labels stack inside each calendar day.",
    href: "/regimens",
    linkLabel: "Open Regimens",
  },
];

const DAY_FORMATS: { spec: string; meaning: string }[] = [
  { spec: "Days 1-7", meaning: "Every day from Day 1 to Day 7" },
  { spec: "1, 8, 15", meaning: "Days 1, 8, and 15 only" },
  { spec: "1-3, 8-10", meaning: "Days 1 to 3 and Days 8 to 10" },
  { spec: "Day 1", meaning: "A single day" },
];

export default function GuidePage() {
  return (
    <Box sx={{ maxWidth: 860 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a", mb: 0.5 }}>
          How to Use
        </Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>
          Build a treatment-cycle calendar in a few steps
        </Typography>
      </Box>

      {/* Steps */}
      <Stack spacing={1.5} sx={{ mb: 3 }}>
        {STEPS.map((step, i) => (
          <Card key={i} variant="outlined">
            <CardContent sx={{ display: "flex", gap: 2, alignItems: "flex-start", py: 2, px: 2.5, "&:last-child": { pb: 2 } }}>
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: "10px",
                  background: "#e8f2fc",
                  color: "#0f4c81",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  "& svg": { fontSize: "1.3rem" },
                }}
              >
                {step.icon}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.25 }}>
                  <Chip
                    label={`Step ${i + 1}`}
                    size="small"
                    sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, background: "#e8f2fc", color: "#0f4c81" }}
                  />
                  <Typography sx={{ fontWeight: 600, fontSize: "0.95rem", color: "#1e293b" }}>
                    {step.title}
                  </Typography>
                </Box>
                <Typography sx={{ fontSize: "0.85rem", color: "#64748b", lineHeight: 1.6 }}>
                  {step.body}
                </Typography>
                {step.href && (
                  <Button
                    component={Link}
                    href={step.href}
                    size="small"
                    endIcon={<ArrowForwardRoundedIcon sx={{ fontSize: "0.85rem !important" }} />}
                    sx={{ mt: 1, fontSize: "0.75rem", color: "#0f4c81", px: 1, minWidth: 0 }}
                  >
                    {step.linkLabel}
                  </Button>
                )}
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>

      {/* Day format cheat sheet */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 2.25, px: 2.5, "&:last-child": { pb: 2.25 } }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.95rem", color: "#1e293b", mb: 0.25 }}>
            Treatment-day formats
          </Typography>
          <Typography sx={{ fontSize: "0.8rem", color: "#64748b", mb: 1.5 }}>
            The &ldquo;Days&rdquo; field for each agent accepts ranges, lists, or a mix of both:
          </Typography>
          <Stack spacing={0.75}>
            {DAY_FORMATS.map((f) => (
              <Box key={f.spec} sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Box
                  component="code"
                  sx={{
                    fontFamily: "'DM Mono', monospace",
                    fontSize: "0.78rem",
                    background: "#f1f5f9",
                    border: "1px solid #e2e8f0",
                    borderRadius: "5px",
                    px: 1,
                    py: 0.4,
                    color: "#0f4c81",
                    minWidth: 110,
                    textAlign: "center",
                    flexShrink: 0,
                  }}
                >
                  {f.spec}
                </Box>
                <Typography sx={{ fontSize: "0.82rem", color: "#475569" }}>{f.meaning}</Typography>
              </Box>
            ))}
          </Stack>
        </CardContent>
      </Card>

      {/* Disclaimer */}
      <Box
        sx={{
          px: 2,
          py: 1.75,
          background: "#fffbeb",
          border: "1px solid #fde68a",
          borderRadius: "8px",
          display: "flex",
          gap: 1.25,
          alignItems: "flex-start",
        }}
      >
        <WarningAmberRoundedIcon sx={{ fontSize: "1.1rem", color: "#92400e", mt: 0.2 }} />
        <Typography sx={{ fontSize: "0.82rem", color: "#92400e", lineHeight: 1.55 }}>
          <Box component="span" sx={{ fontWeight: 700 }}>Clinical support tool.</Box>{" "}
          Generated calendars are aids for scheduling only. Always verify doses, days, and
          supportive care against the source protocol and order set before use.
        </Typography>
      </Box>
    </Box>
  );
}
