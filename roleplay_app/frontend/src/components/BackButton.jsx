export default function BackButton({ onClick, children }) {
  return (
    <button className="back-button" onClick={onClick}>
      {children}
    </button>
  );
}
