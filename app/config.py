"""应用配置模块。

从环境变量加载配置项，包括 OpenAI API 密钥、模型名称、Viking 数据目录等。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """应用全局配置。

    Attributes:
        openai_api_key: OpenAI API 密钥。
        openai_model: 使用的 OpenAI 模型名称。
        viking_data_dir: OpenViking 数据存储目录。
        host: 服务监听地址。
        port: 服务监听端口。
    """

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    viking_data_dir: str = field(default_factory=lambda: os.getenv("VIKING_DATA_DIR", "./data/viking"))
    skills_dir: str = field(default_factory=lambda: os.getenv("SKILLS_DIR", "./skills"))
    analytics_api_base: str = field(default_factory=lambda: os.getenv("ANALYTICS_API_BASE", "https://api.example.com/v1"))
    analytics_api_key: str = field(default_factory=lambda: os.getenv("ANALYTICS_API_KEY", ""))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))


settings = Settings()
