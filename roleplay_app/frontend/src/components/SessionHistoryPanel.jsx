export default function SessionHistoryPanel({ sessions, onSelect, onClose }) {
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
            <li key={s.id}>
              <button className="session-history-item" onClick={() => onSelect(s.id)}>
                <span className="session-history-date">{new Date(s.created_at).toLocaleString()}</span>
                <span className="session-history-count">{s.message_count} messages</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
