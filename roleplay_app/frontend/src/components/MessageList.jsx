import { forwardRef } from "react";
import MessageBubble from "./MessageBubble";

const MessageList = forwardRef(function MessageList(
  { messages, characterName, sending, canRegenerate, onRegenerate },
  bottomRef
) {
  return (
    <div className="chat-messages">
      {messages.map((m, i) => {
        const isLast = i === messages.length - 1;
        return (
          <MessageBubble
            key={i}
            message={m}
            characterName={characterName}
            isPending={sending && isLast}
            showRegenerate={canRegenerate && isLast && !sending}
            onRegenerate={onRegenerate}
          />
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
});

export default MessageList;
