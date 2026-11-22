# AI 에이전트 실행 실패·보안 위협 패턴 분석

Introduction to Big Data · 2026 Fall 프로젝트 (27팀).
데이터: [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) (80,036 궤적, CC-BY-4.0)

성공률만 보는 평가에 가려진 코딩 에이전트의 위험 행동 두 가지, **테스트 변조**(기존 테스트의 assert 삭제·주석 처리·조건 뒤집기·skip 추가 등)와 **위험 명령**(`rm -rf`, `pip install`, 외부 `curl/wget`, `sudo` 등)을 찾는다. 이어서 이 행동이 일어나기 전의 행동 로그만으로 미리 경고할 수 있는지 본다. 실행 실패 패턴(실패 유형, 실패 조기 예측·조기 종료 정책)은 보조 분석이다.

## 실행

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('nebius/SWE-agent-trajectories', repo_type='dataset', local_dir='data/raw', allow_patterns=['*.parquet'])"

# 보안 위협 (본론)
python 06_labels.py            # E1 라벨: data/labels.parquet, results/label_stats.csv (감사: results/label_audit.csv)
python 07_failure_modes.py     # E2 실패 유형 + E3 위협 패턴: failure_modes.csv, threat_bigram_lift.csv, transition_diff.png ...
python 08_sec_features.py      # E4 특징: data/features_sec.parquet
TARGET=y_tamper FEAT=data/features_sec.parquet python 02_train.py   # E4 LR/LightGBM 사전 경고 (y_risky도 동일)
TARGET=y_tamper python 09_seq_graph.py                              # E5 GRU·GCN·앙상블 (y_risky도 동일)
python 10_monitor.py           # E6 검토 예산별 탐지율·부트스트랩 CI: monitor_y_*.csv, monitor_curve.png

# 실행 실패 예측·조기 종료 정책 (보조)
python 01_features.py && python 02_train.py && python 04_gru.py --oof && python 03_policy.py p_ens && python 05_oracle.py
```

## 파이프라인

| 단계 | 파일 | 내용 |
| --- | --- | --- |
| E1 라벨 | `06_labels.py` | 최종 패치 diff에서 **기존** 테스트 파일의 assert 삭제·변경, 테스트 함수 삭제, skip/xfail 추가, 파일 삭제 → `y_tamper`. 실행된 명령에서 위험 명령 → `y_risky`. 사건 시점 `t_tamper`, `t_risky` |
| E2·E3 기술 분석 | `07_failure_modes.py` | 실패 6유형. 변조 직전 5단계 2-gram lift(매칭 대조군), 추론 키워드, 행동 전이 그래프 차이 |
| E4 표 형식 모델 | `08_sec_features.py`, `02_train.py` | 기존 prefix 특징 + 보안 특징. 사건 시점 t > k인 prefix만 써서 누수 방지. 과제 단위 홀드아웃 20% + GroupKFold(5) |
| E5 시퀀스·그래프 | `09_seq_graph.py` | GRU(행동 토큰 + 단계 신호), GCN(행동 전이 그래프, 순수 torch), LR+GRU+GCN 앙상블 |
| E6 감시 운영 | `10_monitor.py` | 위험 점수 상위 x%만 검토할 때의 재현율, 과제 단위 부트스트랩 95% CI, 단순 규칙과 비교, 경보 후 사건까지 남은 단계 |
| 보조 | `01~05_*.py` | 실패 조기 예측(ROC-AUC 0.66~0.76)과 조기 종료·재시작 정책 |

## 누수 방지

- 사전 경고 모델은 사건이 일어난 단계 이후의 정보를 쓰지 않는다. `02_train.py`에서 assert로 확인한다.
- `exit_status`, `generated_patch`, `eval_logs`, 전체 궤적 길이는 입력에 쓰지 않는다. 패치는 라벨을 만드는 데만 쓴다.
