import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ChatView from "./ChatView";
import BackButton from "./BackButton";
import LoadingOverlay from "./LoadingOverlay";
import { getCharacter, startCharacter } from "../api";
import { portraitImageSrc } from "../theme";

export default function ChatPage() {
  const { characterId } = useParams();
  const navigate = useNavigate();
  const [character, setCharacter] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [loadingLabel, setLoadingLabel] = useState("Entering the scene…");

  useEffect(() => {
    let cancelled = false;
    setCharacter(null);
    setSessionId(null);
    (async () => {
      try {
        const full = await getCharacter(characterId);
        const resolved = { ...full, id: characterId };
        setLoadingLabel(`Entering ${resolved.name}'s scene…`);
        const { session_id } = await startCharacter(characterId);
        if (cancelled) return;
        setCharacter(resolved);
        setSessionId(session_id);
      } catch {
        if (!cancelled) navigate("/", { replace: true });
      } finally {
        if (!cancelled) setLoadingLabel(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [characterId]);

  // Swap the browser tab icon to the character's portrait while chatting, restoring
  // the default favicon on leaving the page.
  useEffect(() => {
    if (!character) return;
    const link = document.querySelector('link[rel="icon"]');
    if (!link) return;
    const prevHref = link.href;
    const prevType = link.type;
    link.href = portraitImageSrc(character.name);
    link.type = "";
    return () => {
      link.href = prevHref;
      link.type = prevType;
    };
  }, [character]);

  const handleSessionReset = async () => {
    setLoadingLabel(`Setting a new scene with ${character.name}…`);
    try {
      const { session_id } = await startCharacter(characterId);
      setSessionId(session_id);
    } finally {
      setLoadingLabel(null);
    }
  };

  return (
    <div className="app app-chat">
      {loadingLabel && <LoadingOverlay label={loadingLabel} />}
      <BackButton onClick={() => navigate("/")}>&larr; Back to characters</BackButton>
      {character && sessionId && (
        <ChatView character={character} sessionId={sessionId} onSessionReset={handleSessionReset} />
      )}
    </div>
  );
}
