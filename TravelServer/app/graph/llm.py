from langchain_openai import ChatOpenAI

from app.config import settings


def build_llm(*, temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
        streaming=streaming,
    )
