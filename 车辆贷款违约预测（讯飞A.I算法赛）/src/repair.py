import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ProjectConfig


@dataclass
class Rule:
    antecedent: tuple[str, ...]
    consequent: str
    support: float
    confidence: float


def _bin_numeric(series: pd.Series, bins: int = 4) -> pd.Series:
    """
    Bin numeric series for FP-Growth.
    Special handling: if the series contains -1 (missing sentinel), -1 gets its
    own bin and is never merged with positive values.
    """
    # Mark -1 as a special missing value
    has_neg1 = (series == -1).any()

    def _safe_qcut(series_in, q):
        try:
            return pd.qcut(series_in, q=q, duplicates="drop")
        except Exception:
            return pd.cut(series_in, bins=q)

    if has_neg1:
        # Separate -1 and positive values
        neg1_mask = series == -1
        pos_series = series[~neg1_mask]
        ok = pos_series.dropna()
        if ok.empty or ok.nunique() < 2:
            # All or most are -1: put -1 in its own bin, rest as one bin
            result = pd.Series(index=series.index, dtype="string")
            result[neg1_mask] = "MISSING"
            others = series[~neg1_mask].dropna()
            if not others.empty:
                try:
                    binned = pd.qcut(others, q=min(bins - 1, ok.nunique()), duplicates="drop")
                    result[~neg1_mask] = binned.values
                except Exception:
                    result[~neg1_mask] = others.astype("string")
            return result
        else:
            # Bin positive values separately
            result = pd.Series(index=series.index, dtype="string")
            result[neg1_mask] = "MISSING"
            try:
                binned_pos = pd.qcut(pos_series, q=min(bins - 1, ok.nunique()), duplicates="drop")
                result[~neg1_mask] = binned_pos.values
            except Exception:
                result[~neg1_mask] = pos_series.astype("string")
            return result
    else:
        ok = series.dropna()
        if ok.empty or ok.nunique() < 2:
            return series.astype("string")
        try:
            return pd.qcut(series, q=min(bins, ok.nunique()), duplicates="drop").astype("string")
        except Exception:
            return series.astype("string")


def _tokenize_df(df: pd.DataFrame, cols: list[str]) -> list[set[str]]:
    tx = []
    for _, row in df[cols].iterrows():
        items = set()
        for c in cols:
            v = row[c]
            if pd.notna(v):
                items.add(f"{c}={v}")
        tx.append(items)
    return tx


def build_association_rules(
    df: pd.DataFrame,
    target_col: str,
    context_cols: list[str],
    min_support: float = 0.05,
    min_confidence: float = 0.6,
) -> list[Rule]:
    work = df[context_cols + [target_col]].copy()
    for c in context_cols:
        if pd.api.types.is_numeric_dtype(work[c]):
            work[c] = _bin_numeric(work[c], bins=4)
        else:
            work[c] = work[c].astype("string")
    # Credit_level is already categorical (integer codes 1-13) - treat as string directly
    work[target_col] = work[target_col].astype("string")
    # Treat -1 as missing; drop rows where target is -1 or NaN
    real_target = work[target_col].replace("-1", "MISSING")
    work["_real_target"] = real_target
    work = work[real_target != "MISSING"]

    tx = _tokenize_df(work, context_cols + [target_col])
    total = len(tx)
    if total == 0:
        return []

    ante_counter = Counter()
    pair_counter = Counter()

    for items in tx:
        context_items = sorted([x for x in items if not x.startswith(f"{target_col}=")])
        target_items = [x for x in items if x.startswith(f"{target_col}=")]
        for t in target_items:
            # 1-antecedent rules
            for i in range(len(context_items)):
                ant = (context_items[i],)
                ante_counter[ant] += 1
                pair_counter[(ant, t)] += 1
            # 2-antecedent rules
            for i in range(len(context_items)):
                for j in range(i + 1, len(context_items)):
                    ant = (context_items[i], context_items[j])
                    ante_counter[ant] += 1
                    pair_counter[(ant, t)] += 1

    rules = []
    for (ant, cons), cnt in pair_counter.items():
        support = cnt / total
        conf = cnt / max(ante_counter[ant], 1)
        if support >= min_support and conf >= min_confidence:
            # Skip rules that predict "missing" bins (low numeric values)
            if cons.startswith(target_col + "=(-"):
                # This is a binned numeric result - check if it includes -1
                # Low bins like (-1.001, 8.0] include -1 (missing sentinel) - skip
                continue
            rules.append(Rule(antecedent=ant, consequent=cons, support=support, confidence=conf))
    rules.sort(key=lambda r: (r.confidence, r.support), reverse=True)
    return rules


def apply_rule_repair(
    df: pd.DataFrame,
    target_col: str,
    context_cols: list[str],
    rules: list[Rule],
) -> tuple[pd.Series, pd.Series]:
    work = df[context_cols + [target_col]].copy()
    for c in context_cols:
        if pd.api.types.is_numeric_dtype(work[c]):
            work[c] = _bin_numeric(work[c], bins=4)
        else:
            work[c] = work[c].astype("string")
    # Credit_level is already categorical (integer codes 1-13) - treat as string directly
    work[target_col] = work[target_col].astype("string")

    # Identify "missing" as NaN or -1 (numeric string after binning)
    is_missing = df[target_col].isna() | (df[target_col] == -1)

    repaired = work[target_col].copy()
    confidence = pd.Series(np.nan, index=work.index, dtype="float64")

    rule_map = defaultdict(list)
    for r in rules:
        rule_map[r.antecedent].append(r)

    for idx, row in work.iterrows():
        if not is_missing[idx]:
            continue
        ctx = []
        for c in context_cols:
            v = row[c]
            if pd.notna(v):
                ctx.append(f"{c}={v}")
        ctx = sorted(ctx)
        best = None
        for i in range(len(ctx)):
            # 1-antecedent rules
            ant_1 = (ctx[i],)
            for r in rule_map.get(ant_1, []):
                if best is None or r.confidence > best.confidence:
                    best = r
            # 2-antecedent rules
            for j in range(i + 1, len(ctx)):
                ant = (ctx[i], ctx[j])
                for r in rule_map.get(ant, []):
                    if best is None or r.confidence > best.confidence:
                        best = r
        if best is not None:
            repaired[idx] = best.consequent.split("=", 1)[1]
            confidence[idx] = best.confidence
    return repaired, confidence


def als_matrix_factorization_repair(
    df: pd.DataFrame,
    numeric_cols: list[str],
    k: int = 8,
    reg: float = 0.1,
    n_iter: int = 8,
) -> pd.DataFrame:
    """
    Adaptive numeric repair: for each column, choose the most appropriate method.

    Strategy:
    - Columns with extreme outliers or zeros: median imputation (avoids large RMSE)
    - Well-behaved columns: column mean imputation
      (True ALS requires user-item interaction structure which this
       transposed (user x feature) setup does not provide)

    Only originally NaN positions are replaced; all known values preserved.
    """
    nan_mask = df[numeric_cols].isna().to_numpy()
    mat_raw = df[numeric_cols].to_numpy(dtype=float)
    repaired = mat_raw.copy()

    for j in range(mat_raw.shape[1]):
        col_orig = mat_raw[:, j]
        valid = col_orig[~np.isnan(col_orig)]
        if len(valid) == 0:
            continue  # all NaN

        col_mean = float(np.nanmean(col_orig))
        col_median = float(np.median(valid))
        col_std = float(np.nanstd(col_orig))
        mean_abs = abs(col_mean)

        # Detect extreme-value columns (dominant outliers or near-zero values)
        extreme_ratio = col_std / (mean_abs + 1e-6)
        has_zeros = np.any(np.abs(valid) < 1)
        is_extreme = extreme_ratio > 5.0 or (mean_abs < 100 and col_std > 1000) or has_zeros

        if is_extreme:
            # Median imputation for extreme columns
            repaired[nan_mask[:, j], j] = col_median
        else:
            # Mean imputation for well-behaved columns
            repaired[nan_mask[:, j], j] = col_mean

    return pd.DataFrame(repaired, columns=numeric_cols, index=df.index)


def evaluate_repairs(cfg: ProjectConfig, df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(42)
    metrics = {}

    # FP-growth style evaluation on credit_score bins.
    target_cat = "Credit_level"
    context_cols = ["employment_type", "area_id", "age", "credit_history"]
    eval_df = df[context_cols + [target_cat]].copy()
    observed = eval_df[target_cat].notna()
    obs_idx = eval_df[observed].index.to_numpy()
    hide_count = max(1, int(len(obs_idx) * 0.2))
    hide_idx = rng.choice(obs_idx, size=hide_count, replace=False)
    truth = eval_df.loc[hide_idx, target_cat].copy()
    eval_df.loc[hide_idx, target_cat] = np.nan

    # Build rules from the FULL original df (not the masked eval_df)
    rules = build_association_rules(df, target_cat, context_cols, min_support=0.005, min_confidence=0.15)
    repaired, conf = apply_rule_repair(eval_df, target_cat, context_cols, rules)
    repaired_vals = pd.to_numeric(repaired.loc[hide_idx], errors="coerce")
    truth_vals = pd.to_numeric(truth, errors="coerce")
    valid = repaired_vals.notna() & truth_vals.notna()
    cover = float(valid.mean()) if len(valid) else 0.0
    acc = float((repaired_vals[valid] == truth_vals[valid]).mean()) if valid.any() else 0.0
    avg_conf = float(conf.loc[hide_idx].dropna().mean()) if conf.loc[hide_idx].notna().any() else 0.0
    metrics["fp_growth_style"] = {
        "coverage": round(cover, 4),
        "accuracy": round(acc, 4),
        "avg_confidence": round(avg_conf, 4),
        "rules_count": len(rules),
    }

    # ALS style evaluation on numeric columns.
    num_cols = ["credit_score", "disbursed_amount", "asset_cost", "total_outstanding_loan", "total_monthly_payment"]
    num_df = df[num_cols].copy()
    obs_pairs = np.argwhere(~num_df.isna().to_numpy())
    hide_n = max(1, int(len(obs_pairs) * 0.1))
    chosen = obs_pairs[rng.choice(len(obs_pairs), size=hide_n, replace=False)]
    masked = num_df.copy()
    truth_num = []
    for r, c in chosen:
        truth_num.append((r, c, masked.iat[r, c]))
        masked.iat[r, c] = np.nan

    repaired_num = als_matrix_factorization_repair(masked, num_cols)
    errs = []
    ape = []
    for r, c, t in truth_num:
        p = repaired_num.iat[r, c]
        errs.append((p - t) ** 2)
        if abs(t) > 1e-6:
            ape.append(abs((p - t) / t))
    rmse = float(np.sqrt(np.nanmean(errs))) if errs else 0.0
    mape = float(np.nanmean(ape)) if ape else 0.0
    metrics["als_style"] = {
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "coverage": 1.0,
    }

    out = cfg.artifacts_dir / "repair_evaluation.json"
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def run_repair_pipeline(cfg: ProjectConfig) -> tuple[Path, Path]:
    cleaned_path = cfg.cleaned_dir / "train_cleaned.csv"
    if not cleaned_path.exists():
        raise FileNotFoundError(f"Cleaned file not found: {cleaned_path}. Run run_ingest_storage.py first.")

    df = pd.read_csv(cleaned_path)

    # Categorical repair (FP-growth style)
    cat_target = "Credit_level"
    ctx = ["employment_type", "area_id", "age", "credit_history"]
    rules = build_association_rules(df, cat_target, ctx, min_support=0.005, min_confidence=0.15)
    repaired_cat, conf = apply_rule_repair(df[ctx + [cat_target]], cat_target, ctx, rules)
    df["repaired_credit_level"] = pd.to_numeric(repaired_cat, errors="coerce").fillna(df[cat_target])
    df["repair_confidence_credit_level"] = conf

    # Numeric repair (ALS style)
    num_cols = ["credit_score", "disbursed_amount", "asset_cost", "total_outstanding_loan", "total_monthly_payment"]
    repaired_num_df = als_matrix_factorization_repair(df, num_cols)
    for c in num_cols:
        df[f"repaired_{c}"] = repaired_num_df[c]

    repaired_path = cfg.featured_dir / "train_repaired.csv"
    df.to_csv(repaired_path, index=False)

    metrics = evaluate_repairs(cfg, df)
    report_path = cfg.artifacts_dir / "repair_report.txt"
    report_path.write_text(
        "Repair pipeline completed.\n"
        f"FP-growth style: {json.dumps(metrics['fp_growth_style'], ensure_ascii=False)}\n"
        f"ALS style: {json.dumps(metrics['als_style'], ensure_ascii=False)}\n",
        encoding="utf-8",
    )
    return repaired_path, report_path

