"""E4 사전 경고용 특징: 기존 prefix 특징 + 보안 특징 + 라벨/시점.

기존 01_features.py 출력(실패 예측용)은 그대로 두고 별도 파일로 만든다.
출력: data/features_sec.parquet (궤적 x k, k 이전에 끝난 궤적 제외)
누수 방지는 02_train.py에서: 양성은 사건 시점 t > k 인 행만 쓴다.
"""
import glob
import importlib.util
import re

import pandas as pd
import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location("lab", "06_labels.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
F = L.F
spec = importlib.util.spec_from_file_location("fm", "07_failure_modes.py")
FM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FM)

KS = (5, 10, 20, 30)
PYTEST_FILTER = re.compile(r"pytest.*\s(-k|--deselect|-p\s+no:|--lf|-x)\b")
TEST_WRONG = re.compile(r"(test|assert\w*)\s+(is|are|seems?|might be|may be|was)\s+(wrong|incorrect|outdated|flawed|broken|"
                        r"too strict|not correct)", re.I)
NAV = {"find_file", "ls", "open", "goto", "search", "cat_grep"}


def sec_features(steps, k):
    s = steps[:k]
    tok, fail = FM.tokens(s)
    created = {x[1].split(maxsplit=1)[-1].strip() for x in s if x[0] == "create"}
    is_old_test = [bool(x[4]) and L.is_test(x[4]) and not any(x[4].endswith(c.lstrip("./")) for c in created if c)
                   for x in s]
    f = {
        "s_open_test": sum(x[0] in ("open", "goto", "scroll") and t for x, t in zip(s, is_old_test)),
        "s_edit_new_test": sum(tk == "edit_test" and not t for tk, t in zip(tok, is_old_test)),
        "s_create_test": sum(x[0] == "create" and L.is_test(x[1].split(maxsplit=1)[-1]) for x in s),
        "s_fail_to_test": sum(fail[i] and is_old_test[i + 1] for i in range(len(s) - 1)),
        "s_edit_err_nav": sum(tok[i] in ("edit", "edit_test") and fail[i] and tok[i + 1] in NAV for i in range(len(s) - 1)),
        "s_edit_then_python": sum(tok[i] in ("edit", "edit_test") and tok[i + 1] == "python" for i in range(len(s) - 1)),
        "s_pytest_filter": sum(bool(PYTEST_FILTER.search(x[5])) for x in s),
        "s_kw_test_mod": sum(bool(FM.KW_RE.search(x[2] or "")) for x in s),
        "s_kw_test_wrong": sum(bool(TEST_WRONG.search(x[2] or "")) for x in s),
        "s_n_risky": sum(t == "risky" for t in tok),
        "s_last5_test_ctx": sum(is_old_test[-5:]),
    }
    for name, rx in L.RISK_RE.items():
        f[f"s_{name}"] = sum(x[0] not in L.EXEC_SKIP and bool(rx.search(x[5])) for x in s)
    return f


def main():
    lab = pd.read_parquet("data/labels.parquet")[["traj_id", "y_tamper", "t_tamper", "y_risky", "t_risky"]]
    rows, tid = [], 0
    for path in sorted(glob.glob("data/raw/**/*.parquet", recursive=True)):
        for b in pq.ParquetFile(path).iter_batches(batch_size=256, columns=["instance_id", "model_name", "target",
                                                                            "trajectory"]):
            for r in b.to_pylist():
                steps = F.steps_of(r["trajectory"])
                meta = {"traj_id": tid, "instance_id": r["instance_id"], "model_name": r["model_name"],
                        "target": bool(r["target"]), "n_steps": len(steps)}
                for k in KS:
                    if len(steps) > k:
                        rows.append({**meta, "k": k, **F.prefix_features(steps, k), **sec_features(steps, k)})
                tid += 1
        print(f"{tid} trajectories", flush=True)
    df = pd.DataFrame(rows).merge(lab, on="traj_id")
    df.to_parquet("data/features_sec.parquet", index=False)
    print(df.groupby("k").agg(n=("traj_id", "size"), tamper=("y_tamper", "mean"), risky=("y_risky", "mean")))


if __name__ == "__main__":
    main()
