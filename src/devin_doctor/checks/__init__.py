"""Check registry — one module per check, each exposing ``run(ctx)``.

Checks are ordered the way they appear in the report.
"""

from devin_doctor.checks import config, disk, health, schema, stores

CHECKS = [stores, schema, health, config, disk]

__all__ = ["CHECKS", "config", "disk", "health", "schema", "stores"]
