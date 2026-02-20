"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CssBaseline, Box, Typography, Divider } from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import React from "react";

const LinkBehavior = React.forwardRef<HTMLAnchorElement, any>(function LinkBehavior(props, ref) {
  const { href, ...other } = props;
  return <Link ref={ref} href={href} {...other} />;
});

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#0f4c81", light: "#1a6bb5", dark: "#0a3460" },
    secondary: { main: "#0369a1" },
    background: { default: "#f8fafc", paper: "#ffffff" },
    text: { primary: "#1e293b", secondary: "#64748b" },
    divider: "#e2e8f0",
  },
  typography: {
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    h1: { fontWeight: 700, letterSpacing: "-0.03em" },
    h2: { fontWeight: 700, letterSpacing: "-0.025em" },
    h3: { fontWeight: 600, letterSpacing: "-0.02em" },
    h4: { fontWeight: 600, letterSpacing: "-0.02em" },
    h5: { fontWeight: 600, letterSpacing: "-0.015em" },
    h6: { fontWeight: 600, letterSpacing: "-0.01em" },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.5 },
  },
  shape: { borderRadius: 6 },
  shadows: [
    "none",
    "0 1px 2px rgba(0,0,0,0.06)",
    "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
    "0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.06)",
    "0 10px 15px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.05)",
    "0 20px 25px rgba(0,0,0,0.08), 0 10px 10px rgba(0,0,0,0.04)",
    ...Array(19).fill("none"),
  ] as any,
  components: {
    MuiLink: { defaultProps: { component: LinkBehavior } },
    MuiButtonBase: { defaultProps: { LinkComponent: LinkBehavior } },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 500,
          letterSpacing: "0",
          fontSize: "0.9rem",
        },
        contained: {
          boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
          "&:hover": { boxShadow: "0 2px 4px rgba(0,0,0,0.12)" },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: "#0f4c81",
            },
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
          border: "1px solid #e2e8f0",
        },
      },
    },
    MuiDivider: {
      styleOverrides: { root: { borderColor: "#e2e8f0" } },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 500 } },
    },
  },
});

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "⊞" },
  { href: "/calendar", label: "Calendar", icon: "◫" },
  { href: "/regimens", label: "Regimens", icon: "≡" },
];

function NavLink({ href, label, icon }: { href: string; label: string; icon: string }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.25,
          px: 1.5,
          py: 0.875,
          borderRadius: "6px",
          fontSize: "0.875rem",
          fontWeight: active ? 600 : 400,
          color: active ? "#0f4c81" : "#64748b",
          background: active ? "#e8f2fc" : "transparent",
          transition: "all 0.15s ease",
          "&:hover": {
            background: active ? "#e8f2fc" : "#f1f5f9",
            color: active ? "#0f4c81" : "#334155",
          },
        }}
      >
        <Box component="span" sx={{ fontSize: "1rem", opacity: 0.8, width: 18, textAlign: "center" }}>
          {icon}
        </Box>
        {label}
      </Box>
    </Link>
  );
}

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", minHeight: "100vh" }}>
        {/* Sidebar */}
        <Box
          component="nav"
          sx={{
            width: 220,
            flexShrink: 0,
            background: "#ffffff",
            borderRight: "1px solid #e2e8f0",
            display: "flex",
            flexDirection: "column",
            position: "sticky",
            top: 0,
            height: "100vh",
            overflowY: "auto",
          }}
        >
          {/* Logo / Brand */}
          <Box sx={{ px: 2.5, pt: 3, pb: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 0.25 }}>
              <Box
                sx={{
                  width: 30,
                  height: 30,
                  borderRadius: "7px",
                  background: "linear-gradient(135deg, #0f4c81 0%, #1a6bb5 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Box component="span" sx={{ color: "white", fontSize: "0.95rem", fontWeight: 700, lineHeight: 1 }}>Rx</Box>
              </Box>
              <Box>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, color: "#0f4c81", letterSpacing: "-0.01em", lineHeight: 1.2, fontSize: "0.9rem" }}
                >
                  ChemoCalendar
                </Typography>
                <Typography sx={{ fontSize: "0.68rem", color: "#94a3b8", lineHeight: 1 }}>
                  Clinical Scheduling Tool
                </Typography>
              </Box>
            </Box>
          </Box>

          <Divider />

          {/* Nav items */}
          <Box sx={{ px: 1.5, py: 1.5, flex: 1 }}>
            <Typography sx={{ fontSize: "0.68rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", px: 1.5, pb: 1 }}>
              Navigation
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.href} {...item} />
              ))}
            </Box>
          </Box>

          {/* Footer */}
          <Box sx={{ px: 2.5, py: 2, borderTop: "1px solid #e2e8f0" }}>
            <Typography sx={{ fontSize: "0.7rem", color: "#94a3b8", lineHeight: 1.5 }}>
              For clinical use only.
              <br />
              Verify all schedules independently.
            </Typography>
          </Box>
        </Box>

        {/* Main content */}
        <Box
          component="main"
          sx={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Top bar */}
          <Box
            sx={{
              height: 52,
              background: "#ffffff",
              borderBottom: "1px solid #e2e8f0",
              display: "flex",
              alignItems: "center",
              px: 3,
              flexShrink: 0,
            }}
          >
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                gap: 1,
                px: 1.5,
                py: 0.5,
                background: "#fef3c7",
                border: "1px solid #fde68a",
                borderRadius: "5px",
              }}
            >
              <Box component="span" sx={{ fontSize: "0.75rem", color: "#92400e" }}>⚠</Box>
              <Typography sx={{ fontSize: "0.72rem", color: "#92400e", fontWeight: 500 }}>
                Educational / clinical support tool — always verify independently
              </Typography>
            </Box>
          </Box>

          {/* Page content */}
          <Box sx={{ flex: 1, p: 3, maxWidth: 1400, width: "100%" }}>
            {children}
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
