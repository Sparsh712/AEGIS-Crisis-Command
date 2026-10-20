"""Structured LLM boundary with deterministic offline behavior for Level 0."""

from enum import Enum
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ValidationError

from .config import get_settings


class LLMError(RuntimeError):
    """Raised when a structured LLM response cannot be produced or validated."""


def _fake_value(annotation: Any, field_name: str) -> Any:
    """Build a conservative value for a field in a fake structured response."""

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        non_none = [arg for arg in args if arg is not type(None)]
        return None if not non_none else _fake_value(non_none[0], field_name)
    if origin in (list, set, tuple):
        return []
    if origin is dict:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return next(iter(annotation)).value
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _fake_payload(annotation)
    if annotation is str:
        if field_name == "rationale":
            return "FAKE_LLM response grounded in supplied evidence."
        return "FAKE_LLM response"
    if annotation is int:
        return 3 if field_name in {"priority", "det_score"} else 1
    if annotation is float:
        return 0.0
    if annotation is bool:
        return False
    return None


def _fake_payload(schema: type[BaseModel]) -> dict[str, Any]:
    """Create a valid-enough deterministic payload for any simple Pydantic model."""

    fields = getattr(schema, "model_fields", None)
    if fields is None:  # Pydantic v1 compatibility for local tooling.
        fields = getattr(schema, "__fields__", {})
        hints = get_type_hints(schema)
        return {
            name: _fake_value(hints.get(name, field.outer_type_), name)
            for name, field in fields.items()
            if field.required
        }

    payload: dict[str, Any] = {}
    hints = get_type_hints(schema)
    for name, field in fields.items():
        if not field.is_required():
            continue
        payload[name] = _fake_value(hints.get(name, field.annotation), name)
    return payload


def _validate(schema: type[BaseModel], payload: Any) -> BaseModel:
    if hasattr(schema, "model_validate"):
        return schema.model_validate(payload)
    return schema.parse_obj(payload)


async def complete_json(
    system: str,
    user: str,
    schema: type[BaseModel],
    retries: int = 1,
) -> BaseModel:
    """Return a schema-validated response from the configured provider.

    Level 0 intentionally implements the offline provider only.  Other
    providers fail explicitly until their transport and JSON-schema adapters
    are added in a later level; no network call is made accidentally.
    """

    if not isinstance(schema, type) or not issubclass(schema, BaseModel):
        raise LLMError("schema must be a Pydantic BaseModel class")

    settings = get_settings()
    attempts = max(0, retries) + 1
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            if not settings.fake_llm:
                raise LLMError(
                    f"LLM provider '{settings.llm_provider}' is not implemented in Level 0 "
                    "or FAKE_LLM is disabled"
                )
            payload = _fake_payload(schema)
            return _validate(schema, payload)
        except (ValidationError, LLMError) as exc:
            last_error = exc

    raise LLMError(
        f"structured response failed validation after {attempts} attempt(s)"
    ) from last_error
