from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic parse or schema failure with a stable location and rule."""

    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class StructuredOutputResult:
    """A parsed model output and the validation evidence needed for controller policy."""

    payload: Mapping[str, object] | None
    validation_errors: tuple[ValidationIssue, ...]

    @property
    def accepted(self) -> bool:
        return self.payload is not None and not self.validation_errors


def parse_and_validate_json_object(
    response_text: str,
    schema: Mapping[str, object],
) -> StructuredOutputResult:
    """Parse one model response into a JSON object and validate its declared schema."""

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as error:
        return StructuredOutputResult(
            payload=None,
            validation_errors=(
                ValidationIssue(path="$", rule="json_parse", message="model output must be valid JSON"),
            ),
        )
    if not isinstance(payload, Mapping):
        return StructuredOutputResult(
            payload=None,
            validation_errors=(
                ValidationIssue(path="$", rule="type", message="model output must be a JSON object"),
            ),
        )
    errors = validate_json_schema(payload, schema)
    return StructuredOutputResult(
        payload=dict(payload) if not errors else None,
        validation_errors=errors,
    )


def validate_json_schema(value: object, schema: Mapping[str, object]) -> tuple[ValidationIssue, ...]:
    """Validate the small, deterministic JSON-schema subset used by Axia contracts."""

    errors: list[ValidationIssue] = []
    _validate_schema_value(value, schema, "$", errors)
    return tuple(errors)


def _validate_schema_value(
    value: object,
    schema: Mapping[str, object],
    path: str,
    errors: list[ValidationIssue],
) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_json_type(value, expected_type):
        errors.append(ValidationIssue(path=path, rule="type", message=f"must have JSON type {expected_type!r}"))
        return
    if "const" in schema and value != schema["const"]:
        errors.append(ValidationIssue(path=path, rule="const", message="must match the declared constant"))
    if "enum" in schema:
        enum_values = schema["enum"]
        if not isinstance(enum_values, list):
            errors.append(ValidationIssue(path=path, rule="schema", message="enum must be a list"))
        elif value not in enum_values:
            errors.append(ValidationIssue(path=path, rule="enum", message="must match a declared enum value"))
    if isinstance(value, str):
        _validate_string(value, schema, path, errors)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _validate_number(value, schema, path, errors)
    elif isinstance(value, list):
        _validate_array(value, schema, path, errors)
    elif isinstance(value, Mapping):
        _validate_object(value, schema, path, errors)


def _validate_string(value: str, schema: Mapping[str, object], path: str, errors: list[ValidationIssue]) -> None:
    min_length = schema.get("minLength")
    if min_length is not None:
        if not isinstance(min_length, int):
            errors.append(ValidationIssue(path=path, rule="schema", message="minLength must be an integer"))
        elif len(value) < min_length:
            errors.append(ValidationIssue(path=path, rule="minLength", message=f"must have length at least {min_length}"))


def _validate_number(value: int | float, schema: Mapping[str, object], path: str, errors: list[ValidationIssue]) -> None:
    for keyword, comparison, text in (
        ("minimum", lambda actual, limit: actual < limit, "must be at least"),
        ("maximum", lambda actual, limit: actual > limit, "must be at most"),
    ):
        limit = schema.get(keyword)
        if limit is not None:
            if not isinstance(limit, (int, float)) or isinstance(limit, bool):
                errors.append(ValidationIssue(path=path, rule="schema", message=f"{keyword} must be numeric"))
            elif comparison(value, limit):
                errors.append(ValidationIssue(path=path, rule=keyword, message=f"{text} {limit}"))


def _validate_array(value: list[object], schema: Mapping[str, object], path: str, errors: list[ValidationIssue]) -> None:
    min_items = schema.get("minItems")
    if min_items is not None:
        if not isinstance(min_items, int):
            errors.append(ValidationIssue(path=path, rule="schema", message="minItems must be an integer"))
        elif len(value) < min_items:
            errors.append(ValidationIssue(path=path, rule="minItems", message=f"must contain at least {min_items} items"))
    item_schema = schema.get("items")
    if item_schema is not None:
        if not isinstance(item_schema, Mapping):
            errors.append(ValidationIssue(path=path, rule="schema", message="items must be an object"))
        else:
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, f"{path}[{index}]", errors)


def _validate_object(
    value: Mapping[str, object],
    schema: Mapping[str, object],
    path: str,
    errors: list[ValidationIssue],
) -> None:
    required_fields = schema.get("required", [])
    if not isinstance(required_fields, list):
        errors.append(ValidationIssue(path=path, rule="schema", message="required must be a list"))
        required_fields = ()
    for field in required_fields:
        if not isinstance(field, str):
            errors.append(ValidationIssue(path=path, rule="schema", message="required fields must be strings"))
        elif field not in value:
            errors.append(ValidationIssue(path=f"{path}.{field}", rule="required", message="is required"))

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        errors.append(ValidationIssue(path=path, rule="schema", message="properties must be an object"))
        return
    if schema.get("additionalProperties") is False:
        for field in sorted(set(value) - set(properties)):
            errors.append(ValidationIssue(path=f"{path}.{field}", rule="additionalProperties", message="is not allowed"))
    for field, field_schema in properties.items():
        if field not in value:
            continue
        if not isinstance(field_schema, Mapping):
            errors.append(ValidationIssue(path=f"{path}.{field}", rule="schema", message="property schema must be an object"))
            continue
        _validate_schema_value(value[field], field_schema, f"{path}.{field}", errors)


def _matches_json_type(value: object, expected_type: object) -> bool:
    matches = {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    return isinstance(expected_type, str) and matches.get(expected_type, False)
