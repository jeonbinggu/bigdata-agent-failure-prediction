"""소형 GRU: 처음 k단계의 행동 ID 시퀀스 + 단계별 수치 신호로 성공 예측. LightGBM과 같은 홀드아웃으로 비교.

1) 원본 parquet에서 앞 30단계 시퀀스를 뽑아 data/seqs.npz에 캐시
2) k마다 dev(홀드아웃 제외)로 학습(dev의 10% 과제로 early stopping), 홀드아웃 평가
3) GRU + LightGBM 확률 평균 앙상블도 평가
출력: results/gru_metrics.csv
"""
import glob
import importlib.util
import math
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from torch import nn

spec = importlib.util.spec_from_file_location("feat", "01_features.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

L, KS, SEED = 30, (5, 10, 20, 30), 0
OOF = "--oof" in sys.argv  # dev OOF 예측까지 만들어 정책용 파일에 추가 (학습 5배)
A2I = {a: i + 1 for i, a in enumerate(F.ACTIONS)}  # 0 = padding
N_NUM = 8
torch.manual_seed(SEED)
torch.set_num_threads(os.cpu_count())


def step_vec(st, prev_arg):
    a, arg, ai, obs, _, _ = st
    return [math.log1p(len(ai)) / 10, math.log1p(len(obs)) / 10,
            float(bool(F.ERR_RE.search(obs))), float(F.SYNTAX_FAIL in obs),
            float(bool(F.NOT_FOUND_RE.search(obs))), float(arg == prev_arg),
            float(bool(F.TEST_PASS_RE.search(obs))), float(bool(F.TEST_FAIL_RE.search(obs)))]


def build_cache(path="data/seqs.npz"):
    if os.path.exists(path):
        return dict(np.load(path, allow_pickle=True))
    acts, nums, ids = [], [], []
    files = sorted(glob.glob("data/raw/**/*.parquet", recursive=True))
    tid = 0
    for fp in files:
        for batch in pq.ParquetFile(fp).iter_batches(batch_size=256, columns=["trajectory"]):
            for r in batch.to_pylist():
                steps = F.steps_of(r["trajectory"])[:L]
                a = np.zeros(L, np.int8)
                x = np.zeros((L, N_NUM), np.float16)
                prev = None
                for i, st in enumerate(steps):
                    a[i] = A2I[st[0]]
                    x[i] = step_vec(st, prev)
                    prev = st[1]
                acts.append(a), nums.append(x), ids.append(tid)
                tid += 1
            print(f"cache {tid}", flush=True)
    d = {"acts": np.stack(acts), "nums": np.stack(nums), "traj_id": np.array(ids)}
    np.savez_compressed(path, **d)
    return d


class GRU(nn.Module):
    def __init__(self, n_models):
        super().__init__()
        self.emb = nn.Embedding(len(A2I) + 1, 16, padding_idx=0)
        self.gru = nn.GRU(16 + N_NUM, 64, batch_first=True)
        self.head = nn.Sequential(nn.Linear(64 + n_models, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, a, x, m):
        _, h = self.gru(torch.cat([self.emb(a), x], -1))
        return self.head(torch.cat([h[-1], m], -1)).squeeze(-1)


def predict(model, a, x, m, bs=4096):
    model.eval()
    with torch.no_grad():
        return np.concatenate([torch.sigmoid(model(a[i:i + bs], x[i:i + bs], m[i:i + bs])).numpy()
                               for i in range(0, len(a), bs)])


def train(a, x, m, y, va, epochs=15, bs=512, patience=3):
    """va: 검증용 boolean mask. 검증 PR-AUC 기준 early stopping."""
    model = GRU(m.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    pw = torch.tensor((y[~va] == 0).sum() / max((y[~va] == 1).sum(), 1))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pw)
    tr = np.where(~va)[0]
    yt = torch.tensor(y, dtype=torch.float32)
    best, best_state, bad = -1, None, 0
    for ep in range(epochs):
        model.train()
        np.random.default_rng(ep).shuffle(tr)
        for i in range(0, len(tr), bs):
            b = tr[i:i + bs]
            opt.zero_grad()
            loss_fn(model(a[b], x[b], m[b]), yt[b]).backward()
            opt.step()
        score = average_precision_score(y[va], predict(model, a[va], x[va], m[va]))
        if score > best:
            best, best_state, bad = score, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    return model


def ece(y, p, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any())


def main():
    cache = build_cache()
    meta = pd.read_parquet("data/meta.parquet").set_index("traj_id")
    # 02_train.py와 같은 홀드아웃 재현
    inst = pd.read_parquet("data/features.parquet", columns=["instance_id"])["instance_id"].unique()
    rng = np.random.default_rng(SEED)
    hold = set(rng.choice(inst, size=int(len(inst) * 0.2), replace=False))
    dev_inst = np.array(sorted(set(inst) - hold))
    val_inst = set(np.random.default_rng(1).choice(dev_inst, size=len(dev_inst) // 10, replace=False))

    models = sorted(meta.model_name.unique())
    M = np.eye(len(models), dtype=np.float32)[meta.loc[cache["traj_id"], "model_name"].map(models.index).values]
    y_all = meta.loc[cache["traj_id"], "target"].values.astype(int)
    n_all = meta.loc[cache["traj_id"], "n_steps"].values
    iid = meta.loc[cache["traj_id"], "instance_id"].values
    is_hold = np.isin(iid, list(hold))
    is_val = np.isin(iid, list(val_inst))
    lgbm = pd.read_parquet("results/holdout_preds.parquet")

    rows, dev_out, hold_out = [], [], []
    for k in KS:
        sel = n_all > k
        a = torch.tensor(cache["acts"][sel, :k], dtype=torch.long)
        x = torch.tensor(cache["nums"][sel, :k].astype(np.float32))
        m = torch.tensor(M[sel])
        y, h, v = y_all[sel], is_hold[sel], is_val[sel]
        dev = ~h
        model = train(a[dev], x[dev], m[dev], y[dev], v[dev])
        p_val = predict(model, a[dev & v], x[dev & v], m[dev & v])
        iso = IsotonicRegression(out_of_bounds="clip").fit(p_val, y[dev & v])
        p_raw = predict(model, a[h], x[h], m[h])
        p = iso.predict(p_raw)
        yh = y[h]
        rows.append({"k": k, "model": "gru", "n": len(yh), "roc_auc": roc_auc_score(yh, p_raw),
                     "pr_auc": average_precision_score(yh, p_raw), "ece": ece(yh, p)})

        # LightGBM(isotonic)과 평균 앙상블
        tids = cache["traj_id"][sel][h]
        lg = lgbm[lgbm.k == k].set_index("traj_id").loc[tids, "p_lgbm"].values
        ens = (p + lg) / 2
        rows.append({"k": k, "model": "lgbm", "n": len(yh), "roc_auc": roc_auc_score(yh, lg),
                     "pr_auc": average_precision_score(yh, lg), "ece": ece(yh, lg)})
        rows.append({"k": k, "model": "gru+lgbm", "n": len(yh), "roc_auc": roc_auc_score(yh, ens),
                     "pr_auc": average_precision_score(yh, ens), "ece": ece(yh, ens)})
        print(pd.DataFrame(rows[-3:]).round(4).to_string(index=False), flush=True)

        if OOF:
            # 정책 τ 튜닝용 dev OOF: 과제 단위 5-fold, 각 fold 안에서도 10% 과제로 early stopping
            di = np.where(dev)[0]
            oof = np.zeros(len(di))
            for f, (tr, va) in enumerate(GroupKFold(5).split(di, groups=iid[sel][di])):
                tr_inst = np.unique(iid[sel][di[tr]])
                pick = np.random.default_rng(f).choice(tr_inst, size=len(tr_inst) // 10, replace=False)
                inner_val = np.isin(iid[sel][di[tr]], pick)
                mf = train(a[di[tr]], x[di[tr]], m[di[tr]], y[di[tr]], inner_val)
                oof[va] = predict(mf, a[di[va]], x[di[va]], m[di[va]])
            folds = list(GroupKFold(5).split(di, groups=iid[sel][di]))
            p_dev = np.zeros(len(di))
            for tr, va in folds:  # cross-fit isotonic
                p_dev[va] = IsotonicRegression(out_of_bounds="clip").fit(oof[tr], y[di][tr]).predict(oof[va])
            dtid = cache["traj_id"][sel][di]
            dev_out.append(pd.DataFrame({"traj_id": dtid, "k": k, "p_gru": p_dev}))
            hold_out.append(pd.DataFrame({"traj_id": tids, "k": k, "p_gru": p}))

    pd.DataFrame(rows).to_csv("results/gru_metrics.csv", index=False)
    if OOF:
        # 앙상블 = (GRU + LightGBM)/2 를 기존 예측 파일에 열로 추가 → 03_policy.py p_ens 로 사용
        for path, extra in (("data/dev_oof_preds.parquet", dev_out), ("results/holdout_preds.parquet", hold_out)):
            base = pd.read_parquet(path).drop(columns=["p_gru", "p_ens"], errors="ignore")
            base = base.merge(pd.concat(extra), on=["traj_id", "k"], how="left")
            base["p_ens"] = (base.p_gru + base.p_lgbm) / 2
            base.to_parquet(path, index=False)


if __name__ == "__main__":
    main()
