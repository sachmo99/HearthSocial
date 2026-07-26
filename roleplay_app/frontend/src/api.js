const API_BASE = "";

async function json(method, path, body, timeoutMs = 15000) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${method} ${path} failed (${res.status})`);
  }
  return res.json();
}

export const getStages = () => json("GET", "/api/stages");
export const getHealth = () => json("GET", "/api/health");

export const getCharacters = () => json("GET", "/api/characters");
export const getCharacter = (id) => json("GET", `/api/characters/${id}`);
export const createCharacter = (card) => json("POST", "/api/characters", card);
export const updateCharacter = (id, card) => json("PUT", `/api/characters/${id}`, card);
export const deleteCharacter = (id) => json("DELETE", `/api/characters/${id}`);
// Generates the opening scene server-side (llama_client's default 120s timeout), so this
// needs more headroom than a plain CRUD call.
export const startCharacter = (id) => json("POST", `/api/characters/${id}/start`, undefined, 125000);
export const clearChat = (id) => json("POST", `/api/characters/${id}/clear`);
export const listSessions = (characterId) => json("GET", `/api/characters/${characterId}/sessions`);
export const getMessages = (sessionId) => json("GET", `/api/sessions/${sessionId}/messages`);
export const getSessionState = (sessionId) => json("GET", `/api/sessions/${sessionId}/state`);
export const getSessionDebug = (sessionId) => json("GET", `/api/sessions/${sessionId}/debug`);

export const hideCharacter = (id) => json("POST", `/api/characters/${id}/hide`);
export const listHiddenCharacters = () => json("GET", "/api/hidden/characters");
export const unhideCharacter = (id, pin) => json("POST", `/api/hidden/characters/${id}/unhide`, { pin });

export const hideSession = (sessionId) => json("POST", `/api/sessions/${sessionId}/hide`);
export const listHiddenSessions = (characterId) => json("GET", `/api/hidden/sessions/${characterId}`);
export const unhideSession = (sessionId, pin) => json("POST", `/api/hidden/sessions/${sessionId}/unhide`, { pin });

// Post/react generation queues behind any in-flight chat turn on the single inference slot,
// so these need the same generous timeout as the backend's own llama_client call (300s).
const FEED_GENERATION_TIMEOUT_MS = 305000;

export const getFeed = () => json("GET", "/api/feed");
export const createFeedPost = (characterId) =>
  json("POST", "/api/feed/posts", { character_id: characterId }, FEED_GENERATION_TIMEOUT_MS);
export const reactToFeedPost = (postId, characterId) =>
  json("POST", `/api/feed/posts/${postId}/react`, { character_id: characterId }, FEED_GENERATION_TIMEOUT_MS);
export const commentOnFeedPost = (postId, content) => json("POST", `/api/feed/posts/${postId}/comments`, { content });

export async function uploadAvatar(name, blob) {
  const body = new FormData();
  body.append("name", name);
  body.append("file", blob, "avatar.jpg");
  const res = await fetch(`${API_BASE}/api/avatar`, { method: "POST", body });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `avatar upload failed (${res.status})`);
  }
  return res.json();
}

async function* consumeSSEStream(res) {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (!chunk.startsWith("data:")) continue;
      const dataStr = chunk.slice(5).trim();
      if (dataStr === "[DONE]" || !dataStr) continue;
      const parsed = JSON.parse(dataStr);
      if (parsed.delta) yield parsed;
    }
  }
}

export async function* streamChat(sessionId, message, directorNote, overrides, signal) {
  const res = await fetch(`${API_BASE}/api/chat/${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, director_note: directorNote || null, ...(overrides || {}) }),
    signal,
  });
  yield* consumeSSEStream(res);
}

export async function* regenerateResponse(sessionId, overrides, signal) {
  const res = await fetch(`${API_BASE}/api/chat/${sessionId}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(overrides || {}),
    signal,
  });
  yield* consumeSSEStream(res);
}
