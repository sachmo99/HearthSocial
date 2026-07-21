const API_BASE = "http://127.0.0.1:8000";

async function json(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${method} ${path} failed (${res.status})`);
  }
  return res.json();
}

export const getCharacters = () => json("GET", "/api/characters");
export const getCharacter = (id) => json("GET", `/api/characters/${id}`);
export const createCharacter = (card) => json("POST", "/api/characters", card);
export const updateCharacter = (id, card) => json("PUT", `/api/characters/${id}`, card);
export const deleteCharacter = (id) => json("DELETE", `/api/characters/${id}`);
export const startCharacter = (id) => json("POST", `/api/characters/${id}/start`);
export const clearChat = (id) => json("POST", `/api/characters/${id}/clear`);
export const listSessions = (characterId) => json("GET", `/api/characters/${characterId}/sessions`);
export const getMessages = (sessionId) => json("GET", `/api/sessions/${sessionId}/messages`);
export const getSessionState = (sessionId) => json("GET", `/api/sessions/${sessionId}/state`);

export async function* streamChat(sessionId, message, overrides) {
  const res = await fetch(`${API_BASE}/api/chat/${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, ...(overrides || {}) }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `chat failed (${res.status})`);
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
