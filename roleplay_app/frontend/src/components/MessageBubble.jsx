import ThinkingBlock from "./ThinkingBlock";
import TypingIndicator from "./TypingIndicator";
import FormattedMessage from "./FormattedMessage";

export default function MessageBubble({ message, characterName, isPending, showRegenerate, onRegenerate }) {
  const label = message.role === "user" ? "You" : characterName;
  const isWaiting = isPending && !message.content && !message.reasoning;
  return (
    <div className={`chat-bubble-row chat-bubble-row-${message.role}`}>
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
    </div>
  );
}
