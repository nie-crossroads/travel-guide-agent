from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # add_messages：追加新消息；压缩时配合 RemoveMessage 删除旧消息
    messages: Annotated[list, add_messages]
    summary: NotRequired[str]  # 已压缩的旅行记忆，下一轮拼进 system prompt
    token_count: NotRequired[int]
    compressed: NotRequired[bool]  # 本轮是否刚完成压缩，供 SSE 提示前端
    intent: NotRequired[str]  # plan | chat
    needed_agents: NotRequired[list]  # destination/flight/hotel/activity/budget/weather/maps_route
    progress: NotRequired[str]
    preferences: NotRequired[dict]
    destination: NotRequired[dict]
    flights: NotRequired[dict]
    hotels: NotRequired[dict]
    activities: NotRequired[dict]
    budget: NotRequired[dict]
    weather: NotRequired[dict]
    maps_route: NotRequired[dict]
    adjustment_round: NotRequired[int]
    adjustment_hints: NotRequired[list]
