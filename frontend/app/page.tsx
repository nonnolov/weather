"use client";

import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "../lib/api";

type HealthState =
  | { kind: "loading" }
  | { kind: "success"; data: HealthResponse }
  | { kind: "error"; message: string };

export default function Home() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((data) => setHealth({ kind: "success", data }))
      .catch((error: unknown) =>
        setHealth({
          kind: "error",
          message: error instanceof Error ? error.message : "Unable to reach the backend.",
        }),
      );
  }, []);

  return (
    <main>
      <h1>Weather Forecasting System</h1>
      <section aria-live="polite">
        <h2>Backend health</h2>
        {health.kind === "loading" && <p>Checking backend connection...</p>}
        {health.kind === "success" && (
          <p>
            Status: {health.data.status} (version {health.data.version})
          </p>
        )}
        {health.kind === "error" && <p role="alert">Connection error: {health.message}</p>}
      </section>
    </main>
  );
}


