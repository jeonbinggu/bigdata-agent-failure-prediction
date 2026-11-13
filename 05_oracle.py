"""천장 재기: 예측 기반 정책이 도달할 수 있는 상한.

- 오라클 정책: 각 시도의 실제 target을 체크포인트 k에서 미리 안다고 치고 03_policy와 같은 시뮬레이션.
  oracle_k10 = 현재 체크포인트 설계(k≥10)에서의 상한, oracle_k5 = 비용 열이 있는 가장 이른 체크포인트(k=5).
- 해결 가능 비율: 홀드아웃 과제 중 시도 하나라도 성공한 과제 비율 = 어떤 정책도 못 넘는 해결률 상한.
출력: results/oracle_holdout.csv
"""
import importlib

import numpy as np
import pandas as pd

P = importlib.import_module("03_policy")  # main()은 __main__에서만 돈다


def oracle_tasks(meta, instance_ids, ks):
    t = meta[meta.instance_id.isin(instance_ids)].copy()
    for k in ks:
        t[k] = t.target.astype(float)  # 확률 자리에 정답(0/1)을 넣는다
    return [g.to_dict("records") for _, g in t.groupby("instance_id")]


def main():
    meta = pd.read_parquet("data/meta.parquet")
    hold_ids = set(pd.read_parquet("results/holdout_preds.parquet").instance_id)
    ref = pd.read_csv("results/policy_holdout.csv")  # 기존 정책 결과(비교용)

    hold = oracle_tasks(meta, hold_ids, P.KS)
    hold_k5 = oracle_tasks(meta, hold_ids, (5,))
    solvable = np.mean([any(a["target"] for a in t) for t in hold])
    max_attempts = max(len(t) for t in hold)
    print(f"holdout tasks {len(hold)}, solvable (≥1 success among ≤{max_attempts} attempts): {solvable:.3f}")

    per_step = {"steps": 1, "chars": meta.chars_total.sum() / meta.n_steps.sum(),
                "ctx": meta.ctx_total.sum() / meta.n_steps.sum()}
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


if __name__ == "__main__":
    main()
