export default function AvatarLightbox({ name, src, onClose }) {
  return (
    <div className="avatar-lightbox-overlay" onClick={onClose}>
      <img className="avatar-lightbox-img" src={src} alt={name} />
      <button className="avatar-lightbox-close" onClick={onClose} aria-label="Close">
        ✕
      </button>
    </div>
  );
}
