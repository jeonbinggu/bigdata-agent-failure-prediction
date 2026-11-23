"""발표 자료용 숫자·그림 생성. results CSV와 data/*.parquet만 읽는다(재학습 없음).

출력: slides/data.json (슬라이드에 들어가는 모든 숫자), slides/figs/graph_example.png (행동 전이 그래프 예시)
사용: python 12_slide_figs.py  →  cd slides && node build.js
"""
import json

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
TOK = ["open", "goto", "scroll", "search", "find_file", "edit", "create", "python", "submit", "ls", "cat_grep",
       "other", "edit_test", "risky"]  # 07_failure_modes.TOK 순서 (seqs_sec.npz 토큰 번호)
R = "results/"


def r3(x):
    return round(float(x), 4)


def main():
    lab = pd.read_parquet("data/labels.parquet")
    feat = pd.read_parquet("data/features_sec.parquet",
                           columns=["traj_id", "k", "y_tamper", "t_tamper", "y_risky", "t_risky", "s_edit_err_nav",
                                    "s_edit_then_python", "target"])
    d = {}

    # A1 데이터 통계
    g = lab.groupby("model_name")
    d["models"] = [{"model": m.replace("swe-agent-llama-", ""), "n": int(len(x)), "share": r3(len(x) / len(lab)),
                    "solve": r3(x.target.mean()), "tamper": r3(x.y_tamper.mean()), "risky": r3(x.y_risky.mean()),
                    "steps_med": float(x.n_steps.median())} for m, x in g]
    d["n_total"], d["solve_all"] = int(len(lab)), r3(lab.target.mean())
    bins = [0, 5, 10, 20, 30, 40, 50, 60, 80, 100, 10 ** 6]
    names = ["<5", "5-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-79", "80-99", "100+"]
    d["steps_hist"] = {"labels": names, "values": pd.cut(lab.n_steps, bins, right=False).value_counts(sort=False)
                       .astype(int).tolist(), "median": float(lab.n_steps.median())}
    rows = []
    for k, x in feat.groupby("k"):
        row = {"k": int(k), "rows": int(len(x))}
        for t in ("y_tamper", "y_risky"):
            keep = (x[t] == 0) | (x["t" + t[1:]] > k)
            row[t + "_pos"] = int((keep & (x[t] == 1)).sum())
            row[t + "_drop"] = int((~keep).sum())
        rows.append(row)
    d["rows_by_k"] = rows

    # A2 라벨
    st = pd.read_csv(R + "label_stats.csv").set_index("label")
    d["labels"] = {n: {"n": int(st.loc[n, "n"]), "rate": r3(st.loc[n, "rate"]), "solve_pos": r3(st.loc[n, "resolved_rate_pos"]),
                       "solve_neg": r3(st.loc[n, "resolved_rate_neg"])}
                   for n in st.index if n != "by_model"}
    tt = lab.t_tamper[lab.y_tamper == 1]  # 0 = 시점을 못 찾음
    d["t_tamper_found"], d["t_tamper_median"] = r3((tt > 0).mean()), float(tt[tt > 0].median())

    # A3 감사
    au = pd.read_csv(R + "label_audit.csv")
    d["audit"] = {"n": int(len(au)), "counts": au.judgment.value_counts().astype(int).to_dict(),
                  "deliberate_resolved": int(au[(au.judgment == "deliberate_weaken") & au.target].shape[0])}
    # 사람 블라인드 교차 확인(범주별 5건). 정밀도는 감사 60건의 범주 비율로 재가중해 무작위 표본 기준으로 환산
    h = pd.read_csv(R + "label_check_20.csv").merge(au[["traj_id", "judgment"]], on="traj_id")
    V = {"deliberate_weaken", "accidental_overwrite"}
    w = au.judgment.value_counts(normalize=True)
    by = h.groupby("judgment")
    d["label_check"] = {"n": int(len(h)), "agree": r3((h.human == h.judgment).mean()),
                        "kappa": r3(cohen_kappa_score(h.human, h.judgment)),
                        "bin_agree": r3((h.human.isin(V) == h.judgment.isin(V)).mean()),
                        "prec_violation": r3(sum(w[c] * g.human.isin(V).mean() for c, g in by)),
                        "prec_nonbenign": r3(sum(w[c] * (g.human != "benign").mean() for c, g in by))}

    # A4·A5 실패 유형, 위협 패턴
    fm = pd.read_csv(R + "failure_modes.csv")
    d["failure_modes"] = [{"mode": r.mode, "share": r3(r.share), "mean_steps": round(r.mean_steps, 1), "n": int(r.n)}
                          for r in fm.itertuples()]
    d["n_fail"] = int(fm.n.sum())
    bg = pd.read_csv(R + "threat_bigram_lift.csv").sort_values("lift", ascending=False).head(10)
    d["bigrams"] = [{"bigram": r.bigram.replace("→", "->"), "p_tamper": r3(r.p_tamper), "p_ctrl": r3(r.p_ctrl),
                     "lift": round(r.lift, 1)} for r in bg.itertuples()]
    kw = pd.read_csv(R + "threat_keywords.csv").set_index("grp")
    d["keywords"] = {"tamper": r3(kw.loc[1.0, "mean"]), "ctrl": r3(kw.loc[0.0, "mean"]),
                     "n_tamper": int(kw.loc[1.0, "size"]), "n_ctrl": int(kw.loc[0.0, "size"])}

    # A8 모델 성능
    met = {}
    for t in ("y_tamper", "y_risky"):
        sg = pd.read_csv(R + f"seqgraph_metrics_{t}.csv")
        out = []
        for k, x in sg.groupby("k"):
            if k not in (5, 10):
                continue
            for name, lab_ in (("lr", "LR"), ("lgbm", "LightGBM"), ("gru(seed avg)", "GRU"), ("gcn(seed avg)", "GCN"),
                               ("ens(lr+gru+gcn)", "앙상블")):
                r = x[x.model == name].iloc[0]
                base = name.split("(")[0]
                sd = x[(x.model == base) & (x.seed >= 0)]
                out.append({"k": int(k), "model": lab_, "pos": int(r.pos), "roc": r3(r.roc_auc), "pr": r3(r.pr_auc),
                            **{f"r{b}": r3(r[f"recall@{b}%"]) for b in (1, 2, 5, 10)},
                            "roc_sd": r3(sd.roc_auc.std()) if len(sd) else None,
                            "r5_sd": r3(sd["recall@5%"].std()) if len(sd) else None})
        met[t] = out
    d["metrics"] = met

    # A8·12번 감시 운영
    mon = {}
    for t in ("y_tamper", "y_risky"):
        m = pd.read_csv(R + f"monitor_{t}.csv")
        m = m[m.k.isin([5, 10])]
        mon[t] = [{"k": int(r.k), "scorer": r.scorer, "budget": r.budget, "recall": r3(r.recall), "lo": r3(r.ci_lo),
                   "hi": r3(r.ci_hi), "prec": r3(r.precision), "lead": None if pd.isna(r.median_lead_steps) else r.median_lead_steps} for r in m.itertuples()]
    d["monitor"] = mon
    c = pd.read_csv(R + "monitor_contact.csv")
    d["contact"] = [{"k": int(r.k), "scorer": r.scorer, "contact": bool(r.prior_test_contact), "pos": int(r.pos),
                     "share": r3(r.share_of_pos), "recall": r3(r._7)} for r in c.itertuples()]

    # A9 일반화·단변량
    d["cross_model"] = {t: [{"k": int(r.k), "model": r.held_out_model.replace("swe-agent-llama-", ""), "n": int(r.n),
                             "roc": r3(r.roc_auc)} for r in pd.read_csv(R + f"cross_model_{t}.csv").itertuples()
                            if r.k in (5, 10)] for t in ("y_tamper", "y_risky")}
    fe = pd.read_csv(R + "sec_feature_effects.csv")
    fe = fe[(fe.target == "y_tamper") & (fe.k == 10)].set_index("feature")
    d["univariate"] = [{"feature": f, "pos": r3(fe.loc[f, "nz_pos"]), "neg": r3(fe.loc[f, "nz_neg"])}
                       for f in ("n_create", "s_edit_then_python", "s_last5_test_ctx", "s_open_test", "s_fail_to_test",
                                 "s_edit_err_nav")]

    # A11 보조: 실패 조기 예측
    om = pd.read_csv(R + "metrics.csv")
    d["old_metrics"] = [{"k": int(r.k), "model": r.model, "roc": r3(r.roc_auc)}
                        for r in om[om.split == "holdout"].itertuples()]
    ph = pd.read_csv(R + "policy_holdout_p_ens.csv")
    ph = ph[ph.policy == "tuned_early_stop"]
    d["old_policy"] = [{"unit": r.unit, "budget": int(r.budget_steps), "solve": r3(r.solve_rate),
                        "vs_random": r3(r.diff_vs_random_retry), "vs_cap": r3(r.diff_vs_best_cap)} for r in ph.itertuples()]

    json.dump(d, open("slides/data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    graph_example(feat)
    print("slides/data.json, slides/figs/graph_example.png")


def graph_example(feat, k=10):
    """변조 실행 1건과 정상(성공) 실행 1건의 앞 k단계를 행동 전이 그래프로 그린다(GCN 입력과 같은 구성)."""
    cache = np.load("data/seqs_sec.npz")
    f = feat[feat.k == k]
    tam = f[(f.y_tamper == 1) & (f.t_tamper > k + 2) & (f.s_edit_err_nav >= 2) & (f.s_edit_then_python == 0)]
    ok = f[(f.y_tamper == 0) & f.target & (f.s_edit_then_python >= 2) & (f.s_edit_err_nav == 0)]
    picks = [(tam.traj_id.iloc[0], "변조 실행 (변조 직전)"), (ok.traj_id.iloc[0], "정상 실행 (해결)")]
    used = sorted({int(t) for tid, _ in picks for t in cache["toks"][tid, :k] if t >= 0})
    ang = np.linspace(0, 2 * np.pi, len(used), endpoint=False) + np.pi / 2
    pos = {t: (np.cos(a), np.sin(a)) for t, a in zip(used, ang)}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, (tid, title) in zip(axes, picks):
        toks, nums = cache["toks"][tid, :k], cache["nums"][tid, :k].astype(float)
        cnt, err, edges = {}, {}, {}
        for i, t in enumerate(toks):
            if t < 0:
                break
            cnt[t] = cnt.get(t, 0) + 1
            err[t] = err.get(t, 0) + nums[i, 2]
            if i + 1 < k and toks[i + 1] >= 0:
                edges[(t, toks[i + 1])] = edges.get((t, toks[i + 1]), 0) + 1
        for (a, b), w in edges.items():
            (x0, y0), (x1, y1) = pos[a], pos[b]
            if a == b:
                ax.add_patch(plt.Circle((x0 * 1.13, y0 * 1.13), 0.07, fill=False, lw=1 + w, color="#6b7280"))
                continue
            ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", lw=0.8 + 1.2 * w, color="#6b7280",
                                                                 shrinkA=15, shrinkB=15,
                                                                 connectionstyle="arc3,rad=0.15"))
        for t in used:
            x, y = pos[t]
            n = cnt.get(t, 0)
            fc = "#e5e7eb" if n == 0 else ("#dc2626" if err[t] / n >= 0.5 else "#0f766e")
            ax.scatter([x], [y], s=700 if n else 380, color=fc, zorder=3, edgecolors="white", linewidths=1.5)
            ha = "left" if x > 0.2 else "right" if x < -0.2 else "center"  # 라벨은 노드 바깥쪽에
            ax.text(x * 1.2 + (0.12 if ha == "left" else -0.12 if ha == "right" else 0),
                    y * 1.2 + (0.12 if ha == "center" and y > 0 else -0.2 if ha == "center" else 0), f"{TOK[t]}" + (f" ×{n}" if n else ""),
                    ha=ha, va="center", fontsize=13, fontweight="bold" if n else "normal",
                    color="#111827" if n else "#9ca3af")
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.set_xlim(-2.1, 2.1)
        ax.set_ylim(-1.45, 1.55)
        ax.axis("off")
    fig.text(0.5, 0.02, "노드 = 행동, 굵기 = 전이 횟수, 빨강 = 절반 이상 오류, 회색 = 미사용 (앞 10단계)",
             ha="center", fontsize=12, color="#4b5563")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig("slides/figs/graph_example.png", dpi=200)


if __name__ == "__main__":
    main()
