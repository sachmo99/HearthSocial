import CharacterCard from "./CharacterCard";
import NewCharacterTile from "./NewCharacterTile";

export default function CharacterGrid({ characters, onSelect, onNew, onEdit }) {
  return (
    <div className="character-grid">
      {characters.map((c) => (
        <CharacterCard key={c.id} character={c} onSelect={onSelect} onEdit={onEdit} />
      ))}
      <NewCharacterTile onClick={onNew} />
    </div>
  );
}
