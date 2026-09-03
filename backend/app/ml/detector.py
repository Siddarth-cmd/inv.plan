"""
Isolation Forest Anomaly Detector.

Trains on real transaction features (from features.py).
Scores are normalized from raw IF scores to [0, 1] range.
MODEL SCORE and BUSINESS RISK SCORE are kept strictly separate.

Persists model to disk for reproducibility.
"""
from __future__ import annotations

import os
import pickle
from typing import Optional

import numpy as np
import pandas as pd
import structlog

from app.core.config import get_settings
from app.ml.features import build_features, FEATURE_COLUMNS

logger = structlog.get_logger("finspectra.ml.detector")
settings = get_settings()


class IsolationForestDetector:
    """
    Isolation Forest anomaly detector for transaction data.
    
    Scores are normalized to [0, 1] where:
      ~1.0 = most anomalous (highest IF isolation score)
      ~0.0 = most normal (lowest isolation score)
    
    This is the MODEL SCORE. Business risk scoring is done separately.
    """

    MODEL_FILENAME = "isolation_forest.pkl"
    SCALER_FILENAME = "scaler.pkl"
    META_FILENAME = "model_meta.pkl"

    def __init__(self) -> None:
        self._model = None
        self._scaler = None
        self._meta: dict = {}
        self._model_dir = settings.ml_models_dir
        os.makedirs(self._model_dir, exist_ok=True)

    def _model_path(self, filename: str) -> str:
        return os.path.join(self._model_dir, filename)

    def train(self, transactions_df: pd.DataFrame, contamination: float = 0.1) -> dict:
        """
        Train the Isolation Forest on transaction features.
        
        Args:
            transactions_df: DataFrame with columns required by build_features()
            contamination: Expected fraction of outliers (default: 10%)
        
        Returns:
            Training metadata (not fake scores — actual model params).
        """
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        if len(transactions_df) < 10:
            raise ValueError(f"Need at least 10 transactions to train, got {len(transactions_df)}")

        logger.info("Building features for IF training", rows=len(transactions_df))
        features_df = build_features(transactions_df)
        X = features_df[FEATURE_COLUMNS].fillna(0).values.astype(np.float64)

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train Isolation Forest
        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_scaled)

        self._model = model
        self._scaler = scaler

        # Compute training scores for metadata
        raw_scores = model.score_samples(X_scaled)  # negative: lower = more anomalous
        self._meta = {
            "trained_on": len(transactions_df),
            "n_features": len(FEATURE_COLUMNS),
            "feature_columns": FEATURE_COLUMNS,
            "contamination": contamination,
            "raw_score_min": float(raw_scores.min()),
            "raw_score_max": float(raw_scores.max()),
            "raw_score_mean": float(raw_scores.mean()),
            "n_estimators": 100,
            "random_state": 42,
        }

        # Save to disk
        self._save()
        logger.info("IF model trained and saved", **self._meta)
        return self._meta

    def score(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score transactions with anomaly probability.
        
        Returns DataFrame with columns:
          id, model_anomaly_score (0–1, higher = more anomalous), is_anomaly
        
        model_anomaly_score is the normalized MODEL SCORE.
        It is distinct from the business risk score (computed elsewhere).
        """
        if self._model is None:
            self._load()
        if self._model is None:
            raise RuntimeError("Model not trained — call train() first or ensure model exists")

        features_df = build_features(transactions_df)
        X = features_df[FEATURE_COLUMNS].fillna(0).values.astype(np.float64)
        X_scaled = self._scaler.transform(X)

        raw_scores = self._model.score_samples(X_scaled)  # negative, lower = worse
        predictions = self._model.predict(X_scaled)  # -1 = anomaly, 1 = normal

        # Normalize: raw_scores are negative, range [raw_min, raw_max]
        # Map to [0, 1] where 1 = most anomalous
        raw_min = self._meta.get("raw_score_min", raw_scores.min())
        raw_max = self._meta.get("raw_score_max", raw_scores.max())
        score_range = max(raw_max - raw_min, 1e-6)
        normalized = 1.0 - (raw_scores - raw_min) / score_range  # invert so high = anomalous
        normalized = np.clip(normalized, 0.0, 1.0)

        result = pd.DataFrame({
            "id": features_df["id"].values,
            "model_anomaly_score": normalized,
            "is_anomaly": predictions == -1,
        })
        return result

    def _save(self) -> None:
        with open(self._model_path(self.MODEL_FILENAME), "wb") as f:
            pickle.dump(self._model, f)
        with open(self._model_path(self.SCALER_FILENAME), "wb") as f:
            pickle.dump(self._scaler, f)
        with open(self._model_path(self.META_FILENAME), "wb") as f:
            pickle.dump(self._meta, f)

    def _load(self) -> None:
        try:
            with open(self._model_path(self.MODEL_FILENAME), "rb") as f:
                self._model = pickle.load(f)
            with open(self._model_path(self.SCALER_FILENAME), "rb") as f:
                self._scaler = pickle.load(f)
            with open(self._model_path(self.META_FILENAME), "rb") as f:
                self._meta = pickle.load(f)
            logger.info("IF model loaded from disk", meta=self._meta)
        except FileNotFoundError:
            logger.warning("No trained model found — train() must be called first")

    def is_trained(self) -> bool:
        return os.path.exists(self._model_path(self.MODEL_FILENAME))
