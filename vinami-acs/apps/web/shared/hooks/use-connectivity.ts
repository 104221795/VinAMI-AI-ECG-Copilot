"use client";

import { useEffect, useState } from "react";

export function useConnectivity() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(window.navigator.onLine);
    const connected = () => setOnline(true);
    const disconnected = () => setOnline(false);
    window.addEventListener("online", connected);
    window.addEventListener("offline", disconnected);
    return () => {
      window.removeEventListener("online", connected);
      window.removeEventListener("offline", disconnected);
    };
  }, []);
  return online;
}
