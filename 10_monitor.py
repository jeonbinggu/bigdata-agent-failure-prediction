"""E6 감시 운영 분석: '위험 점수 상위 x%만 사람이 검토한다'고 할 때 사건을 얼마나 미리 잡는가.

비교: 무작위 검토(재현율 = x), 단순 규칙, LR, LightGBM, 앙상블(LR+GRU+GCN)
- 단순 규칙(y_tamper): 테스트 수정 의도 키워드 x10 + 기존 테스트 파일 열람 + 실패 직후 테스트 이동
- 단순 규칙(y_risky): 오류 관찰 수 + not found 수 (환경 문제를 겪는 중인가)
과제 단위 부트스트랩(1000회) 95% CI, 경보 시점과 실제 사건 사이의 남은 단계(lead time)
출력: results/monitor_{TARGET}.csv, results/monitor_curve.png
"""
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BUDGETS = (0.01, 0.02, 0.05, 0.10)
GRID = np.linspace(0.005, 0.2, 40)
RULE = {"y_tamper": lambda f: 10 * f.s_kw_test_mod + f.s_open_test + f.s_fail_to_test,
        "y_risky": lambda f: f.n_error_obs + f.n_not_found}
N_BOOT = 1000


def recall_at(y, p, frac):
    top = np.argsort(-p, kind="stable")[:max(int(len(p) * frac), 1)]
    return y[top].sum() / max(y.sum(), 1)


def main():
    feat = pd.read_parquet("data/features_sec.parquet",
                           columns=["traj_id", "k", "s_kw_test_mod", "s_open_test", "s_fail_to_test",
                                    "n_error_obs", "n_not_found"])
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, target in zip(axes, ("y_tamper", "y_risky")):
        hp = pd.read_parquet(f"results/holdout_preds_{target}.parquet").merge(feat, on=["traj_id", "k"])
        hp["p_rule"] = RULE[target](hp) + np.random.default_rng(0).random(len(hp)) * 1e-3  # 동점은 무작위로 깸
        tcol = "t" + target[1:]
        for k, g in hp.groupby("k"):
            y = g[target].values.astype(int)
            inst = g.instance_id.values
            uniq = np.unique(inst)
            idx = {u: np.where(inst == u)[0] for u in uniq}
            rng = np.random.default_rng(k)
            boots = [np.concatenate([idx[u] for u in rng.choice(uniq, len(uniq))]) for _ in range(N_BOOT)]
            for name in ("p_rule", "p_lr", "p_lgbm", "p_ens"):
                if g[name].isna().all():
                    continue
                p = g[name].values
                for b in BUDGETS:
                    r = recall_at(y, p, b)
                    bs = [recall_at(y[i], p[i], b) for i in boots]
                    top = np.argsort(-p, kind="stable")[:max(int(len(p) * b), 1)]
                    caught = g.iloc[top][g.iloc[top][target] == 1]
                    rows.append({"target": target, "k": k, "scorer": name, "budget": b, "n": len(y), "pos": int(y.sum()),
                                 "recall": r, "ci_lo": np.percentile(bs, 2.5), "ci_hi": np.percentile(bs, 97.5),
                                 "lift_vs_random": r / b, "precision": y[top].mean(),
                                 "median_lead_steps": float((caught[tcol] - k).median()) if len(caught) else np.nan})
                if k == 10:
                    ax.plot(GRID * 100, [recall_at(y, p, x) for x in GRID], label=name[2:])
            if k == 10:
                ax.plot(GRID * 100, GRID, "k--", label="random")
        ax.set_title(f"{target}, k=10 (holdout)")
        ax.set_xlabel("review budget (% of runs flagged)")
        ax.set_ylabel("recall of future incidents")
        ax.legend()
    fig.tight_layout()
    fig.savefig("results/monitor_curve.png", dpi=130)
    out = pd.DataFrame(rows)
    for target, g in out.groupby("target"):
        g.to_csv(f"results/monitor_{target}.csv", index=False)
    print(out[out.budget == 0.05].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
