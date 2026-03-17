"""Input schema validation for human task responses.

Validates response data against the input_schema defined on a human task.
Supports 10 field types: string, text, secret, file, url, email, color,
enum, boolean, number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldError:
    field_name: str
    message: str
    code: str = "invalid"

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field_name,
            "message": self.message,
            "code": self.code,
        }


_URL_PATTERN = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)
_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_response_against_schema(
    input_schema: dict[str, Any],
    response: dict[str, Any],
) -> list[FieldError]:
    """Validate every field in response against its schema definition.

    Returns a list of FieldError for each invalid field. An empty list
    means validation passed.
    """
    errors: list[FieldError] = []

    for field_name, field_def in input_schema.items():
        if not isinstance(field_def, dict):
            continue
        value = response.get(field_name)
        required = field_def.get("required", False)
        field_type = field_def.get("type", "string")

        if value is None or (isinstance(value, str) and value.strip() == ""):
            if required:
                errors.append(FieldError(
                    field_name=field_name,
                    message=f"{field_def.get('label', field_name)} is required",
                    code="required",
                ))
            continue

        field_errors = _validate_field(field_name, field_def, field_type, value)
        errors.extend(field_errors)

    return errors


def _validate_field(
    field_name: str,
    field_def: dict[str, Any],
    field_type: str,
    value: Any,
) -> list[FieldError]:
    """Dispatch to type-specific validator."""
    validators = {
        "string": _validate_string,
        "text": _validate_text,
        "secret": _validate_secret,
        "file": _validate_file,
        "url": _validate_url,
        "email": _validate_email,
        "color": _validate_color,
        "enum": _validate_enum,
        "boolean": _validate_boolean,
        "number": _validate_number,
    }
    validator = validators.get(field_type)
    if validator is None:
        return [FieldError(
            field_name=field_name,
            message=f"Unknown field type: {field_type}",
            code="unknown_type",
        )]
    return validator(field_name, field_def, value)


def _validate_string(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    errors: list[FieldError] = []
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    errors.extend(_check_length(field_name, field_def, value))
    errors.extend(_check_pattern(field_name, field_def, value))
    return errors


def _validate_text(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    return _check_length(field_name, field_def, value)


def _validate_secret(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    errors: list[FieldError] = []
    errors.extend(_check_length(field_name, field_def, value))
    errors.extend(_check_pattern(field_name, field_def, value))
    return errors


def _validate_file(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, dict):
        return [FieldError(field_name, "Must be a file reference object", "type_mismatch")]
    errors: list[FieldError] = []
    if not value.get("asset_key"):
        errors.append(FieldError(field_name, "Missing asset_key", "missing_key"))
    content_type = value.get("content_type", "")
    accept = field_def.get("accept", [])
    if accept and content_type and content_type not in accept:
        errors.append(FieldError(
            field_name,
            f"File type {content_type} not accepted. Allowed: {', '.join(accept)}",
            "invalid_content_type",
        ))
    return errors


def _validate_url(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    if not _URL_PATTERN.match(value):
        return [FieldError(field_name, "Must be a valid URL (http:// or https://)", "invalid_url")]
    return []


def _validate_email(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    if not _EMAIL_PATTERN.match(value):
        return [FieldError(field_name, "Must be a valid email address", "invalid_email")]
    return []


def _validate_color(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    if not _COLOR_PATTERN.match(value):
        return [FieldError(field_name, "Must be a hex color (#RRGGBB)", "invalid_color")]
    return []


def _validate_enum(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, str):
        return [FieldError(field_name, "Must be a string", "type_mismatch")]
    options = field_def.get("options", [])
    valid_values = {opt["value"] if isinstance(opt, dict) else opt for opt in options}
    if value not in valid_values:
        return [FieldError(
            field_name,
            f"Must be one of: {', '.join(sorted(valid_values))}",
            "invalid_option",
        )]
    return []


def _validate_boolean(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, bool):
        return [FieldError(field_name, "Must be a boolean", "type_mismatch")]
    return []


def _validate_number(
    field_name: str,
    field_def: dict[str, Any],
    value: Any,
) -> list[FieldError]:
    if not isinstance(value, (int, float)):
        return [FieldError(field_name, "Must be a number", "type_mismatch")]
    errors: list[FieldError] = []
    min_val = field_def.get("min")
    max_val = field_def.get("max")
    if min_val is not None and value < min_val:
        errors.append(FieldError(field_name, f"Must be >= {min_val}", "below_min"))
    if max_val is not None and value > max_val:
        errors.append(FieldError(field_name, f"Must be <= {max_val}", "above_max"))
    return errors


def _check_length(
    field_name: str,
    field_def: dict[str, Any],
    value: str,
) -> list[FieldError]:
    errors: list[FieldError] = []
    min_len = field_def.get("minLength")
    max_len = field_def.get("maxLength")
    if min_len is not None and len(value) < min_len:
        errors.append(FieldError(
            field_name, f"Must be at least {min_len} characters", "too_short",
        ))
    if max_len is not None and len(value) > max_len:
        errors.append(FieldError(
            field_name, f"Must be at most {max_len} characters", "too_long",
        ))
    return errors


def _check_pattern(
    field_name: str,
    field_def: dict[str, Any],
    value: str,
) -> list[FieldError]:
    pattern = field_def.get("pattern")
    if pattern is None:
        return []
    try:
        if not re.match(pattern, value):
            hint = field_def.get("pattern_hint", f"Must match pattern: {pattern}")
            return [FieldError(field_name, hint, "pattern_mismatch")]
    except re.error:
        return [FieldError(field_name, f"Invalid pattern in schema: {pattern}", "invalid_pattern")]
    return []
