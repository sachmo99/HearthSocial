import { useState } from "react";

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  directorNote,
  onDirectorNoteChange,
  onSuggestReply,
}) {
  const [showNudge, setShowNudge] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState(null);

  const handleSuggest = async () => {
    setSuggesting(true);
    setSuggestError(null);
    try {
      const { suggestion } = await onSuggestReply();
      onChange(suggestion);
    } catch (err) {
      setSuggestError(err.message || "Could not suggest a reply.");
    } finally {
      setSuggesting(false);
    }
  };

  const isEmpty = !value.trim() && !directorNote.trim();

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
      {suggestError && <div className="suggest-reply-error">{suggestError}</div>}
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
        {isEmpty && (
          <button
            type="button"
            className="suggest-reply-button"
            onClick={handleSuggest}
            disabled={disabled || suggesting}
            title="Suggest how you might reply, based on the last few messages"
          >
            {suggesting ? "…" : "💡 Suggest"}
          </button>
        )}
        <button type="submit" disabled={disabled}>
          Send
        </button>
      </div>
    </form>
  );
}
