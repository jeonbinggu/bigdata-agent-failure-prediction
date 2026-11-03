"""궤적 parquet를 스트리밍으로 읽어 처음 k단계 prefix 특징을 추출한다.

출력: data/features.parquet  (궤적 x k 한 행, k 이전에 끝난 궤적은 해당 k에서 제외)
사용: python 01_features.py [--limit N]
"""
import argparse
import glob
import math
import re
from collections import Counter

import pandas as pd
import pyarrow.parquet as pq

KS = (5, 10, 20, 30)
ACTIONS = ["open", "goto", "scroll", "search", "find_file", "edit", "create",
           "python", "submit", "ls", "cat_grep", "other"]
CODE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
OPEN_FILE_RE = re.compile(r"\(Open file: ([^)]*)\)")
ERR_RE = re.compile(r"Traceback|Error|Exception")
SYNTAX_FAIL = "Your proposed edit has introduced new syntax error"
NOT_FOUND_RE = re.compile(r"not found|No such file|No matches found", re.I)


def action_of(ai_text):
    blocks = CODE_RE.findall(ai_text or "")
    cmd = blocks[-1].strip() if blocks else ""
    tok = cmd.split(maxsplit=1)[0] if cmd else ""
    if tok.startswith("scroll_"):
        a = "scroll"
    elif tok in ("search_dir", "search_file"):
        a = "search"
    elif tok in ("python", "python3", "pytest"):
        a = "python"
    elif tok in ("grep", "cat", "head", "tail", "find") or tok.startswith("find."):
        a = "cat_grep"
    elif tok in ACTIONS:
        a = tok
    else:
        a = "other"
    arg = cmd.split("\n", 1)[0]  # 첫 줄(명령+인자)로 반복 여부 판정
    return a, arg


def steps_of(traj):
    """[(action, arg, ai_text, obs_text, open_file_before)] — system/이슈 메시지 제외."""
    steps, open_file = [], None
    msgs = [m for m in traj if m["role"] in ("ai", "user")]
    # 첫 user 메시지는 이슈 본문
    i = 1 if msgs and msgs[0]["role"] == "user" else 0
    while i < len(msgs):
        if msgs[i]["role"] != "ai":
            i += 1
            continue
        ai = msgs[i]["text"] or ""
        obs = msgs[i + 1]["text"] or "" if i + 1 < len(msgs) and msgs[i + 1]["role"] == "user" else ""
        a, arg = action_of(ai)
        steps.append((a, arg, ai, obs, open_file))
        m = OPEN_FILE_RE.findall(obs)
        if m:
            open_file = m[-1]
        i += 2 if obs else 1
    return steps


def prefix_features(steps, k):
    s = steps[:k]
    acts = [x[0] for x in s]
    cnt = Counter(acts)
    f = {f"n_{a}": cnt.get(a, 0) for a in ACTIONS}
    f.update({f"r_{a}": cnt.get(a, 0) / k for a in ACTIONS})
    probs = [c / k for c in cnt.values()]
    f["action_entropy"] = -sum(p * math.log(p) for p in probs)
    f["n_unique_actions"] = len(cnt)

    run = best = 1
    for a, b in zip(acts, acts[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    f["max_same_action_run"] = best
    args = [x[1] for x in s]
    f["n_exact_repeat"] = sum(a == b for a, b in zip(args, args[1:]))
    opened = Counter(x[1] for x in s if x[0] == "open")
    f["n_unique_opened"] = len(opened)
    f["max_open_same_file"] = max(opened.values(), default=0)

    obs = [x[3] for x in s]
    f["n_error_obs"] = sum(bool(ERR_RE.search(o)) for o in obs)
    f["n_syntax_fail"] = sum(SYNTAX_FAIL in o for o in obs)
    f["n_not_found"] = sum(bool(NOT_FOUND_RE.search(o)) for o in obs)

    edit_idx = [i for i, a in enumerate(acts) if a == "edit"]
    f["first_edit_step"] = edit_idx[0] + 1 if edit_idx else k + 1
    f["ran_python"] = int(cnt.get("python", 0) > 0)
    f["n_edited_files"] = len({s[i][4] for i in edit_idx if s[i][4]})

    ai_len = [len(x[2]) for x in s]
    f["ai_chars_total"] = sum(ai_len)
    f["ai_chars_mean"] = sum(ai_len) / k
    f["obs_chars_total"] = sum(len(o) for o in obs)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="data/features.parquet")
    args = ap.parse_args()

    rows, metas, seen = [], [], 0
    files = sorted(glob.glob("data/raw/**/*.parquet", recursive=True))
    for path in files:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=256, columns=["instance_id", "model_name", "target", "trajectory"]):
            for r in batch.to_pylist():
                steps = steps_of(r["trajectory"])
                meta = {"traj_id": seen, "instance_id": r["instance_id"], "model_name": r["model_name"],
                        "target": bool(r["target"]), "n_steps": len(steps)}  # n_steps는 정책 비용용, 특징 아님
                metas.append(meta)
                for k in KS:
                    if len(steps) > k:  # k단계 시점에 아직 실행 중인 궤적만
                        rows.append({**meta, "k": k, **prefix_features(steps, k)})
                seen += 1
                if args.limit and seen >= args.limit:
                    break
            print(f"{seen} trajectories", flush=True)
            if args.limit and seen >= args.limit:
                break
        if args.limit and seen >= args.limit:
            break

    df = pd.DataFrame(rows)
    df.to_parquet(args.out, index=False)
    pd.DataFrame(metas).to_parquet("data/meta.parquet", index=False)  # 전체 궤적(짧은 것 포함), 정책 시뮬레이션용
    print(df.groupby("k").agg(n=("target", "size"), success=("target", "mean")))


if __name__ == "__main__":
    main()
