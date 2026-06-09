from langchain_openai import ChatOpenAI

from backend.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, LLM_MODEL


class LLMClient:
    def __init__(self) -> None:
        if not BAILIAN_API_KEY:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用阿里云百炼模型")
        self.client = ChatOpenAI(
            api_key=BAILIAN_API_KEY,
            base_url=BAILIAN_BASE_URL,
            model=LLM_MODEL,
            temperature=0.2,
        )

    def generate(self, prompt: str) -> str:
        result = self.client.invoke(prompt)
        return str(result.content)

