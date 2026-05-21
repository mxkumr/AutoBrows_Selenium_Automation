"""Configuration helpers for Selenium tests."""

from dataclasses import dataclass
import os


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FrameworkConfig:
    base_url: str = ""
    browser: str = "chrome"
    headless: bool = False
    implicit_wait: int = 5
    page_load_timeout: int = 30

    @classmethod
    def from_env(cls) -> "FrameworkConfig":
        return cls(
            base_url=os.getenv("AUTOBROWS_BASE_URL", ""),
            browser=os.getenv("AUTOBROWS_BROWSER", "chrome"),
            headless=_to_bool(os.getenv("AUTOBROWS_HEADLESS"), default=False),
            implicit_wait=int(os.getenv("AUTOBROWS_IMPLICIT_WAIT", "5")),
            page_load_timeout=int(os.getenv("AUTOBROWS_PAGE_LOAD_TIMEOUT", "30")),
        )
