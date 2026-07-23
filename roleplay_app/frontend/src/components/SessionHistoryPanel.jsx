import { useEffect, useState } from "react";
import { listHiddenSessions, unhideSession } from "../api";
import PinModal from "./PinModal";

export default function SessionHistoryPanel({ sessions, characterId, onSelect, onClose, onHide, onUnhidden }) {
  const [hidden, setHidden] = useState([]);
  const [showHidden, setShowHidden] = useState(false);
  const [unlocking, setUnlocking] = useState(null);

  const refreshHidden = () => listHiddenSessions(characterId).then(setHidden);

  useEffect(() => {
    refreshHidden();
  }, [characterId]);

  return (
    <div className="session-history">
      <div className="session-history-header">
        <h4>Past Conversations</h4>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      {sessions.length === 0 ? (
        <p className="session-history-empty">No past conversations yet.</p>
      ) : (
        <ul className="session-history-list">
          {sessions.map((s) => (
            <li key={s.id} className="session-history-row">
              <button className="session-history-item" onClick={() => onSelect(s.id)}>
                <span className="session-history-date">{new Date(s.created_at).toLocaleString()}</span>
                <span className="session-history-count">{s.message_count} messages</span>
              </button>
              <button
                className="session-history-hide-button"
                onClick={() => onHide(s.id).then(refreshHidden)}
                title="Hide this conversation"
                aria-label="Hide this conversation"
              >
                🙈
              </button>
            </li>
          ))}
        </ul>
      )}
      {hidden.length > 0 && (
        <div className="hidden-panel">
          <button className="hidden-panel-toggle" onClick={() => setShowHidden((v) => !v)}>
            {showHidden ? "▾" : "▸"} {hidden.length} hidden conversation{hidden.length === 1 ? "" : "s"}
          </button>
          {showHidden && (
            <ul className="hidden-panel-list">
              {hidden.map((s) => (
                <li key={s.id}>
                  <span>{new Date(s.created_at).toLocaleString()}</span>
                  <button onClick={() => setUnlocking(s)}>Unhide</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {unlocking && (
        <PinModal
          title="Unhide this conversation?"
          onCancel={() => setUnlocking(null)}
          onSubmit={async (pin) => {
            await unhideSession(unlocking.id, pin);
            setUnlocking(null);
            refreshHidden();
            onUnhidden?.();
          }}
        />
      )}
    </div>
  );
}
