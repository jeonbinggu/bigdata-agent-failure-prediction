"""E2 실행 실패 유형 + E3 보안 위협 패턴 기술 분석.

E2: 실패 실행(target=False)을 종료 상태와 전체 궤적 행동으로 계층 분류
E3: 변조 직전 행동 전이(lift), 추론 텍스트 키워드, 행동 전이 그래프 차이, 모델·성공 여부별 위협 비율
대조군: 테스트를 안 건드린 실행에서 '다른 소스 파일로 옮겨 편집하기 직전' 시점 (변조 쪽도 앞선 편집이 있는 경우만)
출력: results/failure_modes.csv, threat_bigram_lift.csv, threat_keywords.csv, transition_diff.png, threat_by_model.png
"""
import glob
import importlib.util
import re
from collections import Counter

import matplotlib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

spec = importlib.util.spec_from_file_location("lab", "06_labels.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
F = L.F

TOK = F.ACTIONS + ["edit_test", "risky"]
T2I = {t: i for i, t in enumerate(TOK)}
KW_RE = re.compile(r"(skip|remove|delet|comment(ing)? out|disabl|modif|chang|updat|adjust|fix)\w*\s+(the\s+|this\s+|that\s+)?"
                   r"(failing\s+|existing\s+)?(test|assert)", re.I)
WIN = 5


def tokens(steps):
    out, fail = [], []
    for a, arg, ai, obs, open_file, cmd in steps:
        if a == "edit" and open_file and L.is_test(open_file):
            a = "edit_test"
        elif a not in L.EXEC_SKIP and any(r.search(cmd) for r in L.RISK_RE.values()):
            a = "risky"
        out.append(a)
        fail.append(bool(F.TEST_FAIL_RE.search(obs) or F.ERR_RE.search(obs)))
    return out, fail


def main():
    lab = pd.read_parquet("data/labels.parquet")
    rows, bigram = [], {1: Counter(), 0: Counter()}
    trans = {1: np.zeros((len(TOK), len(TOK))), 0: np.zeros((len(TOK), len(TOK)))}
    n_win = {1: 0, 0: 0}
    tid = 0
    for path in sorted(glob.glob("data/raw/**/*.parquet", recursive=True)):
        for b in pq.ParquetFile(path).iter_batches(batch_size=256, columns=["trajectory"]):
            for tr in b.column(0).to_pylist():
                lr = lab.iloc[tid]
                steps = F.steps_of(tr)
                tok, fail = tokens(steps)
                args = [s[1] for s in steps]
                n = len(steps)
                rows.append({"traj_id": tid,
                             "rep_ratio": sum(x == y for x, y in zip(args, args[1:])) / max(n - 1, 1),
                             "max_run": max((len(list(g)) for g in _runs(tok)), default=0),
                             "n_syntax_fail": sum(F.SYNTAX_FAIL in s[3] for s in steps),
                             "ran_python": int(any(t == "python" for t in tok)),
                             "n_edit": sum(t in ("edit", "edit_test") for t in tok)})
                # E3: 변조 실행은 테스트 파일 첫 편집 시점 t,
                # 대조군(테스트를 안 건드린 실행)은 '이미 한 파일을 고친 뒤 다른 소스 파일로 옮겨 편집한' 첫 시점.
                # 둘 다 '편집 대상을 바꾸기 직전' 창이라 탐색→편집 자체의 패턴은 상쇄된다
                g, t = None, 0
                if lr.y_tamper == 1 and lr.t_tamper > 0:
                    t = int(lr.t_tamper)
                    if any(s[0] == "edit" for s in steps[:t - 1]):  # 대조군과 맞추려고 '앞서 편집한 적 있음'만
                        g = 1
                    else:
                        t = 0
                elif lr.y_tamper == 0 and lr.touch_existing_test == 0:
                    last = None
                    for i, s in enumerate(steps, 1):
                        if s[0] == "edit" and s[4]:
                            if last is not None and s[4] != last:
                                g, t = 0, i
                                break
                            last = s[4]
                if t > 1:
                    pre = [f"{a}{'!' if f else ''}" for a, f in zip(tok[:t - 1], fail[:t - 1])][-WIN:]
                    bigram[g].update(set(zip(pre, pre[1:])))
                    for x, y in zip(tok[:t - 1], tok[1:t - 1]):
                        trans[g][T2I[x], T2I[y]] += 1
                    kw = any(KW_RE.search(s[2] or "") for s in steps[max(t - 1 - WIN, 0):t - 1])  # t단계 자신은 제외
                    rows[-1].update({"grp": g, "kw_pre": int(kw)})
                    n_win[g] += 1
                tid += 1
        print(f"{tid} trajectories", flush=True)

    d = lab.merge(pd.DataFrame(rows), on="traj_id")
    d.to_parquet("data/traj_stats.parquet", index=False)

    # ---------- E2: 실패 유형 (계층, 위에서부터 먼저 걸리는 것) ----------
    f = d[~d.target].copy()
    es = f.exit_status
    f["mode"] = np.select(
        [es.str.contains("exit_context"), es.isin(["early_exit", "exit_format", "submitted_no_patch", "exit_cost"])
         | es.str.contains("exit_format|exit_cost"),
         f.rep_ratio >= 0.3, f.n_syntax_fail >= 3, f.ran_python == 0],
        ["컨텍스트 소진", "제출 실패(빈 패치·형식·조기 종료)", "반복 루프", "편집 문법 오류 반복", "검증 없이 제출"],
        "잘못된 수정(기타)")
    fm = f.groupby("mode").agg(n=("traj_id", "size"), mean_steps=("n_steps", "mean"),
                               tamper_rate=("y_tamper", "mean"), risky_rate=("y_risky", "mean"))
    fm["share"] = fm.n / len(f)
    fm = fm.sort_values("n", ascending=False)
    fm.to_csv("results/failure_modes.csv")
    print(fm.round(3).to_string())
    print(pd.crosstab(f["mode"], f.model_name, normalize="columns").round(3).to_string())

    # ---------- E3: 변조 직전 2-gram lift ----------
    bl = pd.DataFrame([{"bigram": f"{a} → {b}", "n_tamper": bigram[1][(a, b)], "n_ctrl": bigram[0][(a, b)]}
                       for a, b in set(bigram[1]) | set(bigram[0])])
    bl["p_tamper"] = bl.n_tamper / n_win[1]
    bl["p_ctrl"] = bl.n_ctrl / n_win[0]
    bl["lift"] = (bl.n_tamper + 0.5) / n_win[1] / ((bl.n_ctrl + 0.5) / n_win[0])
    bl = bl[bl.n_tamper >= 20].sort_values("lift", ascending=False)
    bl.to_csv("results/threat_bigram_lift.csv", index=False)
    print(f"windows: tamper={n_win[1]} ctrl={n_win[0]}")
    print(bl.head(12).round(3).to_string(index=False))

    kw = d[d.grp.notna()].groupby("grp").kw_pre.agg(["mean", "size"])
    kw.to_csv("results/threat_keywords.csv")
    print("추론 키워드(변조 직전 5단계):\n", kw.round(4))

    # 행동 전이 그래프 차이 (행 정규화 전이확률: 변조 − 대조)
    P = {g: trans[g] / np.maximum(trans[g].sum(1, keepdims=True), 1) for g in (0, 1)}
    diff = P[1] - P[0]
    diff[trans[1].sum(1) < 30] = np.nan  # 변조 쪽 출발 횟수가 적은 행(예: submit)은 노이즈라 가린다
    np.save("results/transition_counts.npy", np.stack([trans[0], trans[1]]))
    fig, ax = plt.subplots(figsize=(8, 7))
    lim = np.nanmax(np.abs(diff))
    im = ax.imshow(diff, cmap="RdBu_r", vmin=-lim, vmax=lim)
    ax.set_xticks(range(len(TOK)), TOK, rotation=60, ha="right")
    ax.set_yticks(range(len(TOK)), TOK)
    ax.set_xlabel("next action")
    ax.set_ylabel("current action")
    ax.set_title("Transition prob. difference before t (tamper − control)")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout()
    fig.savefig("results/transition_diff.png", dpi=130)

    # 모델·성공 여부별 위협 비율
    g = d.groupby(["model_name", "target"])[["y_tamper", "y_risky"]].mean().unstack("target")
    g.to_csv("results/threat_by_model.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, col in zip(axes, ["y_tamper", "y_risky"]):
        g[col].plot.bar(ax=ax, rot=0)
        ax.set_title(col)
        ax.set_ylabel("rate")
        ax.legend(["failed", "resolved"])
    fig.tight_layout()
    fig.savefig("results/threat_by_model.png", dpi=130)
    print(g.round(4).to_string())


def _runs(seq):
    from itertools import groupby
    return (list(g) for _, g in groupby(seq))


if __name__ == "__main__":
    main()
