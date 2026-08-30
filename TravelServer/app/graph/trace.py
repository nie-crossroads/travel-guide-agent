from __future__ import annotations

import functools
import inspect
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Iterator

logger = logging.getLogger("travel.trace")

_turn: ContextVar["TurnTrace | None"] = ContextVar("travel_turn_trace", default=None)


@dataclass
class Span:
    """一轮对话里的一段计时：Agent 进出、模型调用或工具调用。"""

    id: str
    kind: str
    name: str
    parent: str | None
    duration_ms: float
    ok: bool
    error: str = ""


@dataclass
class TurnTrace:
    """按请求隔离的 span 列表。不写入 LangGraph state，避免检查点膨胀。"""

    started_at: float = field(default_factory=time.perf_counter)
    spans: list[Span] = field(default_factory=list)
    _open: dict[str, Span] = field(default_factory=dict)
    _stack: list[str] = field(default_factory=list)
    _seq: int = 0
    _emitted: int = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f"s{self._seq}"

    def begin(self, kind: str, name: str) -> Span:
        """先占坑再执行，子 span 才能挂到当前 Agent 上；结束前不推 SSE。"""
        span = Span(
            id=self._next_id(),
            kind=kind,
            name=name,
            parent=self._stack[-1] if self._stack else None,
            duration_ms=0,
            ok=True,
        )
        self._open[span.id] = span
        self._stack.append(span.id)
        return span

    def finish(self, span: Span, duration_ms: float, ok: bool, error: str = "") -> None:
        span.duration_ms = round(duration_ms, 1)
        span.ok = ok
        span.error = error
        self._open.pop(span.id, None)
        if self._stack and self._stack[-1] == span.id:
            self._stack.pop()
        elif span.id in self._stack:
            self._stack.remove(span.id)
        self.spans.append(span)

    def drain(self) -> list[dict[str, Any]]:
        """取出已结束、尚未推给前端的 span，供 SSE 边跑边出。"""
        fresh = self.spans[self._emitted :]
        self._emitted = len(self.spans)
        return [span_to_dict(item) for item in fresh]

    def snapshot(self) -> dict[str, Any]:
        total_ms = round((time.perf_counter() - self.started_at) * 1000, 1)
        return {
            "total_ms": total_ms,
            "spans": [span_to_dict(item) for item in self.spans],
        }


def span_to_dict(span: Span) -> dict[str, Any]:
    return {
        "id": span.id,
        "kind": span.kind,
        "name": span.name,
        "parent": span.parent,
        "duration_ms": span.duration_ms,
        "ok": span.ok,
        "error": span.error,
    }


def start_turn() -> TurnTrace:
    trace = TurnTrace()
    _turn.set(trace)
    return trace


def end_turn(token: Token | None = None) -> None:
    if token is not None:
        _turn.reset(token)
    else:
        _turn.set(None)


def current_trace() -> TurnTrace | None:
    return _turn.get()


def drain_spans() -> list[dict[str, Any]]:
    trace = current_trace()
    if trace is None:
        return []
    return trace.drain()


def turn_snapshot() -> dict[str, Any]:
    trace = current_trace()
    if trace is None:
        return {"total_ms": 0, "spans": []}
    return trace.snapshot()


def log_turn(trace: dict[str, Any]) -> None:
    """收尾打一行摘要，按耗时降序，方便在后端日志里找慢段。"""
    spans = list(trace.get("spans") or [])
    if not spans:
        logger.info("trace 本轮无 span total_ms=%s", trace.get("total_ms"))
        return
    ranked = sorted(spans, key=lambda item: float(item.get("duration_ms") or 0), reverse=True)
    bits = [
        f"{item.get('kind')}:{item.get('name')}={item.get('duration_ms')}ms"
        for item in ranked[:8]
    ]
    logger.info("trace total_ms=%s %s", trace.get("total_ms"), " ".join(bits))


@contextmanager
def span_sync(kind: str, name: str) -> Iterator[None]:
    """同步出入口计时；失败也记账，避免慢请求丢失。"""
    trace = current_trace()
    started = time.perf_counter()
    ok = True
    error = ""
    current: Span | None = None
    if trace is not None:
        current = trace.begin(kind, name)
    try:
        yield
    except Exception as exc:
        ok = False
        error = str(exc)
        raise
    finally:
        if trace is not None and current is not None:
            trace.finish(current, (time.perf_counter() - started) * 1000, ok, error)


@asynccontextmanager
async def span(kind: str, name: str) -> AsyncIterator[None]:
    trace = current_trace()
    started = time.perf_counter()
    ok = True
    error = ""
    current: Span | None = None
    if trace is not None:
        current = trace.begin(kind, name)
    try:
        yield
    except Exception as exc:
        ok = False
        error = str(exc)
        raise
    finally:
        if trace is not None and current is not None:
            trace.finish(current, (time.perf_counter() - started) * 1000, ok, error)


def traced(kind: str, name: str | None = None) -> Callable:
    """给 Agent / 节点函数包一层进出耗时；内部工具会挂到该 span 下。"""

    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any):
                async with span(kind, span_name):
                    return await fn(*args, **kwargs)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any):
            with span_sync(kind, span_name):
                return fn(*args, **kwargs)

        return sync_wrapper

    return decorator
