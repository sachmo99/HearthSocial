import { forwardRef } from "react";
import MessageBubble from "./MessageBubble";

const MessageList = forwardRef(function MessageList({ messages, characterName, sending }, bottomRef) {
  return (
    <div className="chat-messages">
      {messages.map((m, i) => (
        <MessageBubble
          key={i}
          message={m}
          characterName={characterName}
          isPending={sending && i === messages.length - 1}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
});

export default MessageList;
