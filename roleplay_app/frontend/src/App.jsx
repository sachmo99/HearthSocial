import { useEffect, useState } from "react";
import CharacterGrid from "./components/CharacterGrid";
import CharacterForm from "./components/CharacterForm";
import ChatView from "./components/ChatView";
import Modal from "./components/Modal";
import Hero from "./components/Hero";
import FeaturedRow from "./components/FeaturedRow";
import HiddenCharactersPanel from "./components/HiddenCharactersPanel";
import BackButton from "./components/BackButton";
import LoadingOverlay from "./components/LoadingOverlay";
import { getCharacters, getCharacter, createCharacter, updateCharacter, startCharacter, uploadAvatar, hideCharacter } from "./api";
import "./App.css";

export default function App() {
  const [characters, setCharacters] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editInitial, setEditInitial] = useState(null);
  const [active, setActive] = useState(null);
  const [loadingLabel, setLoadingLabel] = useState(null);

  const refresh = () => getCharacters().then(setCharacters);

  useEffect(() => {
    refresh();
  }, []);

  const handleSelect = async (character) => {
    setLoadingLabel(`Entering ${character.name}'s scene…`);
    try {
      const { session_id } = await startCharacter(character.id);
      setActive({ character, sessionId: session_id });
    } finally {
      setLoadingLabel(null);
    }
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

  const handleSubmitForm = async (form, avatarBlob) => {
    if (editingId) {
      await updateCharacter(editingId, form);
    } else {
      await createCharacter(form);
    }
    if (avatarBlob) {
      await uploadAvatar(form.name, avatarBlob);
    }
    setShowForm(false);
    refresh();
  };

  const handleHideCharacter = async (character) => {
    await hideCharacter(character.id);
    refresh();
  };

  const handleSessionReset = async () => {
    setLoadingLabel(`Setting a new scene with ${active.character.name}…`);
    try {
      const { session_id } = await startCharacter(active.character.id);
      setActive({ character: active.character, sessionId: session_id });
    } finally {
      setLoadingLabel(null);
    }
  };

  return (
    <>
      {loadingLabel && <LoadingOverlay label={loadingLabel} />}
      {active ? (
        <div className="app app-chat">
          <BackButton onClick={() => setActive(null)}>&larr; Back to characters</BackButton>
          <ChatView character={active.character} sessionId={active.sessionId} onSessionReset={handleSessionReset} />
        </div>
      ) : (
        <div className="app app-home">
          <Hero />
          <FeaturedRow characters={characters} onSelect={handleSelect} />
          <CharacterGrid
            characters={characters}
            onSelect={handleSelect}
            onNew={handleNew}
            onEdit={handleEdit}
            onHide={handleHideCharacter}
          />
          <HiddenCharactersPanel onUnhidden={refresh} />
          {showForm && (
            <Modal>
              <CharacterForm initial={editInitial} onSubmit={handleSubmitForm} onCancel={() => setShowForm(false)} />
            </Modal>
          )}
        </div>
      )}
    </>
  );
}
