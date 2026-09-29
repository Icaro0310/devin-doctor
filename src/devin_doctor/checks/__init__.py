"""Check registry — one module per check, each exposing ``run(ctx)``.

Checks are ordered the way they appear in the report.
"""

from devin_doctor.checks import config, health, schema, stores

CHECKS = [stores, schema, health, config]

__all__ = ["CHECKS", "config", "health", "schema", "stores"]
