import { useEffect, useState } from "react";
import { getStages } from "./api";

// Module-level cache: relationship stages are static config, fetched once
// and shared across every component that needs the list or a label lookup.
let cache = null;
let inflight = null;

function loadStages() {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = getStages().then((data) => {
      cache = data;
      return data;
    });
  }
  return inflight;
}

export function useStages() {
  const [stages, setStages] = useState(cache || []);

  useEffect(() => {
    if (cache) return;
    loadStages().then(setStages);
  }, []);

  return stages; // [{id, label}, ...]
}

export function stageLabel(stages, id) {
  return stages.find((s) => s.id === id)?.label || id;
}
