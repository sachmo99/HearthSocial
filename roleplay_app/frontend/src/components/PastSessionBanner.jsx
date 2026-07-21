import { portraitStyle } from "../theme";

export default function PastSessionBanner({ character, onBack, onToggleHistory }) {
  return (
    <div className="chat-banner" style={portraitStyle(character.name)}>
      <div className="chat-banner-overlay">
        <span className="chat-banner-name">{character.name} — Past Conversation</span>
        <div className="chat-banner-actions">
          <button className="clear-button" onClick={onToggleHistory}>
            📜 History
          </button>
          <button className="clear-button" onClick={onBack}>
            ← Back to Current Chat
          </button>
        </div>
      </div>
    </div>
  );
}
