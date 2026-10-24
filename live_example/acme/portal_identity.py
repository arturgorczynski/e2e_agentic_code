"""Compatibility entry point for the portal's demo persona selector.

The shared identity implementation lives in :mod:`acme.demo_identity` so the
agent runtime never needs to import a web module.
"""

from acme.demo_identity import (
    DEPARTMENT_SCOPE,
    SCHEMA,
    initialize,
    kind_for_actor,
    persona,
    select,
)

__all__ = ["DEPARTMENT_SCOPE", "SCHEMA", "initialize", "kind_for_actor", "persona", "select"]
