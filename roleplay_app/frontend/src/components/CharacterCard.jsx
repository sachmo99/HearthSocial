import { useState } from "react";
import { portraitStyle, initial, portraitImageSrc } from "../theme";

export default function CharacterCard({ character, onSelect, onEdit }) {
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <div className="character-card">
      <button className="character-tile" onClick={() => onSelect(character)}>
        {imageFailed ? (
          <div className="character-portrait" style={portraitStyle(character.name)}>
            <span>{initial(character.name)}</span>
          </div>
        ) : (
          <img
            className="character-portrait character-portrait-image"
            src={portraitImageSrc(character.name)}
            alt={character.name}
            onError={() => setImageFailed(true)}
          />
        )}
        <div className="character-tile-name">{character.name}</div>
      </button>
      <button
        className="character-edit-button"
        onClick={(e) => {
          e.stopPropagation();
          onEdit(character);
        }}
        aria-label={`Edit ${character.name}`}
        title="Edit character"
      >
        ✎
      </button>
    </div>
  );
}
