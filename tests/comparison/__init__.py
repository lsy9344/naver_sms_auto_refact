"""
Comparison Testing Framework

Implements parity validation between legacy and refactored Lambda implementations.
Replays production-equivalent workloads through both systems and compares outputs.
"""

__version__ = "1.0"
__all__ = [
    "ComparisonFactory",
    "OutputNormalizer",
    "DiffReporter",
    "ParityValidator",
]
