from langchain_openai import ChatOpenAI

from config.settings import settings


def chat_llm(*, model: str | None = None, temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or settings.default_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
    )