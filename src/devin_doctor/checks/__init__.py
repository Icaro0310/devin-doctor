"""Check registry — one module per check, each exposing ``run(ctx)``.

Checks are ordered the way they appear in the report.
"""

from devin_doctor.checks import health, schema, stores

CHECKS = [stores, schema, health]

__all__ = ["CHECKS", "health", "schema", "stores"]
