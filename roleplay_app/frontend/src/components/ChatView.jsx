import { useEffect, useRef, useState } from "react";
import { getMessages, getSessionState, getHealth, streamChat, regenerateResponse, clearChat, listSessions, hideSession, suggestReply } from "../api";
import ChatBanner from "./ChatBanner";
import PastSessionBanner from "./PastSessionBanner";
import ChatStatsBar from "./ChatStatsBar";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import ChatSettings from "./ChatSettings";
import SessionHistoryPanel from "./SessionHistoryPanel";
import DebugPanel from "./DebugPanel";

export default function ChatView({ character, sessionId, onSessionReset }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [directorNote, setDirectorNote] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionState, setSessionState] = useState(null);
  const [overrides, setOverrides] = useState(null);
  const [showSettings, setShowSettings] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [viewing, setViewing] = useState(null);
  const [imageGenEnabled, setImageGenEnabled] = useState(false);
  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);
  const stalledRef = useRef(false);

  const refreshSessions = () => listSessions(character.id).then(setSessions);

  useEffect(() => {
    getHealth().then((h) => setImageGenEnabled(!!h.image_generation)).catch(() => {});
  }, []);

  useEffect(() => {
    getMessages(sessionId).then(setMessages);
    getSessionState(sessionId).then(setSessionState);
    refreshSessions();
    setShowSettings(true);
    setOverrides(null);
    setViewing(null);
    setHistoryOpen(false);
  }, [sessionId]);

  // Abort any in-flight generation for this session when we navigate away from it
  // (switching characters unmounts this component; clearing chat changes sessionId).
  useEffect(() => {
    return () => abortControllerRef.current?.abort();
  }, [sessionId]);

  useEffect(() => {
    if (!viewing) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, viewing]);

  const refreshState = () => getSessionState(sessionId).then(setSessionState);

  useEffect(() => {
    if (viewing) return;
    const interval = setInterval(refreshState, 5000);
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshState();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [sessionId, viewing]);

  const showError = (message) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant" && !last.content) {
        next[next.length - 1] = { ...last, content: `[${message}]` };
      }
      return next;
    });
  };

  const consumeStream = async (streamGenerator, controller) => {
    const stall = () => {
      stalledRef.current = true;
      controller.abort();
    };
    let stallTimer = setTimeout(stall, 60000);
    const resetStallTimer = () => {
      clearTimeout(stallTimer);
      stallTimer = setTimeout(stall, 60000);
    };
    let newMessageId = null;
    try {
      for await (const chunk of streamGenerator) {
        resetStallTimer();
        if (chunk.type === "message_id") {
          newMessageId = chunk.message_id;
          continue;
        }
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] =
            chunk.type === "reasoning"
              ? { ...last, reasoning: (last.reasoning || "") + chunk.delta }
              : { ...last, content: last.content + chunk.delta };
          return next;
        });
      }
    } finally {
      clearTimeout(stallTimer);
    }
    return newMessageId;
  };

  const send = async () => {
    const messageToSend = input.trim();
    const note = directorNote.trim();
    if ((!messageToSend && !note) || sending) return;
    setMessages((prev) => [
      ...prev,
      ...(messageToSend ? [{ role: "user", content: messageToSend }] : []),
      ...(note ? [{ role: "hidden_trigger", content: note }] : []),
      { role: "assistant", content: "", reasoning: "" },
    ]);
    setInput("");
    setDirectorNote("");
    setSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const newMessageId = await consumeStream(
        streamChat(sessionId, messageToSend, note, overrides, controller.signal),
        controller
      );
      if (newMessageId) {
        setMessages((prev) => prev.map((m, i) => (i === prev.length - 1 ? { ...m, id: newMessageId } : m)));
      }
    } catch (err) {
      if (err.name === "AbortError") {
        if (stalledRef.current) showError("Connection stalled - try again");
        stalledRef.current = false;
        return;
      }
      showError(err.message || "Something went wrong.");
    } finally {
      setSending(false);
      refreshState();
    }
  };

  const regenerate = async () => {
    if (sending || messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (last.role === "assistant") {
      setMessages((prev) => [...prev.slice(0, -1), { role: "assistant", content: "", reasoning: "" }]);
    } else {
      setMessages((prev) => [...prev, { role: "assistant", content: "", reasoning: "" }]);
    }
    setSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const newMessageId = await consumeStream(regenerateResponse(sessionId, overrides, controller.signal), controller);
      if (newMessageId) {
        setMessages((prev) => prev.map((m, i) => (i === prev.length - 1 ? { ...m, id: newMessageId } : m)));
      }
    } catch (err) {
      if (err.name === "AbortError") {
        if (stalledRef.current) showError("Connection stalled - try again");
        stalledRef.current = false;
        return;
      }
      showError(err.message || "Something went wrong.");
    } finally {
      setSending(false);
      refreshState();
    }
  };

  const handleClear = async () => {
    await clearChat(character.id);
    onSessionReset();
  };

  const handleDownload = () => {
    const lines = messages.map((m) => {
      if (m.role === "hidden_trigger") return `[Director's note: ${m.content}]`;
      const label = m.role === "user" ? "You" : character.name;
      return `${label}: ${m.content}`;
    });
    const header = `Conversation with ${character.name}\nExported ${new Date().toLocaleString()}\n\n`;
    const blob = new Blob([header + lines.join("\n\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${character.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-conversation.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleViewSession = async (id) => {
    const [msgs, state] = await Promise.all([getMessages(id), getSessionState(id)]);
    setViewing({ id, messages: msgs, state });
    setHistoryOpen(false);
  };

  const handleHideSession = async (id) => {
    await hideSession(id);
    refreshSessions();
  };

  const handleImageGenerated = (messageId, imagePath) => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, image_path: imagePath } : m)));
  };

  const pastSessions = sessions.filter((s) => s.id !== sessionId);

  return (
    <div className="chat-view">
      {viewing ? (
        <PastSessionBanner
          character={character}
          onBack={() => setViewing(null)}
          onToggleHistory={() => setHistoryOpen((v) => !v)}
        />
      ) : (
        <ChatBanner
          character={character}
          onOpenSettings={() => setShowSettings(true)}
          onClear={handleClear}
          onToggleHistory={() => setHistoryOpen((v) => !v)}
          onDownload={handleDownload}
        />
      )}

      {viewing ? (
        <ChatStatsBar state={viewing.state} characterName={character.name} />
      ) : (
        sessionState && (
          <ChatStatsBar state={sessionState} sessionId={sessionId} onRefresh={refreshState} characterName={character.name} />
        )
      )}

      <MessageList
        ref={viewing ? undefined : bottomRef}
        messages={viewing ? viewing.messages : messages}
        characterName={character.name}
        sending={!viewing && sending}
        canRegenerate={!viewing}
        onRegenerate={regenerate}
        imageGenEnabled={!viewing && imageGenEnabled}
        onImageGenerated={handleImageGenerated}
      />

      {!viewing && (
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={send}
          disabled={sending}
          directorNote={directorNote}
          onDirectorNoteChange={setDirectorNote}
          onSuggestReply={() => suggestReply(sessionId)}
        />
      )}
      {!viewing && <DebugPanel sessionId={sessionId} />}

      {historyOpen && (
        <SessionHistoryPanel
          sessions={pastSessions}
          characterId={character.id}
          onSelect={handleViewSession}
          onClose={() => setHistoryOpen(false)}
          onHide={handleHideSession}
          onUnhidden={refreshSessions}
        />
      )}

      {showSettings && sessionState && !viewing && (
        <ChatSettings
          initial={overrides || sessionState.sampling_params}
          onApply={(values) => {
            setOverrides(values);
            setShowSettings(false);
          }}
          onReset={() => {
            setOverrides(null);
            setShowSettings(false);
          }}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
