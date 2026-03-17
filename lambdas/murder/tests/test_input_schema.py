"""Tests for input schema validation — all 10 field types + 10 real-world examples."""

from __future__ import annotations

import pytest

from murder.input_schema import FieldError, validate_response_against_schema


class TestStringField:
    def test_valid_string(self) -> None:
        schema = {"name": {"type": "string", "required": True}}
        errors = validate_response_against_schema(schema, {"name": "Eduardo"})
        assert errors == []

    def test_required_string_missing(self) -> None:
        schema = {"name": {"type": "string", "required": True}}
        errors = validate_response_against_schema(schema, {})
        assert len(errors) == 1
        assert errors[0].code == "required"

    def test_optional_string_missing(self) -> None:
        schema = {"name": {"type": "string", "required": False}}
        errors = validate_response_against_schema(schema, {})
        assert errors == []

    def test_pattern_match(self) -> None:
        schema = {"phone": {
            "type": "string",
            "pattern": r"^\+[1-9]\d{1,14}$",
            "pattern_hint": "E.164 format",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"phone": "+5511999999999"})
        assert errors == []

    def test_pattern_mismatch(self) -> None:
        schema = {"phone": {
            "type": "string",
            "pattern": r"^\+[1-9]\d{1,14}$",
            "pattern_hint": "E.164 format",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"phone": "not-a-phone"})
        assert len(errors) == 1
        assert errors[0].code == "pattern_mismatch"
        assert "E.164" in errors[0].message

    def test_min_length(self) -> None:
        schema = {"code": {"type": "string", "minLength": 5, "required": True}}
        errors = validate_response_against_schema(schema, {"code": "ab"})
        assert len(errors) == 1
        assert errors[0].code == "too_short"

    def test_max_length(self) -> None:
        schema = {"code": {"type": "string", "maxLength": 5, "required": True}}
        errors = validate_response_against_schema(schema, {"code": "abcdefgh"})
        assert len(errors) == 1
        assert errors[0].code == "too_long"

    def test_type_mismatch(self) -> None:
        schema = {"name": {"type": "string", "required": True}}
        errors = validate_response_against_schema(schema, {"name": 123})
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"


class TestTextField:
    def test_valid_text(self) -> None:
        schema = {"body": {"type": "text", "maxLength": 1024, "required": True}}
        errors = validate_response_against_schema(schema, {"body": "Hello world\nLine 2"})
        assert errors == []

    def test_text_too_long(self) -> None:
        schema = {"body": {"type": "text", "maxLength": 10, "required": True}}
        errors = validate_response_against_schema(schema, {"body": "x" * 20})
        assert len(errors) == 1
        assert errors[0].code == "too_long"


class TestSecretField:
    def test_valid_secret(self) -> None:
        schema = {"token": {"type": "secret", "required": True}}
        errors = validate_response_against_schema(schema, {"token": "sk-abc123"})
        assert errors == []

    def test_secret_with_pattern(self) -> None:
        schema = {"token": {
            "type": "secret",
            "pattern": "^EAAGm0.+",
            "pattern_hint": "Starts with EAAGm0...",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"token": "EAAGm0xyz123"})
        assert errors == []

    def test_secret_pattern_mismatch(self) -> None:
        schema = {"token": {
            "type": "secret",
            "pattern": "^EAAGm0.+",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"token": "wrong-token"})
        assert len(errors) == 1
        assert errors[0].code == "pattern_mismatch"

    def test_secret_min_length(self) -> None:
        schema = {"token": {"type": "secret", "minLength": 8, "required": True}}
        errors = validate_response_against_schema(schema, {"token": "short"})
        assert len(errors) == 1
        assert errors[0].code == "too_short"


class TestFileField:
    def test_valid_file(self) -> None:
        schema = {"logo": {
            "type": "file",
            "accept": ["image/png", "image/svg+xml"],
            "required": True,
        }}
        response = {"logo": {"asset_key": "T/.../logo.png", "content_type": "image/png"}}
        errors = validate_response_against_schema(schema, response)
        assert errors == []

    def test_file_wrong_type(self) -> None:
        schema = {"logo": {
            "type": "file",
            "accept": ["image/png"],
            "required": True,
        }}
        response = {"logo": {"asset_key": "T/.../doc.pdf", "content_type": "application/pdf"}}
        errors = validate_response_against_schema(schema, response)
        assert len(errors) == 1
        assert errors[0].code == "invalid_content_type"

    def test_file_missing_asset_key(self) -> None:
        schema = {"logo": {"type": "file", "required": True}}
        response = {"logo": {"content_type": "image/png"}}
        errors = validate_response_against_schema(schema, response)
        assert len(errors) == 1
        assert errors[0].code == "missing_key"

    def test_file_not_dict(self) -> None:
        schema = {"logo": {"type": "file", "required": True}}
        errors = validate_response_against_schema(schema, {"logo": "just-a-string"})
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"


class TestURLField:
    def test_valid_url(self) -> None:
        schema = {"website": {"type": "url", "required": True}}
        errors = validate_response_against_schema(schema, {"website": "https://example.com"})
        assert errors == []

    def test_invalid_url(self) -> None:
        schema = {"website": {"type": "url", "required": True}}
        errors = validate_response_against_schema(schema, {"website": "not-a-url"})
        assert len(errors) == 1
        assert errors[0].code == "invalid_url"

    def test_http_url_valid(self) -> None:
        schema = {"website": {"type": "url", "required": True}}
        errors = validate_response_against_schema(schema, {"website": "http://localhost:3000/api"})
        assert errors == []


class TestEmailField:
    def test_valid_email(self) -> None:
        schema = {"email": {"type": "email", "required": True}}
        errors = validate_response_against_schema(schema, {"email": "user@example.com"})
        assert errors == []

    def test_invalid_email(self) -> None:
        schema = {"email": {"type": "email", "required": True}}
        errors = validate_response_against_schema(schema, {"email": "not-an-email"})
        assert len(errors) == 1
        assert errors[0].code == "invalid_email"


class TestColorField:
    def test_valid_color(self) -> None:
        schema = {"primary": {"type": "color", "required": True}}
        errors = validate_response_against_schema(schema, {"primary": "#FF5733"})
        assert errors == []

    def test_invalid_color_no_hash(self) -> None:
        schema = {"primary": {"type": "color", "required": True}}
        errors = validate_response_against_schema(schema, {"primary": "FF5733"})
        assert len(errors) == 1
        assert errors[0].code == "invalid_color"

    def test_invalid_color_short(self) -> None:
        schema = {"primary": {"type": "color", "required": True}}
        errors = validate_response_against_schema(schema, {"primary": "#FFF"})
        assert len(errors) == 1
        assert errors[0].code == "invalid_color"


class TestEnumField:
    def test_valid_enum(self) -> None:
        schema = {"theme": {
            "type": "enum",
            "options": [
                {"value": "light", "label": "Light"},
                {"value": "dark", "label": "Dark"},
            ],
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"theme": "dark"})
        assert errors == []

    def test_invalid_enum(self) -> None:
        schema = {"theme": {
            "type": "enum",
            "options": [
                {"value": "light", "label": "Light"},
                {"value": "dark", "label": "Dark"},
            ],
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"theme": "neon"})
        assert len(errors) == 1
        assert errors[0].code == "invalid_option"

    def test_enum_simple_options(self) -> None:
        schema = {"size": {
            "type": "enum",
            "options": ["small", "medium", "large"],
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"size": "medium"})
        assert errors == []


class TestBooleanField:
    def test_valid_boolean_true(self) -> None:
        schema = {"confirmed": {"type": "boolean", "required": True}}
        errors = validate_response_against_schema(schema, {"confirmed": True})
        assert errors == []

    def test_valid_boolean_false(self) -> None:
        schema = {"confirmed": {"type": "boolean", "required": True}}
        errors = validate_response_against_schema(schema, {"confirmed": False})
        assert errors == []

    def test_boolean_type_mismatch(self) -> None:
        schema = {"confirmed": {"type": "boolean", "required": True}}
        errors = validate_response_against_schema(schema, {"confirmed": "yes"})
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"


class TestNumberField:
    def test_valid_number(self) -> None:
        schema = {"count": {"type": "number", "min": 1, "max": 100, "required": True}}
        errors = validate_response_against_schema(schema, {"count": 42})
        assert errors == []

    def test_number_below_min(self) -> None:
        schema = {"count": {"type": "number", "min": 1, "required": True}}
        errors = validate_response_against_schema(schema, {"count": 0})
        assert len(errors) == 1
        assert errors[0].code == "below_min"

    def test_number_above_max(self) -> None:
        schema = {"count": {"type": "number", "max": 100, "required": True}}
        errors = validate_response_against_schema(schema, {"count": 200})
        assert len(errors) == 1
        assert errors[0].code == "above_max"

    def test_number_float(self) -> None:
        schema = {"price": {"type": "number", "min": 0, "required": True}}
        errors = validate_response_against_schema(schema, {"price": 9.99})
        assert errors == []

    def test_number_type_mismatch(self) -> None:
        schema = {"count": {"type": "number", "required": True}}
        errors = validate_response_against_schema(schema, {"count": "42"})
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"


class TestRealWorldExamples:
    """10 real-world examples from the design doc."""

    def test_logo_image(self) -> None:
        schema = {"logo": {
            "type": "file",
            "accept": ["image/png", "image/svg+xml"],
            "maxSizeMB": 5,
            "required": True,
        }}
        response = {"logo": {"asset_key": "T/t1/P/p1/assets/logo.png", "content_type": "image/png"}}
        errors = validate_response_against_schema(schema, response)
        assert errors == []

    def test_meta_access_token(self) -> None:
        schema = {"token": {
            "type": "secret",
            "pattern": "^EAAGm0.+",
            "pattern_hint": "Starts with EAAGm0...",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"token": "EAAGm0PZBhFT4BAK3z..."})
        assert errors == []

    def test_meta_token_invalid(self) -> None:
        schema = {"token": {
            "type": "secret",
            "pattern": "^EAAGm0.+",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"token": "wrong-prefix"})
        assert len(errors) == 1

    def test_pdf_reference_doc(self) -> None:
        schema = {"document": {
            "type": "file",
            "accept": ["application/pdf"],
            "maxSizeMB": 20,
            "required": True,
        }}
        response = {"document": {"asset_key": "T/.../doc.pdf", "content_type": "application/pdf"}}
        errors = validate_response_against_schema(schema, response)
        assert errors == []

    def test_esim_phone_number(self) -> None:
        schema = {"phone": {
            "type": "string",
            "pattern": r"^\+[1-9]\d{1,14}$",
            "pattern_hint": "E.164: +5511999999999",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"phone": "+5511999999999"})
        assert errors == []

    def test_meta_business_confirmation(self) -> None:
        schema = {"confirmed": {
            "type": "boolean",
            "label": "I have configured Meta Business Manager",
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"confirmed": True})
        assert errors == []

    def test_webhook_verify_token(self) -> None:
        schema = {"token": {
            "type": "secret",
            "minLength": 8,
            "required": True,
        }}
        errors = validate_response_against_schema(schema, {"token": "my-random-verify-token"})
        assert errors == []

    def test_message_template_content(self) -> None:
        schema = {
            "body": {"type": "text", "maxLength": 1024, "required": True},
            "header": {"type": "string", "maxLength": 60, "required": False},
            "has_variables": {"type": "boolean", "required": True},
        }
        response = {
            "body": "Hello {{1}}, your order {{2}} is ready!",
            "header": "Order Update",
            "has_variables": True,
        }
        errors = validate_response_against_schema(schema, response)
        assert errors == []

    def test_brand_color_palette(self) -> None:
        schema = {
            "primary": {"type": "color", "required": True},
            "secondary": {"type": "color", "required": True},
            "accent": {"type": "color", "required": True},
        }
        response = {
            "primary": "#1A1A2E",
            "secondary": "#16213E",
            "accent": "#E94560",
        }
        errors = validate_response_against_schema(schema, response)
        assert errors == []

    def test_domain_dns_config(self) -> None:
        schema = {"domain": {"type": "url", "required": True}}
        errors = validate_response_against_schema(schema, {"domain": "https://caioo.com.br"})
        assert errors == []


class TestMultipleFieldErrors:
    def test_multiple_required_fields_missing(self) -> None:
        schema = {
            "name": {"type": "string", "required": True},
            "email": {"type": "email", "required": True},
            "age": {"type": "number", "required": True},
        }
        errors = validate_response_against_schema(schema, {})
        assert len(errors) == 3
        field_names = {e.field_name for e in errors}
        assert field_names == {"name", "email", "age"}

    def test_mixed_valid_and_invalid(self) -> None:
        schema = {
            "name": {"type": "string", "required": True},
            "email": {"type": "email", "required": True},
        }
        errors = validate_response_against_schema(schema, {"name": "Ed", "email": "bad"})
        assert len(errors) == 1
        assert errors[0].field_name == "email"

    def test_empty_string_treated_as_missing(self) -> None:
        schema = {"name": {"type": "string", "required": True}}
        errors = validate_response_against_schema(schema, {"name": ""})
        assert len(errors) == 1
        assert errors[0].code == "required"

    def test_unknown_field_type(self) -> None:
        schema = {"data": {"type": "binary", "required": True}}
        errors = validate_response_against_schema(schema, {"data": b"bytes"})
        assert len(errors) == 1
        assert errors[0].code == "unknown_type"


class TestFieldErrorSerialization:
    def test_to_dict(self) -> None:
        error = FieldError(field_name="phone", message="Invalid format", code="pattern_mismatch")
        d = error.to_dict()
        assert d == {
            "field": "phone",
            "message": "Invalid format",
            "code": "pattern_mismatch",
        }
