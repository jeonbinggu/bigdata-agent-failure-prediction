"""E5 시퀀스(GRU)·그래프(GCN) 사전 경고 모델. LightGBM(02_train.py)과 같은 행·같은 홀드아웃에서 비교.

- 입력 캐시 data/seqs_sec.npz: 궤적별 앞 30단계의 행동 토큰(edit_test·risky 포함 14종) + 단계별 신호 11개
- GRU: 토큰 임베딩 + 신호 → GRU → (모델 one-hot) → 확률
- GCN: prefix를 행동 전이 그래프(노드 14 = 행동 종류, 간선 = 전이 횟수)로 바꿔 2층 GCN + mean/max readout
- 앙상블: LR·GRU·GCN 확률(각각 isotonic 보정) 평균. LR은 dev 교차검증에서 LightGBM보다 앞서 표 형식 대표로 씀
사용: TARGET=y_tamper python 09_seq_graph.py   (먼저 02_train.py를 같은 TARGET으로 실행)
출력: results/seqgraph_metrics_{TARGET}.csv, results/holdout_preds_{TARGET}.parquet 에 p_gru·p_gcn·p_ens 열 추가
"""
import glob
import importlib.util
import math
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn

spec = importlib.util.spec_from_file_location("sf", "08_sec_features.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
FM, L, F = S.FM, S.L, S.F

TARGET = os.environ.get("TARGET", "y_tamper")
SEQ, KS, SEED = 30, (5, 10, 20, 30), 0
NT, NN = len(FM.TOK), 11
BUDGETS = (0.01, 0.02, 0.05, 0.10)
torch.manual_seed(SEED)
torch.set_num_threads(os.cpu_count())


def build_cache(path="data/seqs_sec.npz"):
    if os.path.exists(path):
        return dict(np.load(path))
    toks, nums = [], []
    for fp in sorted(glob.glob("data/raw/**/*.parquet", recursive=True)):
        for b in pq.ParquetFile(fp).iter_batches(batch_size=256, columns=["trajectory"]):
            for tr in b.column(0).to_pylist():
                st = F.steps_of(tr)[:SEQ]
                tok, fail = FM.tokens(st)
                t = np.full(SEQ, -1, np.int8)
                x = np.zeros((SEQ, NN), np.float16)
                prev = None
                for i, (s, tk, fl) in enumerate(zip(st, tok, fail)):
                    a, arg, ai, obs, open_file, cmd = s
                    t[i] = FM.T2I[tk]
                    x[i] = [math.log1p(len(ai)) / 10, math.log1p(len(obs)) / 10, fl, F.SYNTAX_FAIL in obs,
                            bool(F.NOT_FOUND_RE.search(obs)), arg == prev, bool(F.TEST_PASS_RE.search(obs)),
                            bool(F.TEST_FAIL_RE.search(obs)), bool(open_file) and L.is_test(open_file),
                            bool(FM.KW_RE.search(ai)), tk == "risky"]
                    prev = arg
                toks.append(t)
                nums.append(x)
        print(f"cache {len(toks)}", flush=True)
    d = {"toks": np.stack(toks), "nums": np.stack(nums)}
    np.savez_compressed(path, **d)
    return d


class GRU(nn.Module):
    def __init__(self, n_models):
        super().__init__()
        self.emb = nn.Embedding(NT + 1, 16, padding_idx=0)
        self.gru = nn.GRU(16 + NN, 64, batch_first=True)
        self.head = nn.Sequential(nn.Linear(64 + n_models, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, t, x, adj, nf, m):
        _, h = self.gru(torch.cat([self.emb(t + 1), x], -1))  # 토큰 -1(패딩) → 0
        return self.head(torch.cat([h[-1], m], -1)).squeeze(-1)


class GCN(nn.Module):
    def __init__(self, n_models, nf_dim, hid=32):
        super().__init__()
        self.w1, self.w2 = nn.Linear(nf_dim, hid), nn.Linear(hid, hid)
        self.head = nn.Sequential(nn.Linear(2 * hid + n_models, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, t, x, adj, nf, m):
        h = torch.relu(adj @ self.w1(nf))
        h = torch.relu(adj @ self.w2(h))
        return self.head(torch.cat([h.mean(1), h.max(1).values, m], -1)).squeeze(-1)


def graphs(t, x):
    """prefix → (정규화 인접행렬 B×NT×NT, 노드 특징 B×NT×(NT+3)).
    간선: 전이 횟수(무방향화) + 자기 루프, 대칭 정규화. 노드 특징: one-hot 정체성, 방문 비율, 오류 비율, 테스트 파일 문맥 비율."""
    B, k = t.shape
    A = np.zeros((B, NT, NT), np.float32)
    cnt = np.zeros((B, NT), np.float32)
    err = np.zeros((B, NT), np.float32)
    tst = np.zeros((B, NT), np.float32)
    rows = np.arange(B)
    for i in range(k):
        ok = t[:, i] >= 0
        np.add.at(cnt, (rows[ok], t[ok, i]), 1)
        np.add.at(err, (rows[ok], t[ok, i]), x[ok, i, 2])
        np.add.at(tst, (rows[ok], t[ok, i]), x[ok, i, 8])
        if i + 1 < k:
            ok2 = ok & (t[:, i + 1] >= 0)
            np.add.at(A, (rows[ok2], t[ok2, i], t[ok2, i + 1]), 1)
    A = A + A.transpose(0, 2, 1) + np.eye(NT, dtype=np.float32)
    d = A.sum(2) ** -0.5
    A = d[:, :, None] * A * d[:, None, :]
    c = np.maximum(cnt, 1)
    nf = np.concatenate([np.broadcast_to(np.eye(NT, dtype=np.float32), (B, NT, NT)),
                         (cnt / k)[..., None], (err / c)[..., None], (tst / c)[..., None]], -1)
    return torch.tensor(A), torch.tensor(nf)


def predict(model, inp, bs=4096):
    model.eval()
    with torch.no_grad():
        n = len(inp[0])
        return np.concatenate([torch.sigmoid(model(*(z[i:i + bs] for z in inp))).numpy() for i in range(0, n, bs)])


def train(make, inp, y, va, epochs=20, bs=512, patience=4):
    model = make()
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    tr = np.where(~va)[0]
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((y[tr] == 0).sum() / max((y[tr] == 1).sum(), 1)))
    yt = torch.tensor(y, dtype=torch.float32)
    vi = np.where(va)[0]
    best, state, bad = -1, None, 0
    for ep in range(epochs):
        model.train()
        np.random.default_rng(ep).shuffle(tr)
        for i in range(0, len(tr), bs):
            b = tr[i:i + bs]
            opt.zero_grad()
            loss_fn(model(*(z[b] for z in inp)), yt[b]).backward()
            opt.step()
        score = average_precision_score(y[vi], predict(model, [z[vi] for z in inp]))
        if score > best:
            best, state, bad = score, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(state)
    return model


def scores(y, p):
    top = lambda f: y[np.argsort(-p, kind="stable")[:max(int(len(p) * f), 1)]].sum() / max(y.sum(), 1)  # noqa: E731
    return {"n": len(y), "pos": int(y.sum()), "roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
            **{f"recall@{int(b * 100)}%": top(b) for b in BUDGETS}}


def main():
    cache = build_cache()
    meta = pd.read_parquet("data/labels.parquet").set_index("traj_id")
    models = sorted(meta.model_name.unique())
    hold_path = f"results/holdout_preds_{TARGET}.parquet"
    hold = pd.read_parquet(hold_path).drop(columns=["p_gru", "p_gcn", "p_ens"], errors="ignore")
    dev = pd.read_parquet(f"data/dev_oof_preds_{TARGET}.parquet")
    rows, add = [], []
    for k in KS:
        hk, dk = hold[hold.k == k], dev[dev.k == k]
        if dk[TARGET].sum() < 100:  # 양성이 너무 적으면 신경망 학습·조기 종료가 불안정해 건너뛴다
            print(f"k={k}: dev 양성 {int(dk[TARGET].sum())}건 → 건너뜀", flush=True)
            continue
        ids = np.concatenate([dk.traj_id.values, hk.traj_id.values])
        y = np.concatenate([dk[TARGET].values, hk[TARGET].values]).astype(int)
        is_h = np.r_[np.zeros(len(dk), bool), np.ones(len(hk), bool)]
        dev_inst = np.array(sorted(dk.instance_id.unique()))
        val_inst = np.random.default_rng(1).choice(dev_inst, size=len(dev_inst) // 10, replace=False)
        is_v = np.r_[np.isin(dk.instance_id.values, val_inst), np.zeros(len(hk), bool)]
        tk = cache["toks"][ids, :k].astype(np.int64)
        xk = cache["nums"][ids, :k].astype(np.float32)
        adj, nf = graphs(tk, xk)
        m = torch.tensor(np.eye(len(models), dtype=np.float32)[meta.loc[ids, "model_name"].map(models.index).values])
        inp = [torch.tensor(tk), torch.tensor(xk), adj, nf, m]
        d = np.where(~is_h)[0]
        h = np.where(is_h)[0]
        out = {"traj_id": hk.traj_id.values, "k": k}
        for name, make in (("gru", lambda: GRU(len(models))), ("gcn", lambda: GCN(len(models), nf.shape[-1]))):
            torch.manual_seed(SEED)
            mdl = train(make, [z[d] for z in inp], y[d], is_v[d])
            v = d[is_v[d]]
            iso = IsotonicRegression(out_of_bounds="clip").fit(predict(mdl, [z[v] for z in inp]), y[v])
            p_raw = predict(mdl, [z[h] for z in inp])
            out[f"p_{name}"] = iso.predict(p_raw)
            rows.append({"k": k, "model": name, **scores(y[h], p_raw)})
        # 표 형식 대표는 dev 교차검증(cv_oof_xfit)에서 앞선 LR (희귀 양성에서 LightGBM이 과적합)
        out["p_ens"] = (hk.p_lr.values + out["p_gru"] + out["p_gcn"]) / 3
        for name in ("lr", "lgbm"):
            rows.append({"k": k, "model": name, **scores(y[h], hk[f"p_{name}"].values)})
        rows.append({"k": k, "model": "ens(lr+gru+gcn)", **scores(y[h], out["p_ens"])})
        add.append(pd.DataFrame(out))
        print(pd.DataFrame(rows[-5:]).round(4).to_string(index=False), flush=True)
    pd.DataFrame(rows).to_csv(f"results/seqgraph_metrics_{TARGET}.csv", index=False)
    hold.merge(pd.concat(add), on=["traj_id", "k"], how="left").to_parquet(hold_path, index=False)


if __name__ == "__main__":
    main()
