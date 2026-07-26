import { useState } from "react";
import ThinkingBlock from "./ThinkingBlock";
import TypingIndicator from "./TypingIndicator";
import FormattedMessage from "./FormattedMessage";
import ImageLightbox from "./ImageLightbox";
import { generateMessageImage } from "../api";
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

function MessageImage({ message, imageGenEnabled, onImageGenerated }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const canGenerate = imageGenEnabled && message.id;
  if (!message.image_path && !canGenerate) return null;

  const handleClick = async () => {
    setGenerating(true);
    setError(null);
    try {
      const { image_path } = await generateMessageImage(message.id);
      onImageGenerated(message.id, image_path);
    } catch (err) {
      setError(err.message || "Image generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      {message.image_path && (
        <details className="chat-reasoning" open>
          <summary>Generated image</summary>
          <img
            className="message-image message-image-clickable"
            src={message.image_path}
            alt="Generated scene"
            onClick={() => setExpanded(true)}
          />
          {expanded && <ImageLightbox name="Generated scene" src={message.image_path} onClose={() => setExpanded(false)} />}
        </details>
      )}
      {canGenerate && (
        <div className="message-image-action">
          <button className="message-image-button" onClick={handleClick} disabled={generating}>
            {generating ? "Generating…" : message.image_path ? "🔄 Regenerate image" : "🖼️ Generate image"}
          </button>
          {error && <span className="message-image-error">{error}</span>}
        </div>
      )}
    </>
  );
}

export default function MessageBubble({
  message,
  characterName,
  isPending,
  showRegenerate,
  onRegenerate,
  imageGenEnabled,
  onImageGenerated,
}) {
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
        {!isUser && !isPending && (
          <MessageImage message={message} imageGenEnabled={imageGenEnabled} onImageGenerated={onImageGenerated} />
        )}
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
