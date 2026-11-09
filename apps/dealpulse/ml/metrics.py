"""Model evaluation metrics, dependency-light so they run inside the SageMaker container and in tests."""
from __future__ import annotations

import numpy as np


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """Area under the ROC curve (probability a random winner scores above a random loser; ties count half)."""
    y = np.asarray(y, dtype=float)
    score = np.asarray(score, dtype=float)
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    sorted_scores = score[order]
    i = 0
    while i < len(score):  # average ranks for ties
        j = i
        while j + 1 < len(score) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = y.sum()
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    """Mean squared error of probabilities (lower is better; 0.25 = always guessing 50%)."""
    return float(np.mean((np.asarray(prob, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def calibration_table(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> list[dict]:
    """Rows of {bin, n, mean_predicted, observed_rate} for equal-width probability bins."""
    y = np.asarray(y, dtype=float)
    prob = np.asarray(prob, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for k in range(bins):
        mask = (prob >= edges[k]) & ((prob < edges[k + 1]) if k < bins - 1 else (prob <= edges[k + 1]))
        n = int(mask.sum())
        rows.append({
            "bin": f"{edges[k]:.1f}–{edges[k + 1]:.1f}", "n": n,
            "mean_predicted": float(prob[mask].mean()) if n else None,
            "observed_rate": float(y[mask].mean()) if n else None,
        })
    return rows
