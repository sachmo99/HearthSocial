import CharacterCard from "./CharacterCard";
import NewCharacterTile from "./NewCharacterTile";

export default function CharacterGrid({ characters, onSelect, onNew, onEdit, onHide }) {
  return (
    <div className="roster">
      <div className="section-eyebrow">
        <span>All characters</span>
        <div className="section-eyebrow-line" />
      </div>
      <div className="character-grid">
        {characters.map((c) => (
          <CharacterCard key={c.id} character={c} onSelect={onSelect} onEdit={onEdit} onHide={onHide} />
        ))}
        <NewCharacterTile onClick={onNew} />
      </div>
    </div>
  );
}
