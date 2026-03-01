from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Literal


class Settings(BaseSettings):
    llm_provider: Literal["openai", "anthropic", "auto"] = "auto"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def resolve_provider(self) -> "Settings":
        if self.llm_provider == "auto":
            if self.openai_api_key:
                object.__setattr__(self, "llm_provider", "openai")
            elif self.anthropic_api_key:
                object.__setattr__(self, "llm_provider", "anthropic")
        return self

    @property
    def active_model(self) -> str:
        return self.openai_model if self.llm_provider == "openai" else self.anthropic_model


settings = Settings()
