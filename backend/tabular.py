"""One switch for the in-context tabular model. TAB_BACKEND = tabicl (default) | tabfm | gbm.

TabICL and TabFM share the scikit-learn interface: fit() stores the context rows, predict() runs a
forward pass. No training, so new rows (a new survey wave, yesterday's sales) are used at once.
"""
import os
import warnings

warnings.filterwarnings("ignore")
BACKEND = os.environ.get("TAB_BACKEND", "tabicl")
N_EST = int(os.environ.get("TAB_ESTIMATORS", "4"))          # ensemble members; fewer is faster
DEVICE = os.environ.get("TAB_DEVICE") or None   # e.g. cpu; default lets the library choose (MPS on Apple silicon)


def classifier():
    if BACKEND == "tabfm":  # needs the 6 GB classification weights from google/tabfm-1.0.0-jax
        from tabfm import TabFMClassifier, tabfm_v1_0_0_jax
        return TabFMClassifier(model=tabfm_v1_0_0_jax.load(), max_num_rows=2000, n_estimators=4)
    if BACKEND == "tabicl":
        from tabicl import TabICLClassifier
        return TabICLClassifier(n_estimators=N_EST, device=DEVICE)
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06)


def regressor():
    if BACKEND == "tabfm":
        from tabfm import TabFMRegressor, tabfm_v1_0_0_jax
        return TabFMRegressor(model=tabfm_v1_0_0_jax.load(model_type="regression"), max_num_rows=2000, n_estimators=4)
    if BACKEND == "tabicl":
        from tabicl import TabICLRegressor
        return TabICLRegressor(n_estimators=N_EST, device=DEVICE)
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05)


def describe() -> dict:
    version = "n/a"
    try:
        import importlib.metadata as md
        version = md.version("tabicl" if BACKEND == "tabicl" else "tabfm" if BACKEND == "tabfm" else "scikit-learn")
    except Exception:
        pass
    return {"backend": BACKEND, "version": version}
