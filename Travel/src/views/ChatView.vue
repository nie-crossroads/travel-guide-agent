<template>
  <div class="app-shell">
    <aside class="panel sidebar">
      <div class="brand">
        <div class="brand-mark">✈</div>
        <div>
          <h1>出发吧</h1>
          <p>私人旅行顾问 · 记住你的行程偏好</p>
        </div>
      </div>

      <el-button type="primary" class="new-trip-btn" :icon="Plus" @click="onNewSession">
        新对话
      </el-button>

      <div class="session-list">
        <div
          v-for="item in store.sessions"
          :key="item.id"
          class="session-item"
          :class="{ active: item.id === store.currentId }"
          @click="store.openSession(item.id)"
        >
          <div class="session-item-main">
            <h3>{{ item.title }}</h3>
            <span>{{ formatTime(item.updated_at) }} · {{ item.token_count || 0 }} tokens</span>
          </div>
          <el-button
            class="session-delete"
            text
            circle
            :icon="Delete"
            title="清除会话"
            @click.stop="onDeleteSession(item)"
          />
        </div>
      </div>
    </aside>

    <section class="panel chat-panel">
      <header class="chat-header">
        <div>
          <h2>出发吧 · 旅行顾问</h2>
          <p>按你的问题按需调用 Agent：问景点就推荐地方，完整攻略才会排行程和住宿。</p>
        </div>
        <div class="token-meter">
          <div class="hint" style="margin-top: 0; margin-bottom: 6px">
            记忆窗口 {{ store.tokenCount }} / {{ store.contextWindow }}
          </div>
          <el-progress
            :percentage="tokenPercent"
            :stroke-width="10"
            :color="tokenColor"
            :format="() => `${tokenPercent}%`"
          />
          <div class="hint">剩余不足 20% 时会自动压缩并保存对话记忆</div>
        </div>
      </header>

      <div ref="listRef" class="messages" @scroll.passive="onMessagesScroll">
        <div v-if="store.summary" class="summary-card">
          <strong>已保存的旅行记忆</strong>
          <div class="markdown-body" v-html="renderMarkdown(store.summary)" />
        </div>

        <div v-if="!store.messages.length" class="empty-hero">
          <h3>有什么可以帮你规划的？</h3>
          <p>先问你想了解什么；只有完整规划才会并行搜航班、酒店和活动。</p>
          <div class="chips">
            <el-button
              v-for="item in store.SUGGESTIONS"
              :key="item"
              round
              plain
              @click="onSend(item)"
            >
              {{ item }}
            </el-button>
          </div>
        </div>

        <div
          v-for="(item, index) in store.messages"
          :key="`${item.role}-${index}`"
          class="bubble-row"
          :class="item.role"
        >
          <div class="bubble" :class="item.role">
            <div
              v-if="item.role === 'assistant' && item.content"
              class="markdown-body"
              v-html="renderMarkdown(item.content)"
            />
            <template v-else>
              {{ item.content || (store.sending && index === store.messages.length - 1 ? (store.agentProgress || "正在思考…") : "") }}
            </template>
          </div>
        </div>
        <div class="messages-end" aria-hidden="true" />
      </div>

      <footer class="composer">
        <div class="composer-inner">
          <div class="composer-box">
            <el-input
              v-model="draft"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              resize="none"
              placeholder="询问关于目的地、行程或预算…"
              @keydown.enter.exact.prevent="onSend()"
            />
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="store.sending"
              circle
              @click="onSend()"
            />
          </div>
          <div class="hint">Enter 发送，Shift + Enter 换行</div>
        </div>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete, Plus, Promotion } from "@element-plus/icons-vue";
import { useChatStore } from "@/stores/chat";
import { renderMarkdown } from "@/utils/markdown";

const store = useChatStore();
const draft = ref("");
const listRef = ref(null);
const stickToBottom = ref(true);
let ignoreProgrammaticScroll = false;

const NEAR_BOTTOM_PX = 96;

function isNearBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX;
}

function onMessagesScroll() {
  // 用户上滑后停止跟滚，滑回底部再恢复，避免回答时被强制拉下去
  if (ignoreProgrammaticScroll) return;
  const el = listRef.value;
  if (!el) return;
  stickToBottom.value = isNearBottom(el);
}

async function scrollToBottom(force = false) {
  // 只滚消息列表；force 用于用户刚发送时一定看到最新气泡
  const el = listRef.value;
  if (!el) return;
  if (!force && !stickToBottom.value) return;
  await nextTick();
  ignoreProgrammaticScroll = true;
  el.scrollTop = el.scrollHeight;
  requestAnimationFrame(() => {
    ignoreProgrammaticScroll = false;
  });
}

const tokenPercent = computed(() => {
  // 进度条按当前窗口计算；≥80% 表示即将触发压缩
  if (!store.contextWindow) return 0;
  return Math.min(100, Math.round((store.tokenCount / store.contextWindow) * 100));
});

const tokenColor = computed(() => {
  if (tokenPercent.value >= 80) return "#f54e00";
  if (tokenPercent.value >= 60) return "#f5c518";
  return "#6f6f6f";
});

function formatTime(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function onNewSession() {
  stickToBottom.value = true;
  await store.newSession();
  draft.value = "";
  await scrollToBottom(true);
}

async function onDeleteSession(item) {
  try {
    await ElMessageBox.confirm(`确定清除「${item.title}」？清除后无法恢复。`, "清除会话", {
      type: "warning",
      confirmButtonText: "清除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    const wasCurrent = item.id === store.currentId;
    await store.removeSession(item.id);
    if (wasCurrent) {
      stickToBottom.value = true;
      draft.value = "";
      await scrollToBottom(true);
    }
  } catch (error) {
    ElMessage.error(error.message || "清除失败");
  }
}

async function onSend(text) {
  const content = (text ?? draft.value).trim();
  if (!content) return;
  if (!text) draft.value = "";
  stickToBottom.value = true;
  await scrollToBottom(true);
  try {
    const result = await store.sendMessage(content);
    if (result?.compressed) {
      // ElMessage.success("对话记忆已压缩并保存");
    }
  } catch (error) {
    ElMessage.error(error.message || "发送失败");
  }
}

watch(
  () => [store.messages.map((item) => item.content).join(), store.agentProgress],
  () => {
    scrollToBottom();
  }
);

onMounted(async () => {
  try {
    await store.bootstrap();
  } catch (error) {
    ElMessage.error(error.message || "无法连接到旅行顾问服务");
  }
});
</script>

<style scoped>
.new-trip-btn {
  --el-button-bg-color: #1c1c1c;
  --el-button-border-color: rgba(255, 255, 255, 0.08);
  --el-button-text-color: #e8e8e8;
  --el-button-hover-bg-color: #2a2a2a;
  --el-button-hover-border-color: #3a3a3a;
  --el-button-hover-text-color: #fff;
}
</style>
