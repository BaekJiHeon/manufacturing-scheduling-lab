# 추가 강화학습 비교 결과

실행 `20261117T101814Z-eab66180`. PPO·PQN·GRPO-Sched·GSPO-Sched를 각각 5개 시드, 65,536 환경 전이로 학습했다. 총 20개 실행 / 1,310,720 전이이며 모든 마지막 체크포인트를 평가했다. 36개 평가 조건 × 20개 모델 = 720개 RL 스케줄, 별도로 CP-SAT 1/5초와 휴리스틱 3종 180개를 평가했다.

**GRPO·GSPO가 PPO보다 확실히 우수하다는 근거는 부족하다. 이번 설정에서 CP-SAT을 대체할 근거는 없다.** 새 생성 문제의 CP-SAT 대비 문제별 상대차 평균은 GSPO-Sched가 51.75%로 가장 작았지만, 원시 비용 평균은 PPO0.6334 / GSPO0.6340였다. 문제별 비율을 평균하는 것과 원시 비용을 평균하는 것은 가중치가 달라 순위가 다를 수 있다. PPO와 직접 짝지은 GRPO/GSPO 상대차의 모든 시나리오95% 구간은0을 포함했다. 이것은 고정 예산 파일럿이며 수렴·일반적 우월성·최신 알고리즘 전체에 대한 결론이 아니다.

## 품질 비교

비용은 `(makespan + mean tardiness)/100`이며 낮을수록 좋다. 각 문제의 CP5 대비 상대차를 시드별로 평균한 뒤, 학습 시드5개에 대한 평균과 t95% 구간을 계산했다. 구간은 독립 공장 표본의 불확실성이 아니다.

| method | scenario | objective_score | gap_cp_percent | gap_cp_percent_ci95_low | gap_cp_percent_ci95_high | wins_cp | ties_cp | losses_cp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GRPO-Sched | external_dynamic | 1.210 | 96.384 | 90.660 | 102.108 | 0 | 0 | 6 |
| GRPO-Sched | external_static | 3.192 | 58.106 | 53.106 | 63.107 | 0 | 0 | 10 |
| GRPO-Sched | fresh_generated_test | 0.642 | 53.457 | 48.095 | 58.820 | 0 | 0 | 20 |
| GSPO-Sched | external_dynamic | 1.243 | 103.862 | 81.156 | 126.568 | 0 | 0 | 6 |
| GSPO-Sched | external_static | 3.163 | 60.257 | 52.353 | 68.162 | 0 | 0 | 10 |
| GSPO-Sched | fresh_generated_test | 0.634 | 51.749 | 45.486 | 58.013 | 0 | 0 | 20 |
| MaskablePPO | external_dynamic | 1.291 | 109.687 | 93.573 | 125.800 | 0 | 0 | 6 |
| MaskablePPO | external_static | 3.261 | 69.366 | 49.966 | 88.767 | 0 | 0 | 10 |
| MaskablePPO | fresh_generated_test | 0.633 | 52.634 | 49.631 | 55.637 | 0 | 0 | 20 |
| MaskedPQN | external_dynamic | 1.703 | 189.268 | 82.729 | 295.807 | 0 | 0 | 6 |
| MaskedPQN | external_static | 3.919 | 112.955 | 74.627 | 151.282 | 0 | 0 | 10 |
| MaskedPQN | fresh_generated_test | 0.784 | 88.419 | 78.634 | 98.204 | 0 | 0 | 20 |

wins/ties/losses는 문제별 RL 시드 평균과 CP5의 비교다. 외부 정적10개/동적6개는 이전에 확인한 전이 평가이고, 새 생성20개만 이번에 고정한 새로운 평가다.

## 휴리스틱 기준도 함께 확인

단순 SPT(가장 짧은 처리시간 우선)의 시나리오별 평균 비용도 이번 네 RL 구성보다 낮았다. 따라서 CP-SAT 대비 차이만으로 결과를 설명하면 안 된다. 모델 교체만으로 성능 개선이 확보되지 않았으며, 추가 연구에서는 상태 표현·학습 분포·예산의 영향을 따로 검증해야 한다. 아래는 튜닝 없이 고정한 휴리스틱 결과다.

| method | scenario | objective_mean | episode_ms_mean |
| --- | --- | --- | --- |
| EDD | external_dynamic | 1.021 | 21.124 |
| EDD | external_static | 2.957 | 29.831 |
| EDD | fresh_generated_test | 0.555 | 1.458 |
| MWKR | external_dynamic | 0.961 | 21.324 |
| MWKR | external_static | 2.705 | 30.063 |
| MWKR | fresh_generated_test | 0.548 | 1.492 |
| SPT | external_dynamic | 0.857 | 21.593 |
| SPT | external_static | 2.891 | 29.896 |
| SPT | fresh_generated_test | 0.515 | 1.440 |

## 같은 예산의 PPO 대비

음수면 해당 방법이 이번 PPO보다 평균 비용이 낮다. 같은 학습 시드와 같은 평가 문제끼리 짝지었다.

| method | scenario | gap_ppo_percent | gap_ppo_percent_ci95_low | gap_ppo_percent_ci95_high |
| --- | --- | --- | --- | --- |
| GRPO-Sched | external_dynamic | -5.153 | -14.606 | 4.299 |
| GRPO-Sched | external_static | -4.101 | -10.883 | 2.682 |
| GRPO-Sched | fresh_generated_test | 1.781 | -1.551 | 5.113 |
| GSPO-Sched | external_dynamic | -0.852 | -16.131 | 14.426 |
| GSPO-Sched | external_static | -3.419 | -13.892 | 7.054 |
| GSPO-Sched | fresh_generated_test | 0.615 | -2.946 | 4.176 |
| MaskablePPO | external_dynamic | 0.000 | 0.000 | 0.000 |
| MaskablePPO | external_static | 0.000 | 0.000 | 0.000 |
| MaskablePPO | fresh_generated_test | 0.000 | 0.000 | 0.000 |
| MaskedPQN | external_dynamic | 41.207 | -8.620 | 91.034 |
| MaskedPQN | external_static | 26.043 | 3.508 | 48.578 |
| MaskedPQN | fresh_generated_test | 25.662 | 20.212 | 31.111 |

## 속도와 계산 비용

| method | scenario | runtime_ms | mean_inference_ms |
| --- | --- | --- | --- |
| GRPO-Sched | external_dynamic | 26.164 | 0.048 |
| GRPO-Sched | external_static | 36.433 | 0.050 |
| GRPO-Sched | fresh_generated_test | 3.014 | 0.054 |
| GSPO-Sched | external_dynamic | 26.044 | 0.048 |
| GSPO-Sched | external_static | 35.625 | 0.048 |
| GSPO-Sched | fresh_generated_test | 2.916 | 0.052 |
| MaskablePPO | external_dynamic | 38.187 | 0.151 |
| MaskablePPO | external_static | 50.871 | 0.143 |
| MaskablePPO | fresh_generated_test | 6.007 | 0.150 |
| MaskedPQN | external_dynamic | 32.716 | 0.052 |
| MaskedPQN | external_static | 46.595 | 0.056 |
| MaskedPQN | fresh_generated_test | 3.903 | 0.056 |

runtime_ms는 전체 에피소드 계산, mean_inference_ms는 행동 한 번의 평균이다. PPO/PQN/GRPO/GSPO의 행동 한 번과 CP-SAT의 전체 재계획은 서로 다른 작업 단위다. 사용자 정의 정책과 SB3 정책의 추론 경로·망 크기도 달라, 속도 차이를 알고리즘 자체의 우월성으로 단정하지 않는다. CP·휴리스틱도 같은 호스트에서 다시 실행했다.

| method | trials | training_seconds_mean | training_seconds_std | parameters | unused_transitions_mean | unused_transitions_max |
| --- | --- | --- | --- | --- | --- | --- |
| GRPO-Sched | 5 | 18.317 | 0.100 | 1326397.000 | 517.200 | 686.000 |
| GSPO-Sched | 5 | 18.571 | 0.706 | 1326397.000 | 490.200 | 704.000 |
| MaskablePPO | 5 | 32.528 | 0.979 | 2149694.000 | 0.000 | 0.000 |
| MaskedPQN | 5 | 15.557 | 0.620 | 1326909.000 | 0.000 | 0.000 |

학습 시간은 주기적 검증·기록·체크포인트 저장을 포함한다. 그룹 방법에서 마지막 예산 경계에 걸린 미완성 그룹의 전이도 총65,536에 포함했고, 학습에 사용하지 않은 수를 공개했다. 네 방법이 같은128개 학습 문제를 사용하지만 그룹 재표본으로 방문 횟수는 다르다. 이전 PPO 파일럿은 학습 데이터 생성 방식도 달라 직접 통제군으로 쓰지 않았다.

## 최근 알고리즘을 어디까지 구현했는가?

- PQN: [2024 논문 / ICLR2025](https://arxiv.org/abs/2407.04811)의 온라인 Q(lambda), LayerNorm, 병렬 환경, replay/target network 없는 구성을 스케줄링에 맞춰 구현했다. 행동 선택과 bootstrap 모두 합법 행동만 허용한다.
- GRPO-Sched: [DeepSeekMath(2024)](https://arxiv.org/abs/2402.03300)의 동일 문제 그룹 보상 정규화와 행동별 clipped ratio를 스케줄 궤적에 적용했다.
- GSPO-Sched: [GSPO(2025)](https://arxiv.org/abs/2507.18071)의 길이 정규화된 전체 궤적 likelihood ratio와 궤적 단위 clipping을 적용했다.

GRPO/GSPO는 원래 언어모델용 방법의 **스케줄링 적용 실험**이다. 공식 제조 구현이나 LLM 결과 재현으로 표현하면 안 된다. 사전학습 참조 모델이 없어 KL beta=0, entropy .01을 사용했다. PQN은 LayerNorm/ReLU, 정책 방식은 Tanh128×128이고 PPO만 value망이 추가되어, 순수 optimizer만 바꾼 실험도 아니다. 모든 차이와 고정 설정은 multi_rl_protocol.md 및 configs/algorithms/multi_rl.json에 기록했다. 테스트 결과를 본 뒤 튜닝하거나 좋은 시드만 선택하지 않았다.

## 검증과 보관

독립 스케줄 검사: 900개 완료 스케줄 및 128개 중간 계획, 제약 위반 0건. 솔버 응답 감사 경고 1건은 원본과 감사 파일에 보존했다. 20개 체크포인트 모두 재로딩 후 검증 스케줄이 동일했다. 원시 JSON·CSV·DB 모든 셀 대조는 db_validation.json에 있다.

- 원시 결과 및 표: results/multi_rl/20261117T101814Z-eab66180/
- 모델: checkpoints/20261117T101814Z-eab66180/ (Git에는 해시만 기록)
- 그림4종: figures/publication/20261117T101814Z-eab66180/ — PDF/SVG/600dpi PNG, 학습곡선은 원시 측정점
- 대시보드: http://localhost:3000/d/research-multi-rl/manufacturing-rl-7c-ppo-pqn-grpo-gspo-comparison?var-run_id=20261117T101814Z-eab66180
