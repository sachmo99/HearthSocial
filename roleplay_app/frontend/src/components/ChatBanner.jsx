import { portraitStyle } from "../theme";

export default function ChatBanner({ character, onOpenSettings, onClear, onToggleHistory }) {
  return (
    <div className="chat-banner" style={portraitStyle(character.name)}>
      <div className="chat-banner-overlay">
        <span className="chat-banner-name">{character.name}</span>
        <div className="chat-banner-actions">
          <button className="clear-button" onClick={onToggleHistory}>
            📜 History
          </button>
          <button className="clear-button" onClick={onOpenSettings}>
            ⚙ Settings
          </button>
          <button className="clear-button" onClick={onClear}>
            Clear Chat
          </button>
        </div>
      </div>
    </div>
  );
}
