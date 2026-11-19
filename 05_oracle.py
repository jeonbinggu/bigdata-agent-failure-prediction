"""천장 재기: 예측 기반 정책이 도달할 수 있는 상한.

- 오라클 정책: 각 시도의 실제 target을 체크포인트 k에서 미리 안다고 치고 03_policy와 같은 시뮬레이션.
  oracle_k10 = 현재 체크포인트 설계(k≥10)에서의 상한, oracle_k5 = 비용 열이 있는 가장 이른 체크포인트(k=5).
- 해결 가능 비율: 홀드아웃 과제 중 시도 하나라도 성공한 과제 비율 = 어떤 정책도 못 넘는 해결률 상한.
출력: results/oracle_holdout.csv, results/decomposition.png
"""
import importlib

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

P = importlib.import_module("03_policy")  # main()은 __main__에서만 돈다


def oracle_tasks(meta, instance_ids, ks):
    t = meta[meta.instance_id.isin(instance_ids)].copy()
    for k in ks:
        t[k] = t.target.astype(float)  # 확률 자리에 정답(0/1)을 넣는다
    return [g.to_dict("records") for _, g in t.groupby("instance_id")]


def plot_decomposition(df, ref, Bs=100):
    """해결률 분해: single → 재시도 → 고정 상한 → 조기 종료 → 오라클 → 천장 (비용 단위별, 예산 Bs)."""
    names = {"steps": "steps", "chars": "characters", "ctx": "cumulative context", "cctx": "cumulative context + caching"}
    units = [u for u in P.UNITS if u in set(df.unit) & set(ref.unit)]
    fig, axes = plt.subplots(1, len(units), figsize=(4.2 * len(units), 3.6), sharey=True)
    for ax, unit in zip(np.atleast_1d(axes), units):
        r = ref[(ref.unit == unit) & (ref.budget_steps == Bs)].set_index("policy").solve_rate
        o = df[(df.unit == unit) & (df.budget_steps == Bs)].set_index("policy")
        bars = [("single attempt", r["single"], 0), ("random retry", r["random_retry"], 0), ("fixed step cap", r["best_cap"], 0),
                ("early stop (ensemble)", r["tuned_early_stop"], 0), ("oracle at k=10", o.solve_rate["oracle_k10"], 1),
                ("oracle at k=5", o.solve_rate["oracle_k5"], 1), ("solvable ceiling", o.solvable_ceiling.iloc[0], 1)]
        labels, vals, bound = zip(*bars[::-1])
        vals = np.array(vals) * 100
        ax.barh(labels, vals, height=0.62, color=["#b9b8b2" if b else "#2a78d6" for b in bound])
        for y, v in enumerate(vals):
            ax.text(v + 0.4, y, f"{v:.1f}", va="center", fontsize=9, color="#0b0b0b")
        ax.set_xlim(0, 28)
        ax.set_title(names[unit], fontsize=10, loc="left")
        ax.set_xlabel("tasks solved (%)", fontsize=9, color="#52514e")
        ax.tick_params(length=0, labelsize=9)
        ax.spines[["top", "right", "left"]].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in ("#2a78d6", "#b9b8b2")]
    fig.legend(handles, ["achievable policy", "upper bound (outcome known in advance)"], loc="lower center", ncol=2, frameon=False, fontsize=9)
    fig.suptitle(f"Where the solve rate comes from (holdout, budget = {Bs} average steps)", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.96))
    fig.savefig("results/decomposition.png", dpi=130)


def main():
    meta = P.load_meta()
    hold_ids = set(pd.read_parquet("results/holdout_preds.parquet").instance_id)
    ref = pd.read_csv("results/policy_holdout_p_ens.csv")  # 대표 정책(앙상블, k=10/20/30) 결과(비교용)

    hold = oracle_tasks(meta, hold_ids, P.KS)
    hold_k5 = oracle_tasks(meta, hold_ids, (5,))
    solvable = np.mean([any(a["target"] for a in t) for t in hold])
    max_attempts = max(len(t) for t in hold)
    print(f"holdout tasks {len(hold)}, solvable (≥1 success among ≤{max_attempts} attempts): {solvable:.3f}")

    per_step = P.per_step_cost(meta)
    rng = np.random.default_rng(0)
    rows = []
    for unit in P.UNITS:
        for Bs in P.BUDGET_STEPS:
            B = Bs * per_step[unit]
            base = P.simulate(hold, B, unit, seeds=P.HOLD_SEEDS)  # random_retry
            runs = {
                "oracle_k10": P.simulate(hold, B, unit, taus={10: 0.5}, seeds=P.HOLD_SEEDS),
                "oracle_k5": P.simulate(hold_k5, B, unit, taus={5: 0.5}, seeds=P.HOLD_SEEDS),
            }
            tuned = ref[(ref.unit == unit) & (ref.budget_steps == Bs) & (ref.policy == "tuned_early_stop")].iloc[0]
            for name, r in runs.items():
                d = r[:, 0] - base[:, 0]
                lo, hi = P.boot_ci(d, rng)
                rows.append({"unit": unit, "budget_steps": Bs, "policy": name, **P.summarize(r),
                             "diff_vs_random_retry": d.mean(), "diff_lo": lo, "diff_hi": hi,
                             "tuned_early_stop": tuned.solve_rate, "random_retry": base[:, 0].mean(),
                             "solvable_ceiling": solvable})
            print(f"{unit} B={Bs} done", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv("results/oracle_holdout.csv", index=False)
    print(df.round(4).to_string(index=False))
    plot_decomposition(df, ref)


if __name__ == "__main__":
    main()
