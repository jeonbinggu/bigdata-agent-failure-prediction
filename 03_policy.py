"""조기 종료·재시작 정책 오프라인 시뮬레이션.

- 과제마다 예산 B를 주고, 같은 과제의 시도들을 무작위 순서로 '새 세션'처럼 꺼내 쓴다.
- 비용 단위: steps(행동 수) / chars(ai 출력 + 관찰 글자 수, 토큰 대용)
- 정책: single / random_retry / cap_N / early_stop(체크포인트별 τ)
- τ와 cap N은 dev(OOF 예측)에서 고르고, 홀드아웃에서 과제 단위 부트스트랩 95% CI로 평가한다.
출력: results/policy_dev.csv, results/policy_holdout.csv, results/policy_tradeoff.png
"""
import itertools
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

KS = tuple(int(k) for k in os.environ.get("KS", "10,20,30").split(","))  # KS=5,10,20,30 으로 k=5 체크포인트 추가
BUDGET_STEPS = [60, 100, 150, 200]
TAU_GRID = [0.0, 0.02, 0.05, 0.1, 0.15]
CAPS = [30, 50, 80]
DEV_SEEDS, HOLD_SEEDS, N_BOOT = 5, 20, 2000
UNITS = ("steps", "chars", "ctx")  # ctx: 매 단계 프롬프트 + 누적 대화를 다시 입력하는 과금 근사


PRED = sys.argv[1] if len(sys.argv) > 1 else "p_lgbm"  # p_lgbm / p_gru / p_ens
SUFFIX = ("" if PRED == "p_lgbm" else f"_{PRED}") + ("_k5" if 5 in KS else "")


def load(pred_path, meta):
    pr = pd.read_parquet(pred_path)
    p = pr.pivot_table(index="traj_id", columns="k", values=PRED)
    t = meta[meta.instance_id.isin(set(pr.instance_id))].set_index("traj_id").join(p)
    return [g.to_dict("records") for _, g in t.groupby("instance_id")]


def cost_at(a, step, unit):
    if unit == "steps":
        return min(step, a["n_steps"])
    return a[f"{unit}_at_{step}"]  # chars_at_k / ctx_at_k


def run_attempt(a, taus, cap, unit):
    """(비용, 성공, 조기종료) — taus: {k: τ}"""
    n = a["n_steps"]
    for k in sorted(taus):
        if n <= k:
            break
        if a.get(k, np.nan) < taus[k]:  # NaN 비교는 False
            return cost_at(a, k, unit), False, True
    if cap and n > cap:
        return cost_at(a, cap, unit), False, True
    return (n if unit == "steps" else a[f"{unit}_total"]), bool(a["target"]), False


def simulate(tasks, budget, unit, taus=None, cap=None, single=False, seeds=1):
    """과제별 [solved, used, stops, wrong_stops] 의 시드 평균 (n_tasks x 4)."""
    taus = taus or {}
    out = np.zeros((len(tasks), 4))
    for s in range(seeds):
        rng = np.random.default_rng(s)
        for ti, attempts in enumerate(tasks):
            order = rng.permutation(len(attempts))[: 1 if single else None]
            left = budget
            for i in order:
                if left <= 0:
                    break
                a = attempts[i]
                cost, ok, stopped = run_attempt(a, taus, cap, unit)
                if cost > left:
                    cost, ok = left, False
                left -= cost
                out[ti] += (0, cost, stopped, stopped and a["target"])
                if ok:
                    out[ti, 0] += 1
                    break
    return out / seeds


def summarize(r):
    return {"solve_rate": r[:, 0].mean(), "cost_per_task": r[:, 1].mean(),
            "wrong_stop_rate": r[:, 3].sum() / r[:, 2].sum() if r[:, 2].sum() else 0.0}


def boot_ci(x, rng):
    idx = rng.integers(0, len(x), (N_BOOT, len(x)))
    m = x[idx].mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def policies():
    yield "single", {"single": True}
    yield "random_retry", {}
    for c in CAPS:
        yield f"cap_{c}", {"cap": c}
    for combo in itertools.product(TAU_GRID, repeat=len(KS)):
        if any(combo):
            taus = {k: t for k, t in zip(KS, combo) if t > 0}
            yield "early_stop_" + "_".join(f"k{k}={t}" for k, t in taus.items()), {"taus": taus}


def main():
    meta = pd.read_parquet("data/meta.parquet")
    chars_per_step = meta.chars_total.sum() / meta.n_steps.sum()
    dev = load("data/dev_oof_preds.parquet", meta)
    hold = load("results/holdout_preds.parquet", meta)
    print(f"dev tasks {len(dev)}, holdout tasks {len(hold)}, chars/step {chars_per_step:.0f}")

    dev_rows, hold_rows = [], []
    rng = np.random.default_rng(0)
    per_step = {"steps": 1, "chars": chars_per_step, "ctx": meta.ctx_total.sum() / meta.n_steps.sum()}
    for unit in UNITS:
        for Bs in BUDGET_STEPS:
            B = Bs * per_step[unit]  # 같은 '평균 단계 수' 예산을 각 비용 단위로 환산
            # 1) dev에서 모든 정책 평가 → cap / early_stop 최적값 선택
            res = {}
            for name, kw in policies():
                res[name] = summarize(simulate(dev, B, unit, seeds=DEV_SEEDS, **kw))
                dev_rows.append({"unit": unit, "budget_steps": Bs, "policy": name, **res[name]})
            best_cap = max((n for n in res if n.startswith("cap_")), key=lambda n: res[n]["solve_rate"])
            best_es = max((n for n in res if n.startswith("early_stop")), key=lambda n: res[n]["solve_rate"])

            # 2) 홀드아웃에서 선택된 정책만 평가 + 부트스트랩
            kws = dict(policies())
            sel = {"single": "single", "random_retry": "random_retry", "best_cap": best_cap, "tuned_early_stop": best_es}
            per_task = {lab: simulate(hold, B, unit, seeds=HOLD_SEEDS, **kws[n]) for lab, n in sel.items()}
            for lab, n in sel.items():
                r = per_task[lab]
                lo, hi = boot_ci(r[:, 0], rng)
                row = {"unit": unit, "budget_steps": Bs, "policy": lab, "config": n, **summarize(r),
                       "solve_ci_lo": lo, "solve_ci_hi": hi}
                for base in ("random_retry", "best_cap"):
                    if lab != base:
                        d = r[:, 0] - per_task[base][:, 0]
                        dlo, dhi = boot_ci(d, rng)
                        row[f"diff_vs_{base}"], row[f"diff_vs_{base}_lo"], row[f"diff_vs_{base}_hi"] = d.mean(), dlo, dhi
                        row[f"cost_diff_vs_{base}"] = r[:, 1].mean() - per_task[base][:, 1].mean()
                hold_rows.append(row)
            print(f"{unit} B={Bs} done (cap={best_cap}, es={best_es})", flush=True)

    pd.DataFrame(dev_rows).to_csv(f"results/policy_dev{SUFFIX}.csv", index=False)
    h = pd.DataFrame(hold_rows)
    h.to_csv(f"results/policy_holdout{SUFFIX}.csv", index=False)
    cols = ["unit", "budget_steps", "policy", "config", "solve_rate", "solve_ci_lo", "solve_ci_hi",
            "cost_per_task", "wrong_stop_rate", "diff_vs_random_retry", "diff_vs_random_retry_lo", "diff_vs_random_retry_hi"]
    print(h[cols].round(4).to_string(index=False))

    fig, axes = plt.subplots(1, len(UNITS), figsize=(6 * len(UNITS), 5))
    for ax, unit in zip(axes, UNITS):
        g = h[h.unit == unit]
        for lab, gg in g.groupby("policy"):
            ax.errorbar(gg.cost_per_task, gg.solve_rate,
                        yerr=[gg.solve_rate - gg.solve_ci_lo, gg.solve_ci_hi - gg.solve_rate], fmt="o-", label=lab, capsize=3)
        ax.set_xlabel(f"{unit} used per task")
        ax.set_ylabel("task solve rate (holdout, 95% CI)")
        ax.set_title(f"budget unit: {unit}")
        ax.legend()
    fig.tight_layout()
    fig.savefig(f"results/policy_tradeoff{SUFFIX}.png", dpi=120)


if __name__ == "__main__":
    main()
