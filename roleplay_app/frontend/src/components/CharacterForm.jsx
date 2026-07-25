import { useState } from "react";
import AvatarCropModal from "./AvatarCropModal";
import { portraitImageSrc } from "../theme";
import { useStages } from "../useStages";

const DEFAULT_FORM = {
  name: "",
  persona: "",
  opening_trigger_template: "",
  sampling_preset: "balanced",
  character_appearance: "",
  default_location: "",
  character_affection: 20,
  character_closeness: 10,
  relationship_stage: "stranger",
};

export default function CharacterForm({ initial, onSubmit, onCancel }) {
  const stages = useStages();
  const [form, setForm] = useState(initial || DEFAULT_FORM);
  const [cropSrc, setCropSrc] = useState(null);
  const [avatarBlob, setAvatarBlob] = useState(null);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState(null);
  const [existingAvatarFailed, setExistingAvatarFailed] = useState(false);
  const [avatarError, setAvatarError] = useState(null);

  const update = (field) => (e) => {
    const value = e.target.type === "range" ? Number(e.target.value) : e.target.value;
    setForm({ ...form, [field]: value });
  };

  const pickAvatarFile = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    if (file.type !== "image/jpeg" && file.type !== "image/png") {
      setAvatarError("Avatar must be a JPG or PNG image");
      return;
    }
    setAvatarError(null);
    const reader = new FileReader();
    reader.onload = () => setCropSrc(reader.result);
    reader.readAsDataURL(file);
  };

  const confirmCrop = (blob) => {
    if (avatarPreviewUrl) URL.revokeObjectURL(avatarPreviewUrl);
    setAvatarBlob(blob);
    setAvatarPreviewUrl(URL.createObjectURL(blob));
    setCropSrc(null);
  };

  const submit = (e) => {
    e.preventDefault();
    onSubmit(form, avatarBlob);
  };

  return (
    <form className="character-form" onSubmit={submit}>
      <h3>{initial ? "Edit Character" : "New Character"}</h3>
      <label>
        Avatar
        <div className="avatar-picker">
          {avatarPreviewUrl ? (
            <img className="avatar-picker-preview" src={avatarPreviewUrl} alt="Avatar preview" />
          ) : form.name && !existingAvatarFailed ? (
            <img
              className="avatar-picker-preview"
              src={portraitImageSrc(form.name)}
              alt="Current avatar"
              onError={() => setExistingAvatarFailed(true)}
            />
          ) : (
            <div className="avatar-picker-placeholder">No avatar yet</div>
          )}
          <input type="file" accept="image/png,image/jpeg" onChange={pickAvatarFile} />
          {avatarError && <div className="avatar-picker-error">{avatarError}</div>}
        </div>
      </label>
      <label>
        Name
        <input value={form.name} onChange={update("name")} required />
      </label>
      <label>
        Persona
        <textarea value={form.persona} onChange={update("persona")} rows={4} required />
      </label>
      <label>
        Opening scene instruction
        <textarea value={form.opening_trigger_template} onChange={update("opening_trigger_template")} rows={3} required />
      </label>
      <label>
        Appearance
        <input value={form.character_appearance} onChange={update("character_appearance")} />
      </label>
      <label>
        Starting location
        <input value={form.default_location} onChange={update("default_location")} />
      </label>
      <label>
        Personality preset
        <select value={form.sampling_preset} onChange={update("sampling_preset")}>
          <option value="calm">Calm</option>
          <option value="balanced">Balanced</option>
          <option value="chaotic">Chaotic</option>
        </select>
      </label>
      <label>
        Starting affection ({form.character_affection})
        <input
          type="range"
          min="0"
          max="100"
          value={form.character_affection}
          onChange={update("character_affection")}
          style={{ background: `linear-gradient(to right, var(--accent) ${form.character_affection}%, oklch(0.32 0.04 255) ${form.character_affection}%)` }}
        />
      </label>
      <label>
        Starting closeness ({form.character_closeness})
        <input
          type="range"
          min="0"
          max="100"
          value={form.character_closeness}
          onChange={update("character_closeness")}
          style={{ background: `linear-gradient(to right, var(--accent) ${form.character_closeness}%, oklch(0.32 0.04 255) ${form.character_closeness}%)` }}
        />
      </label>
      <label>
        Starting relationship stage
        <select value={form.relationship_stage} onChange={update("relationship_stage")}>
          {stages.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      <div className="character-form-actions">
        <button type="submit">Save</button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {cropSrc && (
        <AvatarCropModal imageSrc={cropSrc} onCancel={() => setCropSrc(null)} onConfirm={confirmCrop} />
      )}
    </form>
  );
}
