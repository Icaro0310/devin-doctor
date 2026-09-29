"""Check registry — one module per check, each exposing ``run(ctx)``.

Checks are ordered the way they appear in the report.
"""

from devin_doctor.checks import stores

CHECKS = [stores]

__all__ = ["CHECKS", "stores"]
