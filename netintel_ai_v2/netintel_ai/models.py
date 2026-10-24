from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .features import FEATURE_COLUMNS


@dataclass
class ModelBundle:
    name: str
    pipeline: object


def build_models(contamination: float = 0.05) -> dict[str, ModelBundle]:
    return {
        "isolation_forest": ModelBundle(
            "isolation_forest",
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", IsolationForest(
                    n_estimators=300,
                    contamination=contamination,
                    random_state=42,
                    n_jobs=-1,
                )),
            ]),
        ),
        "one_class_svm": ModelBundle(
            "one_class_svm",
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", OneClassSVM(
                    kernel="rbf",
                    gamma="scale",
                    nu=max(min(contamination, 0.5), 0.001),
                )),
            ]),
        ),
        "lof": ModelBundle(
            "lof",
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", LocalOutlierFactor(
                    n_neighbors=10,
                    contamination=contamination,
                    novelty=True,
                )),
            ]),
        ),
    }


def fit_models(baseline: pd.DataFrame, contamination: float = 0.05) -> dict[str, ModelBundle]:
    if len(baseline) < 10:
        raise ValueError("Baseline minimal 10 windows diperlukan untuk training model.")

    X = baseline[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    models = build_models(contamination)

    for bundle in models.values():
        bundle.pipeline.fit(X)

    return models


def score_models(models: dict[str, ModelBundle], features: pd.DataFrame) -> pd.DataFrame:
    X = features[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    result = features.copy()

    predictions = []
    scores = []

    for name, bundle in models.items():
        pred = bundle.pipeline.predict(X)
        score = bundle.pipeline.decision_function(X)
        result[f"{name}_prediction"] = pred
        result[f"{name}_score"] = score
        predictions.append(pred)
        scores.append(score)

    pred_matrix = np.column_stack(predictions)
    score_matrix = np.column_stack(scores)

    result["ensemble_votes"] = (pred_matrix == -1).sum(axis=1)
    result["ensemble_score"] = score_matrix.mean(axis=1)
    result["status"] = np.where(
        result["ensemble_votes"] >= 2,
        "ANOMALY",
        "NORMAL",
    )

    return result


def validate_labeled_dataset(
    models: dict[str, ModelBundle],
    dataset: pd.DataFrame,
    label_column: str = "label",
) -> pd.DataFrame:
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        roc_auc_score,
    )

    if label_column not in dataset.columns:
        raise ValueError(f"Kolom '{label_column}' tidak ditemukan.")

    y = dataset[label_column].astype(int)
    X = dataset[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    rows = []

    for name, bundle in models.items():
        pred = bundle.pipeline.predict(X)
        pred01 = (pred == -1).astype(int)
        true01 = (y == -1).astype(int)

        try:
            score = bundle.pipeline.decision_function(X)
            auc = roc_auc_score(true01, -score)
        except ValueError:
            auc = float("nan")

        rows.append({
            "model": name,
            "accuracy": accuracy_score(true01, pred01),
            "precision": precision_score(true01, pred01, zero_division=0),
            "recall": recall_score(true01, pred01, zero_division=0),
            "f1": f1_score(true01, pred01, zero_division=0),
            "roc_auc": auc,
        })

    return pd.DataFrame(rows)
