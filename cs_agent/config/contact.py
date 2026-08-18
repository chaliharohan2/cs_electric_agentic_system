"""Where enquiries this agent cannot answer are sent."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class Contact(BaseModel):
    website: str
    phone: str


_PATH = Path(__file__).with_name("contact.yaml")
_ENV_NAMES = {"website": "CS_CONTACT_WEBSITE", "phone": "CS_CONTACT_PHONE"}


@lru_cache(maxsize=1)
def get_contact() -> Contact:
    with _PATH.open(encoding="utf-8") as handle:
        values = yaml.safe_load(handle) or {}
    for field_name, env_name in _ENV_NAMES.items():
        if raw := os.getenv(env_name):
            values[field_name] = raw
    return Contact.model_validate(values)


def clear_contact_cache() -> None:
    get_contact.cache_clear()
