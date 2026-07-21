import { useState } from "react";
import Modal from "./Modal";

const RANGES = {
  temperature: { min: 0.1, max: 1.5, step: 0.05, label: "Temperature" },
  top_p: { min: 0.1, max: 1.0, step: 0.01, label: "Top P" },
  top_k: { min: 1, max: 100, step: 1, label: "Top K" },
  min_p: { min: 0.0, max: 0.2, step: 0.01, label: "Min P" },
};

export default function ChatSettings({ initial, onApply, onReset, onClose }) {
  const [values, setValues] = useState(initial);

  const update = (field) => (e) => {
    setValues({ ...values, [field]: Number(e.target.value) });
  };

  return (
    <Modal>
      <div className="chat-settings">
        <div className="chat-settings-header">
          <h3>Response Parameters</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {Object.entries(RANGES).map(([field, range]) => (
          <label key={field}>
            {range.label} ({values[field]})
            <input
              type="range"
              min={range.min}
              max={range.max}
              step={range.step}
              value={values[field]}
              onChange={update(field)}
            />
          </label>
        ))}
        <div className="character-form-actions">
          <button onClick={() => onApply(values)}>Apply</button>
          <button onClick={onReset}>Reset to Character Defaults</button>
        </div>
      </div>
    </Modal>
  );
}
