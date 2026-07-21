import { useEffect, useRef, useState } from "react";
import { getMessages, getSessionState, streamChat, regenerateResponse, clearChat, listSessions } from "../api";
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
  const [sending, setSending] = useState(false);
  const [sessionState, setSessionState] = useState(null);
  const [overrides, setOverrides] = useState(null);
  const [showSettings, setShowSettings] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [viewing, setViewing] = useState(null);
  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);

  const refreshSessions = () => listSessions(character.id).then(setSessions);

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
    const interval = setInterval(refreshState, 3000);
    return () => clearInterval(interval);
  }, [sessionId, viewing]);

  const consumeStream = async (streamGenerator) => {
    for await (const chunk of streamGenerator) {
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
  };

  const send = async () => {
    if (!input.trim() || sending) return;
    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage, { role: "assistant", content: "", reasoning: "" }]);
    setInput("");
    setSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      await consumeStream(streamChat(sessionId, userMessage.content, overrides, controller.signal));
    } catch (err) {
      if (err.name !== "AbortError") throw err;
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
      await consumeStream(regenerateResponse(sessionId, overrides, controller.signal));
    } catch (err) {
      if (err.name !== "AbortError") throw err;
    } finally {
      setSending(false);
      refreshState();
    }
  };

  const handleClear = async () => {
    await clearChat(character.id);
    onSessionReset();
  };

  const handleViewSession = async (id) => {
    const [msgs, state] = await Promise.all([getMessages(id), getSessionState(id)]);
    setViewing({ id, messages: msgs, state });
    setHistoryOpen(false);
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
        />
      )}

      {viewing ? <ChatStatsBar state={viewing.state} /> : sessionState && <ChatStatsBar state={sessionState} />}

      <MessageList
        ref={viewing ? undefined : bottomRef}
        messages={viewing ? viewing.messages : messages}
        characterName={character.name}
        sending={!viewing && sending}
        canRegenerate={!viewing}
        onRegenerate={regenerate}
      />

      {!viewing && <ChatInput value={input} onChange={setInput} onSubmit={send} disabled={sending} />}
      {!viewing && <DebugPanel sessionId={sessionId} />}

      {historyOpen && (
        <SessionHistoryPanel sessions={pastSessions} onSelect={handleViewSession} onClose={() => setHistoryOpen(false)} />
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
