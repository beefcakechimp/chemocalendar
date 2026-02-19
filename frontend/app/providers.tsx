"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { CssBaseline } from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import React from "react";

const LinkBehavior = React.forwardRef<HTMLAnchorElement, any>(function LinkBehavior(
  props,
  ref
) {
  const { href, ...other } = props;
  return <Link ref={ref} href={href} {...other} />;
});

const theme = createTheme({
  palette: { mode: "light" },
  components: {
    MuiLink: {
      defaultProps: {
        component: LinkBehavior,
      },
    },
    MuiButtonBase: {
      defaultProps: {
        LinkComponent: LinkBehavior,
      },
    },
  },
});

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}