import { useState } from "react";

export default function ChatInput({ value, onChange, onSubmit, disabled, directorNote, onDirectorNoteChange }) {
  const [showNudge, setShowNudge] = useState(false);

  return (
    <form
      className="chat-input"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {showNudge && (
        <input
          className="chat-input-nudge"
          value={directorNote}
          onChange={(e) => onDirectorNoteChange(e.target.value)}
          placeholder="Director's note (e.g. an unexpected visitor arrives)..."
          disabled={disabled}
        />
      )}
      <div className="chat-input-row">
        <button
          type="button"
          className={`chat-input-nudge-toggle${directorNote ? " chat-input-nudge-toggle-active" : ""}`}
          onClick={() => setShowNudge((v) => !v)}
          title="Nudge the scene without speaking as your character"
        >
          🎬
        </button>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Say something..."
          disabled={disabled}
        />
        <button type="submit" disabled={disabled}>
          Send
        </button>
      </div>
    </form>
  );
}
