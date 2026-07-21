export default function NewCharacterTile({ onClick }) {
  return (
    <button className="character-tile character-tile-new" onClick={onClick}>
      <div className="character-portrait character-portrait-new">
        <span>+</span>
      </div>
      <div className="character-tile-name">New Character</div>
    </button>
  );
}
