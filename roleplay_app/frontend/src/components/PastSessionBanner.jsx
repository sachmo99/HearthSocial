import { portraitStyle } from "../theme";
import ChatBannerAvatar from "./ChatBannerAvatar";

export default function PastSessionBanner({ character, onBack, onToggleHistory }) {
  return (
    <div className="chat-banner" style={portraitStyle(character.name)}>
      <div className="chat-banner-overlay">
        <div className="chat-banner-identity">
          <ChatBannerAvatar name={character.name} />
          <span className="chat-banner-name">{character.name} — Past Conversation</span>
        </div>
        <div className="chat-banner-actions">
          <button className="banner-icon-button" onClick={onToggleHistory} title="Past conversations" aria-label="Past conversations">
            ☰
          </button>
          <button className="banner-text-button" onClick={onBack}>
            ← Back to current chat
          </button>
        </div>
      </div>
    </div>
  );
}
