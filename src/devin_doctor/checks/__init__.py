"""Check registry — one module per check, each exposing ``run(ctx)``.

Checks are ordered the way they appear in the report.
"""

from devin_doctor.checks import schema, stores

CHECKS = [stores, schema]

__all__ = ["CHECKS", "schema", "stores"]
