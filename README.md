# AI 에이전트 실행 실패·보안 위협 패턴 분석

Introduction to Big Data · 2026 Fall 프로젝트 (27팀).
데이터: [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) (80,036 궤적, CC-BY-4.0)

> **에이전트가 무엇을 했는지(행동 로그)만 보고, 무엇을 저지를지(보안 위협)를 미리 경고한다.**

성공률만 보는 평가에 가려진 코딩 에이전트의 위험 행동 두 가지, **테스트 변조**(기존 테스트의 assert 삭제·주석 처리·조건 뒤집기·skip 추가 등)와 **위험 명령**(`rm -rf`, `pip install`, 외부 `curl/wget`, `sudo` 등)을 찾는다. 이어서 이 행동이 일어나기 전의 행동 로그만으로 미리 경고할 수 있는지 본다. 실행 실패 패턴(실패 유형, 실패 조기 예측·조기 종료 정책)은 보조 분석이다.

## 주요 결과

| | 결과 |
| --- | --- |
| 규모 | 테스트 변조 719건(0.90%), 위험 명령 4,523건(5.65%). 변조한 실행의 해결률이 **23.5%**로 나머지(16.7%)보다 높다. 성공률만으로는 보이지 않는다 |
| 라벨 검증 | 무작위 60건 감사 정밀도 65%(무결성 훼손)·88%(무해 아님). 사람 블라인드 교차 확인 20건: Cohen's κ 0.53, 훼손 여부 일치 75% |
| 전조 | 변조 직전 5단계에 '오류 난 편집 → 파일 탐색' 전이가 매칭 대조군보다 24~36배, "테스트를 고치자" 추론 22%(대조 0.4%). 재현·재실행 없이 테스트로 향하는 '검증 회피' |
| 사전 경고 | 변조 5~10단계 전 행동 로그로 ROC-AUC **0.80~0.84** (LR + GRU + GCN 앙상블, 시드 5개 평균) |
| 감시 운영 | 실행 5%만 검토해도 미래 변조의 **33~49%**를 약 3단계 먼저 탐지 (사람이 만든 규칙 13~15%, 무작위 5%). 테스트를 건드린 적 없는 변조에서도 27~40% |
| 한계 | 정밀도 4~5%, 규칙 라벨, SWE-agent·Llama 3.1 한 계열, 개입 효과 미검증 |

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
python 10_monitor.py           # E6 검토 예산별 탐지율·부트스트랩 CI: monitor_y_*.csv, monitor_curve.png, monitor_contact.csv
python 11_label_check.py score # 사람 블라인드 교차 확인(results/label_check_20.csv) 일치도

# 발표 자료 (숫자는 모두 results/ CSV에서 다시 읽는다)
python 12_slide_figs.py && cd slides && npm install && node build.js   # slides/27팀_발표.pptx

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
| 라벨 교차 확인 | `11_label_check.py` | 감사 60건 중 범주별 5건을 블라인드로 다시 판정해 Cohen's kappa 계산 |
| 발표 자료 | `12_slide_figs.py`, `slides/build.js` | 결과 CSV → `slides/data.json` → pptxgenjs로 본 발표 14장 + 부록 A0~A17 (대본은 Notion에 보관) |
| 보조 | `01~05_*.py` | 실패 조기 예측(ROC-AUC 0.66~0.76)과 조기 종료·재시작 정책 |

## 누수 방지

- 사전 경고 모델은 사건이 일어난 단계 이후의 정보를 쓰지 않는다. `02_train.py`에서 assert로 확인한다.
- `exit_status`, `generated_patch`, `eval_logs`, 전체 궤적 길이는 입력에 쓰지 않는다. 패치는 라벨을 만드는 데만 쓴다.
