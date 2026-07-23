import { useState } from "react";
import ThinkingBlock from "./ThinkingBlock";
import TypingIndicator from "./TypingIndicator";
import FormattedMessage from "./FormattedMessage";
import { portraitImageSrc, portraitStyle, initial } from "../theme";

function CharacterAvatar({ name }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="message-avatar message-avatar-fallback" style={portraitStyle(name)}>
        {initial(name)}
      </div>
    );
  }
  return (
    <img
      className="message-avatar"
      src={portraitImageSrc(name)}
      alt={name}
      onError={() => setFailed(true)}
    />
  );
}

function UserAvatar() {
  return <div className="message-avatar message-avatar-user">🧑</div>;
}

export default function MessageBubble({ message, characterName, isPending, showRegenerate, onRegenerate }) {
  const label = message.role === "user" ? "You" : characterName;
  const isWaiting = isPending && !message.content && !message.reasoning;
  const isUser = message.role === "user";
  return (
    <div className={`chat-bubble-row chat-bubble-row-${message.role}`}>
      {!isUser && <CharacterAvatar name={characterName} />}
      <div className="chat-bubble-column">
        <div className={`chat-bubble chat-bubble-${message.role}`}>
          <div className="chat-bubble-label">{label}</div>
          {message.reasoning && <ThinkingBlock text={message.reasoning} />}
          {isWaiting ? (
            <TypingIndicator />
          ) : (
            <div className="chat-bubble-text">
              <FormattedMessage text={message.content} />
            </div>
          )}
        </div>
        {showRegenerate && (
          <button className="regenerate-button" onClick={onRegenerate}>
            🔄 Regenerate
          </button>
        )}
      </div>
      {isUser && <UserAvatar />}
    </div>
  );
}
