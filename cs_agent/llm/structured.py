"""Reliable schema validation for models without native structured output."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from langchain_core.messages import AnyMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from .factory import get_model

SchemaT = TypeVar("SchemaT", bound=BaseModel)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _parse(content: object, schema: type[SchemaT]) -> SchemaT:
    text = _FENCE.sub("", _content_text(content).strip()).strip()
    return schema.model_validate(json.loads(text))


def structured(
    node: str,
    messages: list[AnyMessage],
    schema: type[SchemaT],
) -> SchemaT:
    """Invoke a model, parse JSON, and retry once with validation feedback."""

    model = get_model(node)
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    request = [
        *messages,
        HumanMessage(
            content=(
                "Return only one JSON object matching this JSON Schema. "
                "Do not use markdown fences.\n" + schema_json
            )
        ),
    ]
    response = model.invoke(request)
    try:
        return _parse(response.content, schema)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        retry = [
            *request,
            response,
            HumanMessage(
                content=(
                    f"The response failed validation: {exc}. Correct it and return "
                    "only the valid JSON object, without markdown fences."
                )
            ),
        ]
        return _parse(model.invoke(retry).content, schema)
