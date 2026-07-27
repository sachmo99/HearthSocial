import { useCallback, useState } from "react";
import Cropper from "react-easy-crop";
import Modal from "./Modal";

// Fixed output size regardless of source resolution. 500x500 looked soft once scaled
// up on high-DPI displays, so this renders at 1000x1000 (matching the 1:1 crop aspect)
// for real headroom at 2-3x pixel density, while still keeping uploads reasonably small.
const OUTPUT_WIDTH = 1000;
const OUTPUT_HEIGHT = 1000;

async function getCroppedBlob(imageSrc, cropPixels) {
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = imageSrc;
  });
  const canvas = document.createElement("canvas");
  canvas.width = OUTPUT_WIDTH;
  canvas.height = OUTPUT_HEIGHT;
  const ctx = canvas.getContext("2d");
  // JPEG has no alpha channel; fill white first so any transparent source pixels
  // don't turn black on export.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT);
  ctx.drawImage(
    image,
    cropPixels.x,
    cropPixels.y,
    cropPixels.width,
    cropPixels.height,
    0,
    0,
    OUTPUT_WIDTH,
    OUTPUT_HEIGHT
  );
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
}

export default function AvatarCropModal({ imageSrc, onCancel, onConfirm }) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);

  const onCropComplete = useCallback((_, pixels) => setCroppedAreaPixels(pixels), []);

  const confirm = async () => {
    const blob = await getCroppedBlob(imageSrc, croppedAreaPixels);
    onConfirm(blob);
  };

  return (
    <Modal>
      <div className="avatar-crop">
        <h3>Crop avatar</h3>
        <div className="avatar-crop-stage">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={1}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={onCropComplete}
          />
        </div>
        <label className="avatar-crop-zoom">
          Zoom
          <input
            type="range"
            min={1}
            max={3}
            step={0.01}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        <div className="avatar-crop-actions">
          <button type="button" onClick={confirm} disabled={!croppedAreaPixels}>
            Use this crop
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
