"""Strict Pydantic base model for the entire codebase.

All domain models should inherit from ``StrictBase`` instead of
``pydantic.BaseModel`` so that extra fields are rejected at validation
time, defaults are always validated, and instances are re-validated
whenever they are passed into another model.

Note: ``strict=True`` is intentionally **not** enabled because the
codebase relies on ``model_dump()`` / ``model_validate()`` round-trips
(e.g. in dashboard routers and tests) which would break under strict
mode.
"""

from pydantic import BaseModel, ConfigDict


class StrictBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
    )
