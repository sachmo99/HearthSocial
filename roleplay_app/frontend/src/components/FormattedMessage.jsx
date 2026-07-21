import { parseFormattedText } from "../formatting";

export default function FormattedMessage({ text }) {
  return (
    <>
      {parseFormattedText(text).map((seg, i) => {
        if (seg.type === "action") {
          return (
            <em key={i} className="msg-action">
              {seg.text}
            </em>
          );
        }
        if (seg.type === "monologue") {
          return (
            <span key={i} className="msg-monologue">
              ({seg.text})
            </span>
          );
        }
        return <span key={i}>{seg.text}</span>;
      })}
    </>
  );
}
