export default function DirectorNoteDivider({ text }) {
  return (
    <div className="director-note-divider">
      <span className="director-note-line" />
      <span className="director-note-text">🎬 {text}</span>
      <span className="director-note-line" />
    </div>
  );
}
