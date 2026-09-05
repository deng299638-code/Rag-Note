import os
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

def create_embedding_model():

    base_url = os.getenv("EMBED_BASE_URL")
    api_key = os.getenv("EMBED_API_KEY")

    if not base_url and not api_key:
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")

    if not base_url or not api_key:
        raise ValueError(
            "请同时配置 EMBED_BASE_URL 与 EMBED_API_KEY，"
            "或配置 OPENAI_BASE_URL 与 OPENAI_API_KEY"
        )

    return OpenAIEmbeddings(
        model=os.getenv("EMBED_MODEL_NAME","text-embedding-v3"),
        base_url = base_url,
        api_key = SecretStr(api_key) if api_key else None,
        chunk_size = 10,
        check_embedding_ctx_length=False,#跳过token计算
    )
