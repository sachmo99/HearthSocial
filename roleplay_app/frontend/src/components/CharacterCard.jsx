import { useState } from "react";
import { portraitStyle, initial, portraitImageSrc, portraitImageSrcSet } from "../theme";
import EyeOffIcon from "./EyeOffIcon";

export default function CharacterCard({ character, onSelect, onEdit, onHide }) {
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
            srcSet={portraitImageSrcSet(character.name)}
            alt={character.name}
            onError={() => setImageFailed(true)}
          />
        )}
        <div className="character-tile-name">{character.name}</div>
      </button>
      <button
        className="character-hide-button"
        onClick={(e) => {
          e.stopPropagation();
          onHide(character);
        }}
        aria-label={`Hide ${character.name}`}
        title="Hide character"
      >
        <EyeOffIcon />
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
