export default function LoadingOverlay({ label }) {
  return (
    <div className="loading-overlay">
      <div className="spinner" />
      {label && <p className="loading-label">{label}</p>}
    </div>
  );
}
