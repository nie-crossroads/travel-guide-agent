const BASE = "/api";

async function parseJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

export function createSession(title) {
  return fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }).then(parseJson);
}

export function listSessions() {
  return fetch(`${BASE}/sessions`).then(parseJson);
}

export function getSessionMessages(sessionId) {
  return fetch(`${BASE}/sessions/${sessionId}/messages`).then(parseJson);
}

export function deleteSession(sessionId) {
  return fetch(`${BASE}/sessions/${sessionId}`, { method: "DELETE" }).then(parseJson);
}

export async function streamChat(sessionId, message, handlers = {}) {
  // 按 SSE 块解析：token / compressed / done / error
  const response = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "对话请求失败");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // 不完整的 SSE 事件留在 buffer，等下一包拼齐
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .filter((item) => item.startsWith("data:"))
        .map((item) => item.slice(5).trim())
        .join("");
      if (!line) continue;
      const payload = JSON.parse(line);
      if (payload.type === "token") handlers.onToken?.(payload.content);
      if (payload.type === "progress") handlers.onProgress?.(payload);
      if (payload.type === "trace") handlers.onTrace?.(payload.span);
      if (payload.type === "compressed") handlers.onCompressed?.(payload);
      if (payload.type === "done") handlers.onDone?.(payload);
      if (payload.type === "error") throw new Error(payload.message || "模型调用失败");
    }
  }
}
