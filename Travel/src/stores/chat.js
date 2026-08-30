import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { createSession, deleteSession, getSessionMessages, listSessions, streamChat } from "@/api/chat";

const SUGGESTIONS = [
  "成都明天天气怎么样",
  "成都有哪些好玩的地方",
  "帮我规划 3 日京都行程",
  "亲子游海南怎么玩更轻松",
  "预算 5000 的川西自驾",
  "十月去新疆要注意什么",
  "搜一下成都最近有什么展会",
];

export const useChatStore = defineStore("chat", () => {
  const sessions = ref([]);
  const currentId = ref("");
  const messages = ref([]);
  const summary = ref("");
  const tokenCount = ref(0);
  const contextWindow = ref(10000);
  const compressThreshold = ref(8000);
  const loading = ref(false);
  const sending = ref(false);
  const agentProgress = ref("");

  const currentSession = computed(
    () => sessions.value.find((item) => item.id === currentId.value) || null
  );

  async function bootstrap() {
    loading.value = true;
    try {
      const data = await listSessions();
      sessions.value = data.sessions || [];
      if (!sessions.value.length) {
        await newSession();
      } else {
        await openSession(sessions.value[0].id);
      }
    } finally {
      loading.value = false;
    }
  }

  async function refreshSessions() {
    const data = await listSessions();
    sessions.value = data.sessions || [];
  }

  async function newSession() {
    const session = await createSession();
    sessions.value = [session, ...sessions.value.filter((item) => item.id !== session.id)];
    currentId.value = session.id;
    messages.value = [];
    summary.value = "";
    tokenCount.value = 0;
    agentProgress.value = "";
  }

  async function openSession(sessionId) {
    currentId.value = sessionId;
    const data = await getSessionMessages(sessionId);
    messages.value = data.messages || [];
    summary.value = data.summary || "";
    tokenCount.value = data.token_count || 0;
    contextWindow.value = data.context_window || 10000;
    compressThreshold.value = data.compress_threshold || 8000;
  }

  async function removeSession(sessionId) {
    await deleteSession(sessionId);
    const leftover = sessions.value.filter((item) => item.id !== sessionId);
    sessions.value = leftover;
    if (currentId.value !== sessionId) return;
    if (leftover.length) {
      await openSession(leftover[0].id);
      return;
    }
    await newSession();
  }

  async function sendMessage(text) {
    // 先插入空助手气泡，再靠 onToken 往里追加，避免等整段返回才渲染
    if (!text.trim() || sending.value) return;
    if (!currentId.value) await newSession();

    const content = text.trim();
    messages.value.push({ role: "user", content });
    messages.value.push({ role: "assistant", content: "" });
    sending.value = true;
    agentProgress.value = "多 Agent 协作规划中…";
    let donePayload = null;

    try {
      await streamChat(currentId.value, content, {
        onToken(token) {
          const last = messages.value[messages.value.length - 1];
          last.content += token;
          agentProgress.value = "";
        },
        onProgress(payload) {
          agentProgress.value = payload.message || agentProgress.value;
        },
        onTrace(span) {
          const last = messages.value[messages.value.length - 1];
          if (!last || last.role !== "assistant") return;
          const next = [...(last.traceSpans || [])];
          const idx = next.findIndex((item) => item.id === span.id);
          if (idx >= 0) next[idx] = span;
          else next.push(span);
          messages.value[messages.value.length - 1] = { ...last, traceSpans: next };
        },
        onCompressed(payload) {
          summary.value = payload.summary || summary.value;
          tokenCount.value = payload.token_count || tokenCount.value;
        },
        onDone(payload) {
          donePayload = payload;
          tokenCount.value = payload.token_count || 0;
          contextWindow.value = payload.context_window || contextWindow.value;
          compressThreshold.value = payload.compress_threshold || compressThreshold.value;
          if (payload.summary) summary.value = payload.summary;
          const last = messages.value[messages.value.length - 1];
          if (last && last.role === "assistant" && payload.trace) {
            messages.value[messages.value.length - 1] = {
              ...last,
              traceSpans: payload.trace.spans || last.traceSpans || [],
              traceTotal: payload.trace.total_ms,
            };
          }
        },
      });
      await refreshSessions();
      return donePayload;
    } catch (error) {
      const last = messages.value[messages.value.length - 1];
      last.content = last.content || `抱歉，这次没有聊成功：${error.message}`;
      throw error;
    } finally {
      sending.value = false;
      agentProgress.value = "";
    }
  }

  return {
    SUGGESTIONS,
    sessions,
    currentId,
    messages,
    summary,
    tokenCount,
    contextWindow,
    compressThreshold,
    loading,
    sending,
    agentProgress,
    currentSession,
    bootstrap,
    newSession,
    openSession,
    removeSession,
    sendMessage,
  };
});
