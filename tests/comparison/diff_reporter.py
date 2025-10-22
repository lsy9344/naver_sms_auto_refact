"""Backward compatible import shim for DiffReporter."""

from src.comparison.diff_reporter import ComparisonMismatch, DiffReporter

__all__ = ["ComparisonMismatch", "DiffReporter"]
