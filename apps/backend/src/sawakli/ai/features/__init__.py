"""Stable public contract for AI-01 data access and feature engineering."""

from .engineering import ROLLING_WINDOWS, engineer_features
from .loaders import CsvDataLoader, DatabaseDataLoader, DataLoader, local_campaign_id
from .metrics import safe_divide
from .schemas import FeatureDataError, FeatureRecord, MetricRecord

__all__ = [
    "ROLLING_WINDOWS",
    "CsvDataLoader",
    "DataLoader",
    "DatabaseDataLoader",
    "FeatureDataError",
    "FeatureRecord",
    "MetricRecord",
    "engineer_features",
    "local_campaign_id",
    "safe_divide",
]
