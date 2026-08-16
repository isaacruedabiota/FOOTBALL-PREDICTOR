"use client";
import { useEffect } from "react";

// Registra el service worker (solo en producción, para no interferir en `next dev`).
export default function RegisterSW() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
