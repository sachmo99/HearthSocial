import { portraitStyle, initial } from "../theme";

export default function CharacterCard({ character, onSelect, onEdit }) {
  return (
    <div className="character-card">
      <button className="character-tile" onClick={() => onSelect(character)}>
        <div className="character-portrait" style={portraitStyle(character.name)}>
          <span>{initial(character.name)}</span>
        </div>
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
