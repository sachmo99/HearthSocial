import { useEffect, useState } from "react";
import { listHiddenCharacters, unhideCharacter } from "../api";
import PinModal from "./PinModal";

export default function HiddenCharactersPanel({ onUnhidden }) {
  const [hidden, setHidden] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const [unlocking, setUnlocking] = useState(null);

  const refresh = () => listHiddenCharacters().then(setHidden);

  useEffect(() => {
    refresh();
  }, []);

  if (hidden.length === 0) return null;

  return (
    <div className="hidden-panel">
      <button className="hidden-panel-toggle" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "▾" : "▸"} {hidden.length} hidden character{hidden.length === 1 ? "" : "s"}
      </button>
      {expanded && (
        <ul className="hidden-panel-list">
          {hidden.map((c) => (
            <li key={c.id}>
              <span>{c.name}</span>
              <button onClick={() => setUnlocking(c)}>Unhide</button>
            </li>
          ))}
        </ul>
      )}
      {unlocking && (
        <PinModal
          title={`Unhide ${unlocking.name}?`}
          onCancel={() => setUnlocking(null)}
          onSubmit={async (pin) => {
            await unhideCharacter(unlocking.id, pin);
            setUnlocking(null);
            refresh();
            onUnhidden?.();
          }}
        />
      )}
    </div>
  );
}
