# 확장 벤치마크·동적 재계획·PPO 실험 결과

요청한 1–3번 비교를 완료한 뒤 4번 Maskable PPO 학습·평가를 수행했다. **현재 PPO로 CP-SAT을 대체할 근거는 없다.** 속도와 품질을 함께 판단해야 하며, 아래 값은 실제 저장 결과로 계산했다.

## 1. 큰 문제에서도 CP-SAT이 충분한가?

MK01–MK10, 솔버 시드 3개, 1/5/30초 제한과 휴리스틱 5종을 합쳐 240회 평가했다. 아래는 30초 제한의 시드 평균이며, optimal_runs는 3회 중 최적성을 증명한 횟수다. BKS는 고정한 공개 저장소의 최선 알려진 상한이다.

| instance | makespan | BKS | gap_percent | optimal_runs |
| --- | --- | --- | --- | --- |
| MK01 | 40.000 | 40 | 0.000 | 3 |
| MK02 | 27.667 | 26 | 6.410 | 0 |
| MK03 | 204.000 | 204 | 0.000 | 3 |
| MK04 | 60.000 | 60 | 0.000 | 3 |
| MK05 | 173.333 | 172 | 0.775 | 0 |
| MK06 | 60.667 | 57 | 6.433 | 0 |
| MK07 | 148.333 | 139 | 6.715 | 0 |
| MK08 | 523.000 | 523 | 0.000 | 3 |
| MK09 | 307.000 | 307 | 0.000 | 3 |
| MK10 | 249.000 | 193 | 29.016 | 0 |

MK01에서의 빠른 최적해가 모든 규모로 일반화되지는 않는다. 다만 이 표의 CP-SAT은 기존 무힌트 모델이다. 후속 목적함수/동적 비교에서는 휴리스틱 초기해와 안전한 fallback을 사용하므로 서로 다른 솔버 구성을 구분해야 한다. 1/5/30초 표의 제한은 솔버 시간이며, 모델 생성 시간을 포함한 실제 runtime도 CSV에 별도로 보존했다.

## 2. 납기와 일정 변경 비용

MK01, 5초 전체 계획 예산, 시드 3개의 평균이다. 일정 변경은 공통 SPT 기준 계획에 대해 계산했다.

| objective | makespan | tardiness | start_shift | machine_changes |
| --- | --- | --- | --- | --- |
| balanced | 40.000 | 17.000 | 409.333 | 15.333 |
| makespan | 40.000 | 68.000 | 467.000 | 18.000 |
| stable | 47.000 | 51.333 | 61.667 | 1.333 |
| tardiness | 42.000 | 14.000 | 365.333 | 10.333 |

makespan만 같아도 납기지연은 크게 달라진다. `stable`은 일정 변경을 억제하는 가중치까지 포함하므로 makespan 또는 납기만으로 좋고 나쁨을 판단할 수 없다. 정규화 식과 정확한 정수 목적함수 변환은 expanded_experiment_protocol.md에 명시했다.

## 3. 고장·신규 주문·복구의 재계획

목적함수 실험 72회와 동적 실험 144회, 합계 216회 평가했다. 동적 실험에는 MK01/MK06, 이벤트 시드 3개, 고장/도착/복합 조건이 포함된다. 아래는 복합 이벤트 조건의 평균이다. planning_ms는 개별 재계획의 평균 실측 지연이다.

| instance | method | objective | budget_s | makespan | tardiness | revision_cost | replanning_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MK01 | CP-SAT | balanced | 1 | 44.333 | 44.333 | 0.194 | 53.034 |
| MK01 | CP-SAT | balanced | 5 | 44.333 | 44.333 | 0.194 | 58.871 |
| MK01 | CP-SAT | stable | 1 | 45.000 | 58.333 | 0.012 | 75.958 |
| MK01 | CP-SAT | stable | 5 | 45.000 | 58.333 | 0.012 | 73.432 |
| MK01 | EDD | stable | 0 | 65.333 | 96.000 | 0.238 | 0.505 |
| MK01 | MWKR | stable | 0 | 51.000 | 149.000 | 0.363 | 0.521 |
| MK01 | Repair | stable | 0 | 62.667 | 97.000 | 0.164 | 0.454 |
| MK01 | SPT | stable | 0 | 64.667 | 87.667 | 0.335 | 0.518 |
| MK06 | CP-SAT | balanced | 1 | 77.667 | 100.667 | 1.019 | 1001.223 |
| MK06 | CP-SAT | balanced | 5 | 71.667 | 43.667 | 0.778 | 4828.688 |
| MK06 | CP-SAT | stable | 1 | 104.667 | 221.667 | 0.165 | 1001.810 |
| MK06 | CP-SAT | stable | 5 | 88.667 | 198.667 | 0.059 | 5002.241 |
| MK06 | EDD | stable | 0 | 109.333 | 228.667 | 0.646 | 3.616 |
| MK06 | MWKR | stable | 0 | 99.333 | 312.000 | 0.960 | 3.898 |
| MK06 | Repair | stable | 0 | 107.333 | 250.667 | 0.628 | 3.571 |
| MK06 | SPT | stable | 0 | 95.000 | 144.667 | 0.847 | 3.469 |

시작된 작업은 고정했고, 고장 중 작업은 같은 설비에서 일시정지·재개했다. 고장 발생 시 복구 예정 시각을 알며 그 예측이 정확하다는 가정이다. 미래 주문/고장은 정책과 솔버에 노출하지 않았다. 시뮬레이션 시간은 계산 중 정지하므로 실제 공장 시간 지연까지 재현했다고 주장하지 않는다. 동적 CP 실행 중 외부 휴리스틱 fallback 선택 횟수는 0회다.

## 4. PPO를 실제로 학습하면?

Maskable PPO + MLP, 학습 시드 5개, 각 32,768스텝(총 163,840스텝)을 실행했다. 생성 학습 문제와 생성 검증/평가 문제를 분리했다. 학습 분포는 4–10 jobs/3–6 machines이고, 패딩 용량은 260 operations/15 machines다. MK01–MK10은 이미 감사한 외부 전이 평가이며 완전히 블라인드인 테스트라고 부르지 않는다. 하이퍼파라미터 탐색 없이 마지막 체크포인트를 평가했다.

| seed | env_steps | training_time_s | checkpoint_bytes |
| --- | --- | --- | --- |
| 0 | 32768.000 | 17.692 | 26045263.000 |
| 1 | 32768.000 | 17.895 | 26045263.000 |
| 2 | 32768.000 | 18.007 | 26045263.000 |
| 3 | 32768.000 | 18.028 | 26045263.000 |
| 4 | 32768.000 | 17.681 | 26045263.000 |

학습 중 검증 값(5개 학습 시드 평균, 검증 문제 4개):

| env_steps | objective | makespan | tardiness |
| --- | --- | --- | --- |
| 0.000 | 1.561 | 113.450 | 333.700 |
| 8192.000 | 0.738 | 63.300 | 96.000 |
| 16384.000 | 0.606 | 54.400 | 52.300 |
| 24576.000 | 0.593 | 53.250 | 47.950 |
| 32768.000 | 0.603 | 54.400 | 47.750 |

CP-SAT 5초 균형 목적함수 대비 PPO의 `(makespan + mean tardiness)` 상대 비용 차이(%): 양수일수록 PPO가 나쁘다. 구간은 문제별 차이를 평균한 **학습 시드 5개**에 대한 t 95% 구간이며 독립 공장 표본의 구간이 아니다.

| scenario | relative_cost_gap_mean | relative_cost_gap_ci95_low | relative_cost_gap_ci95_high |
| --- | --- | --- | --- |
| external_dynamic | 91.105 | 80.623 | 101.586 |
| external_static | 54.482 | 47.748 | 61.215 |
| generated_test | 63.607 | 50.959 | 76.256 |

PPO의 전체 평가 에피소드 수는 130개다. 에피소드별 평균 추론 지연의 평균은 0.152ms, 에피소드별 p95 지연의 최댓값은 0.756ms다. 이는 한 행동의 지연이며 CP-SAT 전체 재계획 시간과 동일 단위 작업이라고 혼동하면 안 된다. 에피소드 전체 계산시간은 별도 CSV와 Figure 6에 비교했다. 학습 비용도 위 표에 포함했다.

생성 평가 문제 10개에 대한 탐색적 paired Wilcoxon p-value는 0.001953다. 각 문제에서 PPO 학습 시드 평균과 CP-SAT 5초를 짝지었다. 튜닝/다중 비교를 엄밀히 통제한 확증 실험이 아니므로 통계적 우월성의 근거로 사용하지 않는다.

PPO는 온라인 작업 배정을 내고, CP-SAT은 미래 계획을 수정한다. PPO의 재계획 안정성은 N/A이며, PPO 품질 비교에서는 CP-SAT의 안정성 가중치를 0으로 맞췄다. 학습이 충분히 수렴했다거나 PPO 일반의 한계를 입증했다고 해석하면 안 된다.

## 검증과 재현성

- 단위/통합 테스트 33개 통과. CPU 체크포인트 재개 후 모든 모델 파라미터가 완전히 일치하는 테스트 포함.
- 저장된 완료 스케줄 716개와 개별 동적 계획 520개를 독립 검사했다. 제약 위반 0건.
- 각 완료 실행의 JSON과 PostgreSQL 및 scalar CSV의 모든 셀 일치 확인. raw 데이터 SHA-256 대조 완료.
- 솔버 응답 목적값 불일치/하한 경고 17건은 감사 JSON에 보존했다. 실제 스케줄과 모델 식을 재계산하고, 불일치하는 최적성 표시는 허용하지 않았다.
- FAT32에서 PostgreSQL 쓰기 오류가 발생해 원래 DB 파일 및 SQL snapshot을 보존했다. 현재 DB는 임시 tmpfs이며 재시작 후 프로젝트의 JSON/CSV로 복구한다. 실험 원본은 외장 프로젝트에 영구 보관된다.
- 단일 호스트에서 두 CP 캠페인이 동시에 실행됐으므로, 절대 지연값은 통제된 실시간 성능 인증으로 해석하지 않는다. PPO 학습은 두 캠페인 완료 후 시작했다.

## 대시보드 원형 게이지

확장 대시보드 상단에 호스트 CPU/메모리 사용률과 CP-SAT 시간 예산 사용률(P95)을 추가했다. 옆 숫자 패널은 개별 계획 계산 시간의 P95다. 100%는 배정된 시간 예산이며 스케줄 품질이나 학습 진행률이 아니다. 예산 게이지는 0–120% 범위이고 실제 숫자는 제한하지 않는다.

동적 실행은 초기 계획과 각 재계획을 개별 관측으로 사용하며, 에피소드 전체 시간을 단일 재계획 예산으로 나누지 않는다. expanded_static은 솔버 시간/솔버 제한, 나머지는 준비·검증을 포함한 계획 시간/전체 계획 예산이다. 선택한 실행 전체를 집계하므로 예산별 상세 표와 함께 해석한다. PPO 파일럿 실행의 118개 CP 계획에서 예산 사용률 P95는 100.129%, 계획 시간 P95는 5001.498ms였다. 저장 JSON으로 별도 계산한 분위수와 Grafana 쿼리 결과가 일치했다.

CPU/메모리는 호스트 전체 지표이고 선택 시간 범위 끝의 관측값이다. 시간 범위가 now로 끝나면 10초마다 갱신된다. RAM은 psutil의 (total - available) / total 비율이다. 수집되지 않은 시점은 N/A로 표시하며 0으로 채우지 않는다.

## 판단

현재 PPO로 CP-SAT을 대체할 근거는 없다. MK01 같은 작은 정적 문제는 CP-SAT이 이미 충분하다. 큰 문제나 짧은 재계획 시간에서의 한계는 확인됐지만, 그 사실만으로 PPO가 더 좋은 선택이 되지는 않는다. 현재 측정 결과를 기준으로 CP-SAT과 검증된 휴리스틱 fallback을 유지하고, PPO는 학습 예산·상태 표현·보상 분산을 개선하는 연구 후보로 다루는 것이 타당하다.

## 실행과 산출물

프로젝트 루트에서:

```bash
bash scripts/setup_training.sh
bash scripts/start_monitoring.sh
bash scripts/python.sh -m pytest -q --basetemp=runtime/pytest-expanded
bash scripts/python.sh -m src.evaluation.run_expanded_static
bash scripts/python.sh -m src.evaluation.run_objectives_dynamic
bash scripts/python.sh -m src.evaluation.run_ppo_pilot
bash scripts/python.sh scripts/audit_extended_results.py
bash scripts/python.sh scripts/analyze_extended.py
bash scripts/python.sh scripts/build_expanded_report.py
```

기존 중단 캠페인의 재개는 `RESUME_RUN_ID=<id>`를 static/objectives 실행 앞에 지정한다. PPO 상태의 프로그래밍 방식 재개는 src/algorithms/ppo_checkpoint.py의 load_checkpoint를 사용한다. 단순 모델 파일만 로드하면 RNG/환경의 정확한 재개와 다르다.

| Campaign | run_id |
| --- | --- |
| Static | 20261117T055312Z-e99071d3 |
| Objectives/dynamics | 20261117T055818Z-d1b5e3ef |
| PPO | 20261117T060744Z-43676ed5 |

체크포인트: checkpoints/20261117T060744Z-43676ed5/

Figure: figures/publication/20261117T060744Z-43676ed5/ — 7종, 각각 PDF/SVG/600 dpi PNG. manifest.json에 원본 파일 해시를 기록했다. 학습 곡선은 smoothing 없이 실제 검증값을 사용한다.

Dashboard: http://localhost:3000/d/research-extended/manufacturing-rl-7c-expanded-research-and-ppo?var-run_id=20261117T060744Z-43676ed5

공식 구현 문서: https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html ; https://developers.google.com/optimization/cp/cp_solver
