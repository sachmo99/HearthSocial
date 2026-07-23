import { portraitStyle } from "../theme";

export default function ChatBanner({ character, onOpenSettings, onClear, onToggleHistory }) {
  return (
    <div className="chat-banner" style={portraitStyle(character.name)}>
      <div className="chat-banner-overlay">
        <span className="chat-banner-name">{character.name}</span>
        <div className="chat-banner-actions">
          <button className="banner-icon-button" onClick={onToggleHistory} title="Past conversations" aria-label="Past conversations">
            ☰
          </button>
          <button className="banner-icon-button" onClick={onOpenSettings} title="Response parameters" aria-label="Response parameters">
            ⚙
          </button>
          <button className="banner-icon-button" onClick={onClear} title="Clear chat" aria-label="Clear chat">
            🗑
          </button>
        </div>
      </div>
    </div>
  );
}
