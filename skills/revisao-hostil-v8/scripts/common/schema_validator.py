"""Validador de contratos JSON para a Revisão Hostil v8.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

DEFAULT_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "references" / "schemas"


class SchemaValidationError(ValueError):
    """Erro levantado quando um documento viola um contrato JSON."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        message = f"Falha na validação contra {schema_name}: " + "; ".join(errors)
        super().__init__(message)


class SchemaValidator:
    """Carrega e valida documentos contra os JSON Schemas locais em references/schemas/."""

    def __init__(self, schemas_dir: Path | str | None = None) -> None:
        self.schemas_dir = Path(schemas_dir) if schemas_dir else DEFAULT_SCHEMAS_DIR
        self._schemas: dict[str, dict[str, Any]] = {}
        self._registry = self._build_registry()

    def _build_registry(self) -> Registry:
        registry = Registry()
        if not self.schemas_dir.exists():
            return registry
        for path in sorted(self.schemas_dir.glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self._schemas[path.name] = schema
            resource = Resource.from_contents(schema)
            if "$id" in schema:
                registry = registry.with_resource(schema["$id"], resource)
            registry = registry.with_resource(path.name, resource)
        return registry

    def get_schema(self, schema_name: str) -> dict[str, Any]:
        if schema_name not in self._schemas:
            raise FileNotFoundError(f"Schema não encontrado: {schema_name} em {self.schemas_dir}")
        return self._schemas[schema_name]

    def validate(self, instance: Any, schema_name: str) -> list[str]:
        """Retorna lista de erros (vazia se válido)."""
        schema = self.get_schema(schema_name)
        validator = Draft202012Validator(schema, registry=self._registry)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        formatted: list[str] = []
        for err in errors:
            path = ".".join(str(p) for p in err.path) or "<root>"
            formatted.append(f"{path}: {err.message}")
        return formatted

    def assert_valid(self, instance: Any, schema_name: str) -> None:
        """Levanta SchemaValidationError se houver qualquer violação."""
        errors = self.validate(instance, schema_name)
        if errors:
            raise SchemaValidationError(schema_name, errors)


_DEFAULT_VALIDATOR: SchemaValidator | None = None


def validate_contract(instance: Any, schema_name: str, raise_on_error: bool = True) -> list[str]:
    """Atalho para validar um documento contra um contrato JSON da v8.0."""
    global _DEFAULT_VALIDATOR
    if _DEFAULT_VALIDATOR is None:
        _DEFAULT_VALIDATOR = SchemaValidator()
    if raise_on_error:
        _DEFAULT_VALIDATOR.assert_valid(instance, schema_name)
        return []
    return _DEFAULT_VALIDATOR.validate(instance, schema_name)
