# 행동 로그 기반 AI 에이전트 작업 실패 조기 예측 및 조기 종료·재시작 정책

Introduction to Big Data · 2026 Fall 프로젝트.
데이터: [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) (80,036 궤적, CC-BY-4.0)

## 실행

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('nebius/SWE-agent-trajectories', repo_type='dataset', local_dir='data/raw', allow_patterns=['*.parquet'])"

python 01_features.py   # data/features.parquet, data/meta.parquet
python 02_train.py      # results/metrics.csv, holdout_preds.parquet, importance_k*.csv, 그래프
python 03_policy.py     # results/policy_dev.csv, policy_holdout.csv(부트스트랩 CI), policy_tradeoff.png
python 04_gru.py --oof  # GRU + dev OOF → 예측 파일에 p_gru, p_ens 추가
python 03_policy.py p_ens   # 앙상블 확률로 정책 (출력 *_p_ens.*)
python 04_gru.py --seeds 5  # GRU 시드 분산 평가 → results/gru_seeds.csv
python 05_oracle.py         # 천장: 오라클 정책(정답을 k에서 미리 앎) + 해결 가능 비율 → results/oracle_holdout.csv
KS=5,10,20,30 python 03_policy.py p_ens  # k=5 체크포인트 추가 (출력 *_p_ens_k5.*)
```

## 파이프라인

| 단계 | 파일 | 내용 |
| --- | --- | --- |
| 특징 추출 | `01_features.py` | 1단계 = ai 메시지 + 관찰. k ∈ {5,10,20,30} prefix에서 행동 분포·반복·오류·진행·길이 특징. k 이전에 끝난 궤적은 해당 k에서 제외 |
| 예측 | `02_train.py` | 과제(`instance_id`) 단위 홀드아웃 20% + GroupKFold(5). 로지스틱 회귀 / LightGBM, OOF 기반 isotonic 보정, TreeSHAP 중요도, 모델 간 일반화 평가 |
| 시퀀스 | `04_gru.py` | 행동 ID + 단계별 신호 시퀀스로 소형 GRU, LightGBM과 평균 앙상블 |
| 정책 | `03_policy.py` | 예산(단계 수 / 글자 수 / 누적 컨텍스트) 안에서 조기 종료·재시작 정책을 single / 고정 상한 / 무작위 재시도와 비교. τ와 cap은 dev OOF에서 고르고 홀드아웃에서 과제 단위 부트스트랩 95% CI로 평가 |

## 누수 방지

`exit_status`, `generated_patch`, `eval_logs`, 전체 궤적 길이는 입력에 쓰지 않습니다. k단계까지의 정보만 사용합니다.
`n_steps`는 정책 시뮬레이션에서 비용 계산에만 씁니다.
