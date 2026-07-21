import { useEffect, useState } from "react";
import CharacterGrid from "./components/CharacterGrid";
import CharacterForm from "./components/CharacterForm";
import ChatView from "./components/ChatView";
import Modal from "./components/Modal";
import AppHeader from "./components/AppHeader";
import BackButton from "./components/BackButton";
import { getCharacters, getCharacter, createCharacter, updateCharacter, startCharacter } from "./api";
import "./App.css";

export default function App() {
  const [characters, setCharacters] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editInitial, setEditInitial] = useState(null);
  const [active, setActive] = useState(null);

  const refresh = () => getCharacters().then(setCharacters);

  useEffect(() => {
    refresh();
  }, []);

  const handleSelect = async (character) => {
    const { session_id } = await startCharacter(character.id);
    setActive({ character, sessionId: session_id });
  };

  const handleNew = () => {
    setEditingId(null);
    setEditInitial(null);
    setShowForm(true);
  };

  const handleEdit = async (character) => {
    const full = await getCharacter(character.id);
    setEditingId(character.id);
    setEditInitial(full);
    setShowForm(true);
  };

  const handleSubmitForm = async (form) => {
    if (editingId) {
      await updateCharacter(editingId, form);
    } else {
      await createCharacter(form);
    }
    setShowForm(false);
    refresh();
  };

  const handleSessionReset = async () => {
    const { session_id } = await startCharacter(active.character.id);
    setActive({ character: active.character, sessionId: session_id });
  };

  if (active) {
    return (
      <div className="app">
        <BackButton onClick={() => setActive(null)}>&larr; Back to characters</BackButton>
        <ChatView character={active.character} sessionId={active.sessionId} onSessionReset={handleSessionReset} />
      </div>
    );
  }

  return (
    <div className="app">
      <AppHeader title="Role-Play" />
      <CharacterGrid characters={characters} onSelect={handleSelect} onNew={handleNew} onEdit={handleEdit} />
      {showForm && (
        <Modal>
          <CharacterForm initial={editInitial} onSubmit={handleSubmitForm} onCancel={() => setShowForm(false)} />
        </Modal>
      )}
    </div>
  );
}
