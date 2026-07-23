import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import CharacterGrid from "./CharacterGrid";
import CharacterForm from "./CharacterForm";
import Modal from "./Modal";
import Hero from "./Hero";
import FeaturedRow from "./FeaturedRow";
import HiddenCharactersPanel from "./HiddenCharactersPanel";
import { getCharacters, getCharacter, createCharacter, updateCharacter, uploadAvatar, hideCharacter } from "../api";

export default function HomePage() {
  const [characters, setCharacters] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editInitial, setEditInitial] = useState(null);
  const navigate = useNavigate();

  const refresh = () => getCharacters().then(setCharacters);

  useEffect(() => {
    refresh();
  }, []);

  const handleSelect = (character) => {
    navigate(`/chat/${character.id}`);
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

  return (
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
  );
}
