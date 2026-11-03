"""k별 성공 예측: 과제 단위 홀드아웃 + GroupKFold(5), LR / LightGBM, isotonic 보정.

출력: results/metrics.csv, results/holdout_preds.parquet, results/importance_k*.csv,
      results/cross_model.csv, results/k_curve.png, results/calibration.png
"""
import os

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

META = ["traj_id", "instance_id", "model_name", "target", "n_steps", "k"]
SEED = 0
os.makedirs("results", exist_ok=True)


def make_models(pos_weight):
    return {
        "lr": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000)),
        "lgbm": lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=31,
                                   scale_pos_weight=pos_weight, subsample=0.8, subsample_freq=1,
                                   colsample_bytree=0.8, random_state=SEED, verbose=-1),
    }


def xy(df, feat_cols):
    X = pd.get_dummies(df[feat_cols + ["model_name"]], columns=["model_name"], dtype=float)
    return X, df["target"].astype(int).values


def ece(y, p, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean()
               for b in range(bins) if (idx == b).any())


def scores(y, p, thr):
    return {"roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
            "f1": f1_score(y, p >= thr), "brier": brier_score_loss(y, p), "ece": ece(y, p)}


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def best_f1_threshold(y, p):
    grid = np.quantile(p, np.linspace(0.5, 0.99, 50))
    return max(grid, key=lambda t: f1_score(y, p >= t))


def main():
    df = pd.read_parquet("data/features.parquet")
    feat_cols = [c for c in df.columns if c not in META]

    # 과제 단위 홀드아웃 20% (모든 k에서 동일)
    inst = df["instance_id"].unique()
    rng = np.random.default_rng(SEED)
    hold = set(rng.choice(inst, size=int(len(inst) * 0.2), replace=False))
    df["holdout"] = df["instance_id"].isin(hold)

    metrics, preds, dev_preds, cross = [], [], [], []
    for k, dk in df.groupby("k"):
        dev, test = dk[~dk.holdout], dk[dk.holdout]
        Xd, yd = xy(dev, feat_cols)
        Xt, yt = xy(test, feat_cols)
        Xt = Xt.reindex(columns=Xd.columns, fill_value=0)
        pw = (yd == 0).sum() / max((yd == 1).sum(), 1)
        out = test[META].copy()

        dev_out = dev[META].copy()
        for name in make_models(pw):
            oof = np.zeros(len(yd))
            folds = list(GroupKFold(5).split(Xd, yd, dev["instance_id"]))
            for tr, va in folds:
                m = make_models(pw)[name].fit(Xd.iloc[tr], yd[tr])
                oof[va] = m.predict_proba(Xd.iloc[va])[:, 1]
            iso = IsotonicRegression(out_of_bounds="clip").fit(oof, yd)  # OOF로 보정기 학습
            oof_cal = iso.predict(oof)
            thr = best_f1_threshold(yd, oof_cal)
            # Platt: logit(raw p)에 1차원 로지스틱 회귀
            platt = LogisticRegression().fit(logit(oof)[:, None], yd)

            # 정책 τ 튜닝용 dev 확률: 보정기도 cross-fit(자기 폴드 제외)으로 in-sample 보정을 피한다
            oof_xfit = np.zeros(len(yd))
            for tr, va in folds:
                oof_xfit[va] = IsotonicRegression(out_of_bounds="clip").fit(oof[tr], yd[tr]).predict(oof[va])
            dev_out[f"p_{name}"] = oof_xfit

            final = make_models(pw)[name].fit(Xd, yd)
            p_raw = final.predict_proba(Xt)[:, 1]
            p = iso.predict(p_raw)
            p_platt = platt.predict_proba(logit(p_raw)[:, None])[:, 1]
            out[f"p_{name}"] = p
            metrics.append({"k": k, "model": name, "split": "cv_oof_xfit", "n": len(yd), **scores(yd, oof_xfit, thr)})
            metrics.append({"k": k, "model": name, "split": "holdout_raw", "n": len(yt), **scores(yt, p_raw, best_f1_threshold(yd, oof))})
            metrics.append({"k": k, "model": name, "split": "holdout_platt", "n": len(yt),
                            **scores(yt, p_platt, best_f1_threshold(yd, platt.predict_proba(logit(oof)[:, None])[:, 1]))})
            metrics.append({"k": k, "model": name, "split": "holdout", "n": len(yt), **scores(yt, p, thr)})

            if name == "lgbm":
                contrib = final.booster_.predict(Xt, pred_contrib=True)[:, :-1]  # TreeSHAP
                pd.DataFrame({"feature": Xd.columns, "gain": final.booster_.feature_importance("gain"),
                              "mean_abs_shap": np.abs(contrib).mean(0)}) \
                    .sort_values("mean_abs_shap", ascending=False).to_csv(f"results/importance_k{k}.csv", index=False)
        preds.append(out)
        dev_preds.append(dev_out)

        # 모델 간 일반화: 한 model_name은 빼고 학습 -> 그 모델로 평가 (LightGBM)
        for held in dk["model_name"].unique():
            tr, te = dk[dk.model_name != held], dk[dk.model_name == held]
            Xa, ya = xy(tr, feat_cols)
            Xb, yb = xy(te, feat_cols)
            Xb = Xb.reindex(columns=Xa.columns, fill_value=0)
            m = make_models((ya == 0).sum() / max((ya == 1).sum(), 1))["lgbm"].fit(Xa, ya)
            pb = m.predict_proba(Xb)[:, 1]
            cross.append({"k": k, "held_out_model": held, "n": len(yb), "success_rate": yb.mean(),
                          "roc_auc": roc_auc_score(yb, pb), "pr_auc": average_precision_score(yb, pb)})
        print(f"k={k} done", flush=True)

    met = pd.DataFrame(metrics)
    met.to_csv("results/metrics.csv", index=False)
    pd.DataFrame(cross).to_csv("results/cross_model.csv", index=False)
    pr = pd.concat(preds)
    pr.to_parquet("results/holdout_preds.parquet", index=False)
    pd.concat(dev_preds).to_parquet("data/dev_oof_preds.parquet", index=False)  # 커서 git 제외
    print(met[met.split.str.startswith("holdout")].round(4).to_string(index=False))

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    h = met[met.split == "holdout"]
    for name, g in h.groupby("model"):
        ax[0].plot(g.k, g.roc_auc, "o-", label=f"{name} ROC-AUC")
        ax[1].plot(g.k, g.pr_auc, "o-", label=f"{name} PR-AUC")
    for a in ax:
        a.set_xlabel("k (prefix steps)")
        a.legend()
    fig.tight_layout()
    fig.savefig("results/k_curve.png", dpi=120)

    fig, ax = plt.subplots(figsize=(5, 5))
    for k, g in pr.groupby("k"):
        fy, fx = calibration_curve(g.target, g.p_lgbm, n_bins=10, strategy="quantile")
        ax.plot(fx, fy, "o-", label=f"k={k}")
    ax.plot([0, 1], [0, 1], "k--")
    ax.set_xlabel("predicted p (lgbm, isotonic)")
    ax.set_ylabel("observed success rate")
    ax.legend()
    fig.savefig("results/calibration.png", dpi=120)


if __name__ == "__main__":
    main()
