from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Literal


class Settings(BaseSettings):
    llm_provider: Literal["openai", "anthropic", "gemini", "auto"] = "auto"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def resolve_provider(self) -> "Settings":
        if self.llm_provider == "auto":
            if self.openai_api_key:
                object.__setattr__(self, "llm_provider", "openai")
            elif self.anthropic_api_key:
                object.__setattr__(self, "llm_provider", "anthropic")
            elif self.gemini_api_key:
                object.__setattr__(self, "llm_provider", "gemini")
        return self

    @property
    def active_model(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_model
        if self.llm_provider == "gemini":
            return self.gemini_model
        return self.anthropic_model


settings = Settings()
