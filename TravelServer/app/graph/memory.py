from __future__ import annotations

import re

from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately

from app.config import settings
from app.graph.state import AgentState
from app.prompts.travel import TRAVEL_SYSTEM_PROMPT

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


def _encoding():
    """优先使用接近 GPT-5 系列的 o200k，失败则回退 cl100k。"""
    if tiktoken is None:
        return None
    for name in ("o200k_base", "cl100k_base"):
        try:
            return tiktoken.get_encoding(name)
        except Exception:
            continue
    return None


_ENCODER = _encoding()


def _stringify_content(content: object) -> str:
    """把消息 content 统一成纯文本。新模型可能返回 content block 列表。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def count_text_tokens(text: str) -> int:
    """估算一段文本占用的 token 数，用于判断是否触及压缩阈值。"""
    if not text:
        return 0
    if _ENCODER is not None:
        return len(_ENCODER.encode(text))
    return count_tokens_approximately([{"role": "user", "content": text}])


def message_text(message: BaseMessage) -> str:
    return _stringify_content(message.content)


def count_message_tokens(message: BaseMessage) -> int:
    # +4 近似角色、分隔符等消息开销
    role = getattr(message, "type", "message")
    return count_text_tokens(f"{role}: {message_text(message)}") + 4


def build_system_prompt(summary: str | None) -> str:
    """拼出发给模型的系统提示：旅行顾问人设 + 已压缩的历史记忆。"""
    prompt = TRAVEL_SYSTEM_PROMPT.strip()
    if summary and summary.strip():
        prompt += (
            "\n\n以下是此前对话的压缩摘要，请作为背景记忆继续服务，不要遗忘其中的关键信息：\n"
            f"{summary.strip()}"
        )
    return prompt


def count_state_tokens(state: AgentState, extra_messages: list[BaseMessage] | None = None) -> int:
    """统计当前会进入模型上下文的 token：system + 摘要 + 近期消息。"""
    summary = state.get("summary") or ""
    messages = list(state.get("messages") or [])
    if extra_messages:
        messages = messages + extra_messages
    total = count_text_tokens(build_system_prompt(summary))
    for message in messages:
        total += count_message_tokens(message)
    return total


def remaining_tokens(state: AgentState) -> int:
    used = count_state_tokens(state)
    return settings.context_window - used


def should_compress(state: AgentState) -> bool:
    """窗口剩余不足 20%（10000 窗口时已用 ≥ 8000）且还有可压缩的旧消息时触发。"""
    used = count_state_tokens(state)
    remaining = settings.context_window - used
    if remaining <= int(settings.context_window * settings.compress_remaining_ratio):
        keep = settings.keep_recent_messages
        return len(state.get("messages") or []) > keep
    return False


def format_transcript(messages: list[BaseMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        role = "用户" if message.type == "human" else "顾问"
        if message.type == "system":
            role = "系统"
        lines.append(f"{role}：{message_text(message)}")
    return "\n".join(lines)


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """去掉模型完整输出里的 <think> 推理块，避免写入历史或展示给用户。"""
    cleaned = _THINK_BLOCK.sub("", text or "")
    return cleaned.replace("<think>", "").replace("</think>", "").strip()


class ThinkFilter:
    """SSE 流式过滤：边收 token 边丢掉尚未闭合的 <think>…</think>。"""

    def __init__(self) -> None:
        self.buffer = ""
        self.in_think = False

    def feed(self, text: str) -> str:
        """追加一段增量文本，只返回当前已经可以安全展示的内容。"""
        self.buffer += text
        visible: list[str] = []
        while self.buffer:
            if self.in_think:
                end = self.buffer.lower().find("</think>")
                if end < 0:
                    # 结束标签可能被拆到下一块，只保留尾部防止漏掉 </think>
                    if len(self.buffer) > 16:
                        self.buffer = self.buffer[-16:]
                    break
                self.buffer = self.buffer[end + len("</think>") :]
                self.in_think = False
                continue
            start = self.buffer.lower().find("<think>")
            if start < 0:
                hold_at = self.buffer.rfind("<")
                # 可能是不完整的 "<think" 前缀，先按住尾部再等后续 token
                if hold_at >= 0 and len(self.buffer) - hold_at < 10:
                    visible.append(self.buffer[:hold_at])
                    self.buffer = self.buffer[hold_at:]
                else:
                    visible.append(self.buffer)
                    self.buffer = ""
                break
            visible.append(self.buffer[:start])
            self.buffer = self.buffer[start + len("<think>") :]
            self.in_think = True
        return "".join(visible)
