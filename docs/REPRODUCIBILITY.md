# 실행·재현 안내

## 공개 저장소에 포함된 것

코드, 고정 설정, 입력 데이터와 출처, 원시 결과 JSON·CSV, 검증 기록, 그림, Grafana provisioning을 포함한다. 로컬 세션을 포함하는 SQL 백업, 실행 로그, 임시 환경, 모델 가중치와 개인 경로를 담은 설치 메모는 제외한다. 이 저장소는 로컬 연구 작업의 배포용 스냅샷이며 전체 로컬 Git 이력을 게시하지 않는다. 과거 메타데이터의 `git_commit`은 로컬 연구 커밋이므로 이 저장소에서 조회되지 않을 수 있다. 파일별 소스 해시는 메타데이터에 보존되어 있다.

## 환경 준비

검증 환경은 macOS arm64, Apple M5, 16 GiB, Python 3.11.15다. `uv` 및 Docker Compose가 필요하다. Python 의존성은 `requirements.training.lock.txt`로 고정한다. 다른 플랫폼에서의 설치·성능은 별도 검증이 필요하다.

```bash
bash scripts/setup_training.sh
bash scripts/python.sh -m pytest -q --basetemp=runtime/pytest
```

`MANUFACTURING_PYTHON_VERSION`으로 setup에 사용할 Python 버전/경로를 지정할 수 있다. FAT32에서는 의존성 환경만 `/tmp`에 생성한다. 임시 환경이 사라졌으면 setup을 다시 실행한다. 코드·데이터·결과는 저장소 안에 유지한다.

이미 설치된 Python을 사용할 때는 `MANUFACTURING_PYTHON`을 `scripts/python.sh`에 전달할 수 있다.

## 저장 결과 감사와 분석 — DB 불필요

```bash
bash scripts/python.sh scripts/audit_extended_results.py
bash scripts/python.sh scripts/analyze_multi_rl.py
bash scripts/python.sh scripts/verify_multi_rl_figures.py
```

첫 명령은 이전 확장 실험을 검사한다. 두 번째 명령은 추가 RL 비교의 독립 감사, 통계표, 그림과 결과 보고서를 재생성한다. 학습 가중치는 필요하지 않다. 분석기는 `reports/latest_*_run.txt`에 지정된 완료 실행을 읽는다.

## 조회용 DB와 Grafana

```bash
bash scripts/start_monitoring.sh
```

- Grafana: http://localhost:3000 — `admin / admin_local_only`
- PostgreSQL: localhost:5432 — 로컬 데모 구성
- Prometheus: http://localhost:9090

PostgreSQL은 tmpfs를 사용한다. 컨테이너를 다시 생성하면 DB가 사라질 수 있으므로 `start_monitoring.sh`를 통해 원시 기록을 복원한다. 깨끗한 clone에서는 Grafana가 자신의 DB를 초기화하고 JSON으로 패널을 provision한다. 기존 로그인 세션 백업은 필요하지 않다. 서비스 종료는 `docker compose stop`이다.

추가 RL 비교 대시보드는 결과·학습 곡선을 중심으로 구성하며 CPU·RAM·학습 진행률·완료 횟수·상태 표는 제거했다. 다른 이전 대시보드는 과거 실험 조회를 위해 보존한다.

파일을 수정했는데 Docker/FAT32 마운트가 이전 내용을 보여주면:

```bash
docker compose up -d --force-recreate grafana
bash scripts/python.sh scripts/verify_multi_rl_dashboard.py
```

## 새 실험

DB가 실행 중인 상태에서 선택한 캠페인을 실행한다.

```bash
bash scripts/python.sh -m src.evaluation.run_expanded_static
bash scripts/python.sh -m src.evaluation.run_objectives_dynamic
bash scripts/python.sh -m src.evaluation.run_ppo_pilot
bash scripts/python.sh -m src.evaluation.run_multi_rl
```

위 명령은 각각 별도 실행이다. 전체를 실행하면 모든 캠페인을 다시 수행한다. 계산 시간 비교를 위해 동일 호스트에서 캠페인을 동시에 실행하지 않는 편이 좋다. 기존 보고서의 동시 실행 여부는 해당 보고서에 명시되어 있다.

각 실행은 새 `run_id`로 기록한다. `RESUME_RUN_ID=<id>`는 완료된 평가 및 완료된 학습 시드를 재사용한다. 추가 비교의 중단된 사용자 정의 학습 시드는 처음부터 다시 학습한다. 임의 시점의 정확한 학습 재개를 보장하는 인터페이스로 해석하지 않는다.

## 체크포인트와 과거 기록

가중치는 `checkpoints/<run_id>/`에 저장되며 Git에서는 제외한다. 저장소에는 모델 해시·학습 기록·평가 결과가 포함되어 있다. 과거 모델의 20/20 재로딩 검증 기록과, 공개 clone에서 모델 파일이 제공되는지는 별개의 사실이다.

실험 프로토콜, 원시 기록, SHA-256과 저장된 메타데이터를 우선한다. README의 반올림된 값이나 대시보드 표시값만으로 재분석하지 않는다. 학습 곡선은 실제 기록 지점을 사용하고 smoothing하지 않는다.

## 주요 실행 ID

| 캠페인 | run_id |
| --- | --- |
| 정적 확장 | `20261117T055312Z-e99071d3` |
| 목적함수·동적 | `20261117T055818Z-d1b5e3ef` |
| PPO 파일럿 | `20261117T060744Z-43676ed5` |
| 추가 RL 비교 | `20261117T101814Z-eab66180` |

[프로젝트 README로 돌아가기](../README.md)
