import { forwardRef } from "react";
import MessageBubble from "./MessageBubble";
import DirectorNoteDivider from "./DirectorNoteDivider";

const MessageList = forwardRef(function MessageList(
  { messages, characterName, sending, canRegenerate, onRegenerate, imageGenEnabled, onImageGenerated },
  bottomRef
) {
  return (
    <div className="chat-messages">
      {messages.map((m, i) => {
        const isLast = i === messages.length - 1;
        if (m.role === "hidden_trigger") {
          return <DirectorNoteDivider key={i} text={m.content} />;
        }
        return (
          <MessageBubble
            key={i}
            message={m}
            characterName={characterName}
            isPending={sending && isLast}
            showRegenerate={canRegenerate && isLast && !sending}
            onRegenerate={onRegenerate}
            imageGenEnabled={imageGenEnabled}
            onImageGenerated={onImageGenerated}
          />
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
});

export default MessageList;
