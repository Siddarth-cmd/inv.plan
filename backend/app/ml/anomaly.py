"""
Isolation Forest anomaly detection for financial transactions.

Design notes:
- MODEL SCORE: Raw Isolation Forest anomaly score (lower = more anomalous in sklearn)
- NORMALIZED SCORE: Transformed to [0, 1] where 1 = most anomalous
- BUSINESS RISK SCORE: Calculated separately by combining model + rule signals

These three are kept distinct and never conflated.
"""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.ml.features import build_features, get_feature_columns


MODEL_DIR = Path("backend/app/ml/models")


@dataclass
class AnomalyResult:
    transaction_id: str
    model_score: float          # Raw sklearn score (negative = anomalous)
    normalized_score: float     # [0, 1] — 1 is most suspicious
    is_anomaly: bool            # Based on model threshold
    feature_values: dict[str, float]


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector for financial transactions.

    The model is trained on ingested transaction data and produces
    normalized anomaly scores. Scores are NOT directly business risk scores.
    """

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100, random_state: int = 42):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_columns = get_feature_columns()
        self.is_trained = False
        self._score_min: float = -1.0
        self._score_max: float = 1.0

    def fit(self, transactions_df: pd.DataFrame) -> dict:
        """
        Train the Isolation Forest on transaction features.

        Returns metadata about the training run.
        """
        if len(transactions_df) < 10:
            raise ValueError("Need at least 10 transactions to train the anomaly model.")

        features_df = build_features(transactions_df)
        X = features_df[self.feature_columns].values

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)

        # Compute score range for normalization
        raw_scores = self.model.score_samples(X_scaled)
        self._score_min = float(raw_scores.min())
        self._score_max = float(raw_scores.max())

        self.is_trained = True

        n_anomalies = int((self.model.predict(X_scaled) == -1).sum())
        return {
            "n_samples": len(transactions_df),
            "n_features": len(self.feature_columns),
            "contamination": self.contamination,
            "n_anomalies_detected": n_anomalies,
            "anomaly_rate": n_anomalies / len(transactions_df),
            "score_range": [self._score_min, self._score_max],
        }

    def score_transactions(self, transactions_df: pd.DataFrame) -> list[AnomalyResult]:
        """
        Score a set of transactions.
        Returns AnomalyResult for each transaction.
        """
        if not self.is_trained or self.model is None or self.scaler is None:
            raise RuntimeError("Model must be trained before scoring.")

        features_df = build_features(transactions_df)
        X = features_df[self.feature_columns].values
        X_scaled = self.scaler.transform(X)

        raw_scores = self.model.score_samples(X_scaled)
        predictions = self.model.predict(X_scaled)

        results = []
        for i, (_, row) in enumerate(features_df.iterrows()):
            raw = float(raw_scores[i])
            normalized = self._normalize_score(raw)
            results.append(AnomalyResult(
                transaction_id=str(row["id"]),
                model_score=raw,
                normalized_score=normalized,
                is_anomaly=predictions[i] == -1,
                feature_values={col: float(row[col]) for col in self.feature_columns},
            ))

        return results

    def _normalize_score(self, raw_score: float) -> float:
        """
        Normalize Isolation Forest score to [0, 1].

        Sklearn's score_samples returns negative values for anomalies.
        Lower raw score = more anomalous.
        We invert so that 1.0 = most anomalous.

        Transformation:
            normalized = 1 - (raw - min) / (max - min)
            clipped to [0, 1]
        """
        score_range = self._score_max - self._score_min
        if score_range < 1e-9:
            return 0.5
        normalized = 1.0 - (raw_score - self._score_min) / score_range
        return float(np.clip(normalized, 0.0, 1.0))

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist model and scaler to disk."""
        if path is None:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            path = MODEL_DIR / "isolation_forest.pkl"

        state = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_columns": self.feature_columns,
            "contamination": self.contamination,
            "is_trained": self.is_trained,
            "score_min": self._score_min,
            "score_max": self._score_max,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AnomalyDetector":
        """Load a persisted model from disk."""
        if path is None:
            path = MODEL_DIR / "isolation_forest.pkl"

        if not path.exists():
            raise FileNotFoundError(f"No model found at {path}")

        with open(path, "rb") as f:
            state = pickle.load(f)

        detector = cls()
        detector.model = state["model"]
        detector.scaler = state["scaler"]
        detector.feature_columns = state["feature_columns"]
        detector.contamination = state["contamination"]
        detector.is_trained = state["is_trained"]
        detector._score_min = state["score_min"]
        detector._score_max = state["score_max"]
        return detector


# Module-level singleton (loaded lazily)
_detector: Optional[AnomalyDetector] = None


def get_detector() -> AnomalyDetector:
    """Get the module-level detector, loading from disk if available."""
    global _detector
    if _detector is None:
        try:
            _detector = AnomalyDetector.load()
        except FileNotFoundError:
            _detector = AnomalyDetector()
    return _detector


def reset_detector() -> None:
    """Reset the module-level detector (used in testing)."""
    global _detector
    _detector = None
