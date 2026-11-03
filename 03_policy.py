"""홀드아웃 과제 위에서 조기 종료·재시작 정책을 오프라인 시뮬레이션한다.

과제마다 예산 B(단계 수)를 주고, 같은 과제의 시도들을 무작위 순서로 '새 세션'처럼 꺼내 쓴다.
정책: 체크포인트 k에서 p < tau 이면 중단(k단계만 소모) → 다음 시도로 재시작.
기준: single(첫 시도만 끝까지), cap_N(N단계에서 무조건 중단 후 재시도), random_retry(조기 종료 없이 재시도).
출력: results/policy.csv, results/policy_tradeoff.png
"""
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BUDGETS = [60, 100, 150, 200]
TAUS = [0.02, 0.05, 0.08, 0.1, 0.15, 0.2]
CHECKPOINTS = {"k10": (10,), "k20": (20,), "k10-20-30": (10, 20, 30)}
SEEDS = 20


def load():
    pr = pd.read_parquet("results/holdout_preds.parquet")
    p = pr.pivot_table(index="traj_id", columns="k", values="p_lgbm")
    meta = pd.read_parquet("data/meta.parquet").set_index("traj_id")
    # k 이전에 끝난 궤적도 포함해야 하므로 전체 meta 기준으로 홀드아웃 과제를 고른다
    meta = meta[meta.instance_id.isin(set(pr.instance_id))][["instance_id", "target", "n_steps"]]
    t = meta.join(p)
    return {iid: g.drop(columns="instance_id").to_dict("records") for iid, g in t.groupby("instance_id")}


def run_attempt(a, checkpoints, tau, cap):
    """(소모 단계, 성공 여부, 조기종료 여부)"""
    n = a["n_steps"]
    for k in checkpoints:
        if n <= k:
            break
        if a.get(k, np.nan) < tau:  # NaN 비교는 False → 중단 안 함
            return k, False, True
    if cap and n > cap:
        return cap, False, True
    return n, bool(a["target"]), False


def simulate(tasks, budget, checkpoints=(), tau=0.0, cap=None, single=False, seed=0):
    rng = np.random.default_rng(seed)
    solved = used = stops = wrong_stops = 0
    for attempts in tasks.values():
        order = rng.permutation(len(attempts))[: 1 if single else None]
        left = budget
        for i in order:
            if left <= 0:
                break
            a = attempts[i]
            cost, ok, stopped = run_attempt(a, checkpoints, tau, cap)
            if cost > left:  # 예산 초과 → 그 자리에서 끊김
                cost, ok = left, False
            left -= cost
            used += cost
            stops += stopped
            wrong_stops += stopped and a["target"]
            if ok:
                solved += 1
                break
    n = len(tasks)
    return {"solve_rate": solved / n, "steps_per_task": used / n,
            "wrong_stop_rate": wrong_stops / stops if stops else 0.0}


def main():
    tasks = load()
    print(f"holdout tasks: {len(tasks)}, attempts/task mean: {np.mean([len(v) for v in tasks.values()]):.2f}")
    rows = []

    def add(policy, budget, **kw):
        r = pd.DataFrame([simulate(tasks, budget, seed=s, **kw) for s in range(SEEDS)]).mean()
        rows.append({"policy": policy, "budget": budget, **r.to_dict()})

    for B in BUDGETS:
        add("single", B, single=True)
        add("random_retry", B)
        for cap in (30, 50, 80):
            add(f"cap_{cap}", B, cap=cap)
        for cname, cps in CHECKPOINTS.items():
            for tau in TAUS:
                add(f"early_stop_{cname}_tau{tau}", B, checkpoints=cps, tau=tau)
    # 예산 무제한 단일 실행(원래 운영 방식)
    add("single_full_run", 10**9, single=True)

    res = pd.DataFrame(rows)
    res.to_csv("results/policy.csv", index=False)
    best = res.loc[res[res.budget != 10**9].groupby("budget").solve_rate.idxmax()]
    print(res[res.policy.isin(["single", "random_retry", "single_full_run"])].round(4).to_string(index=False))
    print("\nbest per budget:\n", best.round(4).to_string(index=False))

    fig, ax = plt.subplots(figsize=(7, 5))
    for kind, marker in [("random_retry", "s"), ("cap_", "^"), ("early_stop_k10-20-30", "o"), ("single", "x")]:
        g = res[res.policy.str.startswith(kind) & (res.budget != 10**9)]
        ax.scatter(g.steps_per_task, g.solve_rate, marker=marker, label=kind, alpha=0.7)
    ax.set_xlabel("steps used per task")
    ax.set_ylabel("task solve rate")
    ax.legend()
    fig.savefig("results/policy_tradeoff.png", dpi=120)


if __name__ == "__main__":
    main()
