from typing import List

import numpy as np
from openai import OpenAI

from backend.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, EMBEDDING_DIM, EMBEDDING_MODEL_NAME


class EmbeddingModel:
    def __init__(self) -> None:
        if not BAILIAN_API_KEY:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用阿里云百炼 embedding 模型")
        self.client = OpenAI(
            api_key=BAILIAN_API_KEY,
            base_url=BAILIAN_BASE_URL,
        )

    def encode(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([], dtype="float32")
        vectors = [self._embed(text) for text in texts]
        return np.array(vectors, dtype="float32")

    def encode_one(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL_NAME,
            input=text,
            dimensions=EMBEDDING_DIM,
        )
        return list(map(float, response.data[0].embedding))


def get_embedding_model() -> EmbeddingModel:
    return EmbeddingModel()
