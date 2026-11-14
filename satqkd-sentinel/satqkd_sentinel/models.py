"""ML classifiers and novelty detectors for QKD telemetry.

Gradient boosting, random forest, logistic regression (multi-class);
isolation forest and Mahalanobis distance (novelty detection).
"""
import numpy as np
from sklearn.ensemble import (GradientBoostingClassifier, RandomForestClassifier,
                              IsolationForest)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (f1_score, classification_report, confusion_matrix,
                             accuracy_score, precision_recall_fscore_support)
from sklearn.preprocessing import StandardScaler
from sklearn.inspection import permutation_importance as _perm_importance


def train_classifier(X_train, y_train, method='gradient_boosting', seed=42):
    """Train a multi-class classifier.

    Parameters
    ----------
    X_train : array-like, shape (n, 24)
    y_train : array-like, shape (n,)
    method : str
        One of 'gradient_boosting', 'random_forest', 'logistic_regression'.
    seed : int

    Returns
    -------
    dict with keys 'clf', 'scaler', 'method'.
    """
    scaler = StandardScaler().fit(X_train)
    Xs = scaler.transform(X_train)

    if method == 'gradient_boosting':
        clf = GradientBoostingClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            subsample=0.8, random_state=seed)
    elif method == 'random_forest':
        clf = RandomForestClassifier(
            n_estimators=200, max_depth=12, random_state=seed, n_jobs=-1)
    elif method == 'logistic_regression':
        clf = LogisticRegression(
            max_iter=1000, random_state=seed, C=1.0, solver='lbfgs')
    else:
        raise ValueError(f"Unknown method: {method}")

    clf.fit(Xs, y_train)
    return dict(clf=clf, scaler=scaler, method=method)


def predict(model, X):
    """Predict labels using a trained model dict."""
    return model['clf'].predict(model['scaler'].transform(X))


def predict_proba(model, X):
    """Predict class probabilities."""
    return model['clf'].predict_proba(model['scaler'].transform(X))


def train_novelty_detector(X_nominal, method='isolation_forest', seed=42):
    """Train a novelty detector on nominal-only data.

    Parameters
    ----------
    X_nominal : array-like
        Feature matrix of nominal windows.
    method : str
        'isolation_forest' or 'mahalanobis'.

    Returns
    -------
    dict with detector info.
    """
    scaler = StandardScaler().fit(X_nominal)
    Xs = scaler.transform(X_nominal)

    if method == 'isolation_forest':
        det = IsolationForest(n_estimators=200, contamination=0.01,
                              random_state=seed)
        det.fit(Xs)
        return dict(detector=det, scaler=scaler, method=method)
    elif method == 'mahalanobis':
        mu = Xs.mean(axis=0)
        cov = np.cov(Xs, rowvar=False)
        cov += 1e-6 * np.eye(cov.shape[0])
        cov_inv = np.linalg.inv(cov)
        return dict(mu=mu, cov_inv=cov_inv, scaler=scaler, method=method)
    else:
        raise ValueError(f"Unknown method: {method}")


def novelty_score(model, X):
    """Compute anomaly scores (higher = more anomalous)."""
    Xs = model['scaler'].transform(X)
    if model['method'] == 'isolation_forest':
        return -model['detector'].score_samples(Xs)
    elif model['method'] == 'mahalanobis':
        diff = Xs - model['mu']
        return np.sqrt(np.sum(diff @ model['cov_inv'] * diff, axis=1))


def novelty_predict(model, X, threshold=None):
    """Binary anomaly prediction. Returns True for anomalies."""
    scores = novelty_score(model, X)
    if threshold is None:
        if model['method'] == 'isolation_forest':
            return model['detector'].predict(model['scaler'].transform(X)) == -1
        else:
            threshold = np.percentile(scores, 99)
    return scores > threshold


def evaluate_classifier(clf_model, X_test, y_test):
    """Compute classification metrics.

    Returns
    -------
    dict with macro_f1, accuracy, per_class_f1, confusion_matrix,
    classification_report.
    """
    y_pred = predict(clf_model, X_test)
    labels = sorted(set(y_test) | set(y_pred))

    macro_f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
    acc = accuracy_score(y_test, y_pred)
    prec, rec, f1, sup = precision_recall_fscore_support(
        y_test, y_pred, labels=labels, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    report = classification_report(y_test, y_pred, labels=labels, zero_division=0)

    return dict(
        macro_f1=macro_f1,
        accuracy=acc,
        per_class_f1=dict(zip(labels, f1.tolist())),
        per_class_precision=dict(zip(labels, prec.tolist())),
        per_class_recall=dict(zip(labels, rec.tolist())),
        support=dict(zip(labels, sup.tolist())),
        confusion_matrix=cm,
        labels=labels,
        classification_report=report,
        y_pred=y_pred,
    )


def window_alarm(predictions, pass_ids, threshold_consecutive=3):
    """Flag passes where >= threshold consecutive anomalous windows occur.

    Parameters
    ----------
    predictions : array-like of str
        Predicted label per window.
    pass_ids : array-like
        Pass identifier per window.
    threshold_consecutive : int

    Returns
    -------
    dict mapping pass_id to (flagged: bool, max_run: int, dominant_label: str).
    """
    results = {}
    for pid in np.unique(pass_ids):
        mask = pass_ids == pid
        preds = np.array(predictions)[mask]
        anom = preds != 'nominal'

        max_run = 0
        run = 0
        for a in anom:
            run = run + 1 if a else 0
            max_run = max(max_run, run)

        from collections import Counter
        anom_preds = preds[anom]
        dominant = Counter(anom_preds).most_common(1)[0][0] if len(anom_preds) > 0 else 'nominal'

        results[pid] = dict(flagged=max_run >= threshold_consecutive,
                            max_run=max_run, dominant_label=dominant)
    return results


def block_policy(predictions, key_per_window, policy='exclude_jamming'):
    """Compute key yield under a block policy.

    Parameters
    ----------
    predictions : array-like of str
    key_per_window : array-like of float
        Key bits generated per window.
    policy : str
        'exclude_jamming': exclude windows classified as optical_jamming.
        'exclude_all_attacks': exclude all attack-classified windows.
        'exclude_all_anomalies': exclude everything not nominal.

    Returns
    -------
    dict with total_key, excluded_key, retained_fraction.
    """
    preds = np.asarray(predictions)
    key = np.asarray(key_per_window, dtype=float)
    total = key.sum()

    if policy == 'exclude_jamming':
        keep = preds != 'optical_jamming'
    elif policy == 'exclude_all_attacks':
        from .telemetry import GROUPS
        keep = np.array([GROUPS.get(p, 'nominal') != 'attack' for p in preds])
    elif policy == 'exclude_all_anomalies':
        keep = preds == 'nominal'
    else:
        raise ValueError(f"Unknown policy: {policy}")

    retained = key[keep].sum()
    return dict(total_key=float(total), retained_key=float(retained),
                excluded_key=float(total - retained),
                retained_fraction=float(retained / total) if total > 0 else 1.0)


def feature_importance(clf_model, X_test, y_test, n_repeats=10, seed=42):
    """Permutation-based feature importance.

    Returns
    -------
    dict with importances_mean, importances_std (arrays of length n_features).
    """
    Xs = clf_model['scaler'].transform(X_test)
    result = _perm_importance(clf_model['clf'], Xs, y_test,
                              n_repeats=n_repeats, random_state=seed,
                              scoring='f1_macro')
    return dict(importances_mean=result.importances_mean,
                importances_std=result.importances_std)
