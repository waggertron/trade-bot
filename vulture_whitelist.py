"""Vulture whitelist — known false positives."""

# Pydantic model_post_init context parameter (required by Pydantic signature)
__context  # noqa: F821
