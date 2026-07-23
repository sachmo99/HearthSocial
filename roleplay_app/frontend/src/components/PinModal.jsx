import { useState } from "react";
import Modal from "./Modal";

export default function PinModal({ title, onSubmit, onCancel }) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await onSubmit(pin);
    } catch (err) {
      setError(err.message || "Incorrect PIN");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal>
      <form className="pin-modal" onSubmit={submit}>
        <h3>{title || "Enter PIN"}</h3>
        <input
          type="password"
          inputMode="numeric"
          autoFocus
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="PIN"
        />
        {error && <p className="pin-modal-error">{error}</p>}
        <div className="character-form-actions">
          <button type="submit" disabled={submitting || !pin}>
            Unlock
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
