import { useState } from "react";
import { getSessionDebug } from "../api";

export default function DebugPanel({ sessionId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleToggle = (e) => {
    if (!e.target.open) return;
    setLoading(true);
    getSessionDebug(sessionId)
      .then(setData)
      .finally(() => setLoading(false));
  };

  return (
    <details className="debug-panel" onToggle={handleToggle}>
      <summary>🐛 Debug: summary state &amp; RAG</summary>
      <div className="debug-panel-body">
        {loading && <p className="debug-loading">Loading…</p>}
        {data && (
          <>
            <h5>Summary state</h5>
            <pre className="debug-json">{JSON.stringify(data.summary, null, 2)}</pre>
            <h5>RAG hits for the current turn</h5>
            {data.rag_hits.length === 0 ? (
              <p className="debug-empty">No RAG hits right now (nothing outside the recent window yet, or nothing relevant).</p>
            ) : (
              <ul className="debug-rag-list">
                {data.rag_hits.map((h) => (
                  <li key={h.seq}>
                    <span className="debug-rag-meta">
                      seq {h.seq} · distance {h.distance.toFixed(3)}
                    </span>
                    <span className="debug-rag-content">{h.content}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </details>
  );
}
