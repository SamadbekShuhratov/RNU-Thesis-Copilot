"""Language support.

* OUTPUT_LANGUAGES — languages the agents can write the paper in.
* UI_LANGUAGES     — languages of the web portal and of validator messages.
"""
from __future__ import annotations

OUTPUT_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "native": "English"},
    "lv": {"name": "Latvian", "native": "Latviešu"},
    "ru": {"name": "Russian", "native": "Русский"},
    "uz": {"name": "Uzbek (Latin script)", "native": "O'zbekcha"},
    "uk": {"name": "Ukrainian", "native": "Українська"},
    "lt": {"name": "Lithuanian", "native": "Lietuvių"},
    "et": {"name": "Estonian", "native": "Eesti"},
    "pl": {"name": "Polish", "native": "Polski"},
    "de": {"name": "German", "native": "Deutsch"},
    "fr": {"name": "French", "native": "Français"},
    "es": {"name": "Spanish", "native": "Español"},
    "it": {"name": "Italian", "native": "Italiano"},
    "pt": {"name": "Portuguese", "native": "Português"},
    "tr": {"name": "Turkish", "native": "Türkçe"},
    "kk": {"name": "Kazakh", "native": "Қазақша"},
}

UI_LANGUAGES = ["uz", "en", "ru", "lv"]


def language_name(code: str) -> str:
    return OUTPUT_LANGUAGES.get(code, OUTPUT_LANGUAGES["en"])["name"]
