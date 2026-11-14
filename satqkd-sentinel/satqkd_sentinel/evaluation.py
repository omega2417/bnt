"""End-to-end evaluation framework for the telemetry analytics pipeline.

Runs the complete experiment of the article: dataset generation,
feature extraction, classifier training, and metric collection.
"""
import numpy as np
import pandas as pd
from .linkmodel import Link
from .telemetry import generate_dataset, STATES, GROUPS
from .features import extract_features, FEATURE_NAMES, QUANTUM_ONLY
from .models import (train_classifier, predict, evaluate_classifier,
                     train_novelty_detector, novelty_predict, novelty_score,
                     window_alarm, block_policy, feature_importance)


def full_evaluation(link=None, n_train=200, n_test=80, seed=42):
    """Run the complete evaluation pipeline.

    Parameters
    ----------
    link : Link or None
    n_train, n_test : int
        Number of passes for training and test sets.
    seed : int

    Returns
    -------
    dict with train_df, test_df, X_train, X_test, y_train, y_test,
    classifiers (dict of metrics per method), novelty_detectors,
    feature_importance, block_policies, alarm_results.
    """
    if link is None:
        link = Link()

    train_df = generate_dataset(link, n_train, seed=seed)
    test_df = generate_dataset(link, n_test, seed=seed + 1000)

    X_train = extract_features(train_df, link)
    X_test = extract_features(test_df, link)
    y_train = train_df['label'].values
    y_test = test_df['label'].values

    classifiers = {}
    for method in ('gradient_boosting', 'random_forest', 'logistic_regression'):
        model = train_classifier(X_train, y_train, method=method, seed=seed)
        metrics = evaluate_classifier(model, X_test, y_test)
        classifiers[method] = dict(model=model, metrics=metrics)

    best_method = max(classifiers, key=lambda m: classifiers[m]['metrics']['macro_f1'])
    best_model = classifiers[best_method]['model']
    y_pred = predict(best_model, X_test)

    novelty = {}
    nom_mask = y_train == 'nominal'
    for nd_method in ('isolation_forest', 'mahalanobis'):
        det = train_novelty_detector(X_train[nom_mask], method=nd_method, seed=seed)
        is_anom = novelty_predict(det, X_test)
        tp = ((y_test != 'nominal') & is_anom).sum()
        fn = ((y_test != 'nominal') & ~is_anom).sum()
        fp = ((y_test == 'nominal') & is_anom).sum()
        tn = ((y_test == 'nominal') & ~is_anom).sum()
        det_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        novelty[nd_method] = dict(detection_rate=det_rate, false_positive_rate=fpr,
                                  tp=int(tp), fn=int(fn), fp=int(fp), tn=int(tn))

    fi = feature_importance(best_model, X_test, y_test, n_repeats=5, seed=seed)

    alarms = window_alarm(y_pred, test_df['pass_id'].values)

    key_per_window = test_df['rate_bps'].values
    policies = {}
    for pol in ('exclude_jamming', 'exclude_all_attacks', 'exclude_all_anomalies'):
        policies[pol] = block_policy(y_pred, key_per_window, policy=pol)

    # quantum-only subset evaluation
    qi = [FEATURE_NAMES.index(f) for f in QUANTUM_ONLY]
    X_train_q = X_train[:, qi]
    X_test_q = X_test[:, qi]
    q_model = train_classifier(X_train_q, y_train, method='gradient_boosting', seed=seed)
    q_metrics = evaluate_classifier(q_model, X_test_q, y_test)

    return dict(
        train_df=train_df, test_df=test_df,
        X_train=X_train, X_test=X_test,
        y_train=y_train, y_test=y_test,
        classifiers=classifiers,
        best_method=best_method,
        novelty_detectors=novelty,
        feature_importance=fi,
        feature_names=FEATURE_NAMES,
        alarm_results=alarms,
        block_policies=policies,
        quantum_only_metrics=q_metrics,
    )


def static_threshold_baseline(X_test, y_test, percentile=99):
    """Static-threshold baseline: flag a window as anomalous if any
    feature exceeds its percentile-th value on nominal data.

    Returns
    -------
    dict with detection_rate and false_positive_rate.
    """
    nom = y_test == 'nominal'
    thresholds_hi = np.percentile(X_test[nom], percentile, axis=0)
    thresholds_lo = np.percentile(X_test[nom], 100 - percentile, axis=0)
    flagged = np.any((X_test > thresholds_hi) | (X_test < thresholds_lo), axis=1)

    tp = ((y_test != 'nominal') & flagged).sum()
    fn = ((y_test != 'nominal') & ~flagged).sum()
    fp = ((y_test == 'nominal') & flagged).sum()
    tn = ((y_test == 'nominal') & ~flagged).sum()
    return dict(
        detection_rate=tp / (tp + fn) if (tp + fn) > 0 else 0,
        false_positive_rate=fp / (fp + tn) if (fp + tn) > 0 else 0,
    )


def leave_one_attack_out(X_train, y_train, X_test, y_test, seed=42):
    """Leave-one-attack-out: train without each attack type, evaluate on it.

    Returns
    -------
    dict mapping attack name to macro_f1 on the held-out attack windows.
    """
    attacks = [s for s in STATES if GROUPS[s] == 'attack']
    results = {}
    for held_out in attacks:
        mask_train = y_train != held_out
        model = train_classifier(X_train[mask_train], y_train[mask_train],
                                 method='gradient_boosting', seed=seed)
        mask_test = (y_test == held_out) | (y_test == 'nominal')
        if mask_test.sum() == 0:
            continue
        y_pred = predict(model, X_test[mask_test])
        is_detected = (y_pred != 'nominal')
        actual_anom = (y_test[mask_test] != 'nominal')
        recall = (is_detected & actual_anom).sum() / actual_anom.sum() if actual_anom.sum() > 0 else 0
        results[held_out] = dict(recall=float(recall), n_test=int(mask_test.sum()))
    return results


def shifted_hardware_evaluation(link_shifted, clf_model, link_orig=None, n_test=80, seed=42):
    """Evaluate a trained classifier on data from shifted hardware.

    Parameters
    ----------
    link_shifted : Link
        Hardware parameters after shift.
    clf_model : dict
        Trained classifier model dict.
    link_orig : Link or None
        Original link for feature extraction reference.
    n_test : int
    seed : int

    Returns
    -------
    dict with metrics on shifted data.
    """
    if link_orig is None:
        link_orig = Link()
    test_df = generate_dataset(link_shifted, n_test, seed=seed + 5000)
    X_test = extract_features(test_df, link_orig)
    y_test = test_df['label'].values
    return evaluate_classifier(clf_model, X_test, y_test)


def summary_table(results):
    """Format evaluation results as a summary DataFrame (Table 6 analogue)."""
    rows = []
    for method, data in results['classifiers'].items():
        m = data['metrics']
        rows.append(dict(
            method=method,
            macro_f1=m['macro_f1'],
            accuracy=m['accuracy'],
            **{f'f1_{k}': v for k, v in m['per_class_f1'].items()},
        ))
    return pd.DataFrame(rows)
