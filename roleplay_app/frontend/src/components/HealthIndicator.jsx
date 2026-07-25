import { useEffect, useState } from "react";
import { getHealth } from "../api";

const POLL_MS = 10000;

export default function HealthIndicator() {
  const [healthy, setHealthy] = useState(null); // null = checking

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      getHealth()
        .then((data) => {
          if (!cancelled) setHealthy(!!data.llama_server);
        })
        .catch(() => {
          if (!cancelled) setHealthy(false);
        });
    };
    check();
    const interval = setInterval(check, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const stateClass = healthy === null ? "health-unknown" : healthy ? "health-online" : "health-offline";
  const label = healthy === null ? "Checking…" : healthy ? "Model online" : "Model offline";

  return (
    <div className={`health-indicator ${stateClass}`} title="llama-server status">
      <span className="health-dot" />
      <span className="health-label">{label}</span>
    </div>
  );
}
