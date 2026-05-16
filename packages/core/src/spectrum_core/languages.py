from __future__ import annotations

from . import _repo as _repo  # noqa: F401 - ensures repo modules are importable.
from spec_format.spec_encoder import (
    LANGUAGE_C,
    LANGUAGE_CPP,
    LANGUAGE_CSHARP,
    LANGUAGE_CSS,
    LANGUAGE_GO,
    LANGUAGE_HTML,
    LANGUAGE_JS,
    LANGUAGE_JAVA,
    LANGUAGE_JSON,
    LANGUAGE_PHP,
    LANGUAGE_POWERSHELL,
    LANGUAGE_PYTHON,
    LANGUAGE_RUST,
    LANGUAGE_SHELL,
    LANGUAGE_SQL,
    LANGUAGE_TEXT,
    LANGUAGE_TOML,
    LANGUAGE_TS,
    LANGUAGE_XML,
    LANGUAGE_YAML,
)


LANGUAGE_BY_NAME = {
    "py": LANGUAGE_PYTHON,
    "python": LANGUAGE_PYTHON,
    "html": LANGUAGE_HTML,
    "htm": LANGUAGE_HTML,
    "js": LANGUAGE_JS,
    "javascript": LANGUAGE_JS,
    "css": LANGUAGE_CSS,
    "txt": LANGUAGE_TEXT,
    "text": LANGUAGE_TEXT,
    "md": LANGUAGE_TEXT,
    "markdown": LANGUAGE_TEXT,
    "ts": LANGUAGE_TS,
    "typescript": LANGUAGE_TS,
    "sql": LANGUAGE_SQL,
    "rs": LANGUAGE_RUST,
    "rust": LANGUAGE_RUST,
    "php": LANGUAGE_PHP,
    "xml": LANGUAGE_XML,
    "java": LANGUAGE_JAVA,
    "c": LANGUAGE_C,
    "cpp": LANGUAGE_CPP,
    "c++": LANGUAGE_CPP,
    "go": LANGUAGE_GO,
    "cs": LANGUAGE_CSHARP,
    "csharp": LANGUAGE_CSHARP,
    "c#": LANGUAGE_CSHARP,
    "sh": LANGUAGE_SHELL,
    "shell": LANGUAGE_SHELL,
    "bash": LANGUAGE_SHELL,
    "ps1": LANGUAGE_POWERSHELL,
    "psm1": LANGUAGE_POWERSHELL,
    "psd1": LANGUAGE_POWERSHELL,
    "powershell": LANGUAGE_POWERSHELL,
    "pwsh": LANGUAGE_POWERSHELL,
    "json": LANGUAGE_JSON,
    "yaml": LANGUAGE_YAML,
    "yml": LANGUAGE_YAML,
    "toml": LANGUAGE_TOML,
}

LANGUAGE_NAMES = {
    LANGUAGE_PYTHON: "Python",
    LANGUAGE_HTML: "HTML",
    LANGUAGE_JS: "JavaScript",
    LANGUAGE_CSS: "CSS",
    LANGUAGE_TEXT: "Text",
    LANGUAGE_TS: "TypeScript",
    LANGUAGE_SQL: "SQL",
    LANGUAGE_RUST: "Rust",
    LANGUAGE_PHP: "PHP",
    LANGUAGE_XML: "XML-compatible",
    LANGUAGE_JAVA: "Java",
    LANGUAGE_C: "C",
    LANGUAGE_CPP: "C++",
    LANGUAGE_GO: "Go",
    LANGUAGE_CSHARP: "C#",
    LANGUAGE_SHELL: "Shell",
    LANGUAGE_POWERSHELL: "PowerShell",
    LANGUAGE_JSON: "JSON",
    LANGUAGE_YAML: "YAML",
    LANGUAGE_TOML: "TOML",
}


def language_id(language: str | int | None) -> int:
    if language is None:
        return LANGUAGE_PYTHON
    if isinstance(language, int):
        return language
    key = language.lower().lstrip(".")
    try:
        return LANGUAGE_BY_NAME[key]
    except KeyError as exc:
        raise ValueError(f"unsupported Spectrum language: {language!r}") from exc
