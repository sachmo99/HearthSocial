export default function ThinkingBlock({ text }) {
  return (
    <details className="chat-reasoning">
      <summary>Thinking</summary>
      <div className="chat-reasoning-text">{text}</div>
    </details>
  );
}
