"use client";
import * as React from "react";

const STORAGE_KEY = "chemocalendar_user";
const EVENT = "chemocalendar_user_changed";

export function getCurrentUser(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function setCurrentUser(username: string | null) {
  if (typeof window === "undefined") return;
  if (username) window.localStorage.setItem(STORAGE_KEY, username);
  else window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function useCurrentUser(): [string | null, (u: string | null) => void] {
  const [user, setUser] = React.useState<string | null>(null);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    setUser(getCurrentUser());
    setReady(true);
    const onChange = () => setUser(getCurrentUser());
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  return [ready ? user : null, setCurrentUser];
}
