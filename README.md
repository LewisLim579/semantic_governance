# Semantic Layer Repo (시맨틱 레이어 원천)

> AI Agent 개발/관리 표준 — **시맨틱 레이어 원천 저장소**
> 데이터플랫폼(Databricks) → 시맨틱 레이어(Git 관리) → AWS 솔루션 적재 → AI Agent

이 저장소는 시맨틱 레이어의 **원천(source of truth)** 을 관리합니다.
업무 의미·관계·규칙은 여기(Git)에서 관리하고, AWS 솔루션(Neptune / Vector Store / Agent 런타임)은
이 원천을 **빌드(적재)** 한 결과물입니다. **적재본은 직접 수정하지 않으며**, 원천을 수정한 뒤 다시 빌드하여 반영합니다.

---

## 0. 개념 (Concept)

### 무엇을 하는 프로젝트인가

데이터에 **"업무적 의미"** 를 부여하는 **시맨틱 레이어(Semantic Layer)** 를, 데이터·실행과 분리하여
**Git에서 코드처럼(버전관리·리뷰·검증)** 관리하기 위한 거버넌스 체계입니다.

- **데이터**가 무엇인지(정합성·권한)는 **Databricks**가 관리합니다.
- 그 데이터가 업무적으로 **무슨 의미·관계·규칙**을 갖는지는 **이 저장소(Git)** 가 관리합니다 ← *원천(SoT)*.
- **AI Agent**는 두 영역을 직접 고치지 않고, 적재된 지식(그래프·벡터·프롬프트)을 **도구 연계로 조회**해 답변/SQL을 생성합니다.

### 3개 영역 분리

| 영역 | 역할 | 기술 |
|------|------|------|
| ① 데이터플랫폼 | 데이터 적재 · 메타 · 권한 | Databricks (Delta Lake + Unity Catalog) |
| ② **시맨틱 레이어 (본 저장소)** | 업무 의미 · 관계 · 규칙 관리 | **Git Repo** (concept·relation·rule·mapping·prompt) + 관리 UI |
| ③ AI Agent | 실제 업무 활용 | AWS 기반 Agent 런타임 |

### 원천 → 적재 → 활용 흐름

```
[현업/IT]                         이 저장소 = 원천(Git)
   │ 관리 UI / PR
   ▼
[concept·relation·rule·mapping·prompt]  ──검증(.ci)──▶  merge(main)
   │ 빌드(적재 파이프라인)
   ├─▶ Amazon Neptune        (개념·관계·규칙 → 그래프 + 인스턴스)
   ├─▶ Vector Store          (비정형 문서 → 임베딩)
   └─▶ Agent 런타임          (프롬프트)
                                   │ 도구 연계로 조회
                                   ▼
                              [ AI Agent ] ──▶ 사용자
```

### 핵심 원칙

1. **데이터는 Databricks**, **의미는 시맨틱 레이어(Git)** 에서 관리한다.
2. 시맨틱 레이어의 **원천은 Git**이다. AWS 솔루션은 *적재 대상*이며 원천이 아니다 — 적재본은 직접 수정하지 않는다.
3. 원천은 다섯 가지: **concept · relation · rule · mapping · prompt**.
4. **도메인별로 계층화**하고, 공통은 `common/` 에 두며 중복되면 `common/` 으로 **승격**한다.
5. 현업은 **UI로 수정**하고, 모든 변경은 **Git → 검증 → 승인 → 적재** 순서로 진행한다.
6. `mapping` 이 시맨틱 레이어와 Databricks Gold 를 잇는 **기준**이다.

> 이 저장소에는 위 개념을 검증하기 위한 **예시 도메인**(거래·재무·마케팅 및 LPG 충전소 영업분석·멤버십)과,
> 실행 가능한 **검증기(`tools/validate.py`)**, 현업용 **관리 UI(`ui/`)** 가 함께 들어 있습니다.

---

## 1. 디렉터리 구조

```
semantic-layer-repo/
├── README.md
├── manifest.yaml                 # 도메인 레지스트리 + 원천 버전
├── CHANGELOG.md
├── CODEOWNERS                    # Domain Expert 승인 체계
├── requirements.txt              # PyYAML (검증기/UI 의존성)
├── common/                       # 공통 상위 계층 (도메인 공용 개념)
│   ├── concept.yaml
│   ├── relation.yaml
│   └── rule.yaml
├── domains/                      # 도메인별 계층
│   ├── trading/                  # 거래
│   │   ├── concept.yaml          # 개념(클래스)
│   │   ├── relation.yaml         # 관계
│   │   ├── rule.yaml             # 비즈니스 규칙
│   │   ├── mapping.yaml          # Databricks Gold ↔ 개념 매핑
│   │   └── prompt.yaml           # 도메인 프롬프트
│   ├── finance/                  # 재무
│   │   └── ... (동일 5종)
│   ├── marketing/                # 마케팅 (common:Customer·Product 재사용 예시)
│   │   └── ... (동일 5종)
│   ├── station_sales/            # 충전소 영업분석 (TMC 지표군 — Business Glossary 기반)
│   │   └── ... (동일 5종)
│   └── membership/               # 멤버십 (common:Customer·Station·SalesVolume 재사용)
│       └── ... (동일 5종)
├── tools/
│   └── validate.py               # 실행 가능한 검증기 (.ci/validate.yaml 구현)
├── ui/                           # 현업용 간단 관리 UI (§3.6)
│   ├── server.py                 # stdlib 백엔드 (조회·편집·저장·검증·커밋)
│   └── index.html                # 단일 페이지 편집기 (양식/원본 YAML)
├── .ci/
│   └── validate.yaml             # 적재 전 검증 규칙(선언)
├── ci/
│   └── validate.github-actions.yml  # CI 워크플로(아래 안내대로 .github/workflows/ 로 옮겨 활성화)
└── .github/
    └── PULL_REQUEST_TEMPLATE.md
```

> **GitHub Actions 자동 검증 활성화**: `ci/validate.github-actions.yml` 을 `.github/workflows/validate.yml`
> 로 옮긴 뒤 푸시하면 PR/머지 시 자동 검증이 실행됩니다. (푸시 토큰에 `workflow` 권한 필요 —
> 권한이 없으면 GitHub 웹의 *Add file* 로 직접 생성하세요.)

## 빠른 시작

```bash
pip install -r requirements.txt

# 1) 원천 검증 (CI 와 동일)
python tools/validate.py

# 2) 관리 UI 실행 (현업 편집) → 브라우저에서 http://127.0.0.1:8765
python ui/server.py
```

> UI 는 로컬 편집 도구입니다. 인증/권한(§3.6 '추후 정의')은 포함하지 않습니다.
> `localhost` 가 IPv6(`::1`)로 해석되는 환경에서는 반드시 `http://127.0.0.1:8765` 로 접속하세요.
> **양식 편집** 저장 시 YAML 이 재정렬되어 주석이 제거됩니다. 주석 보존이 필요하면 **원본 YAML** 탭을 사용하세요.

UI 는 현업 사용을 고려해 **한글을 병기**합니다 — 도메인/파일 유형/필드명을 `한글(영문)` 형태로 보여주고,
각 파일(개념·관계·규칙·데이터 연결·AI 지침)이 무엇인지 상단에 설명을 표시하며, `종류(kind)`·`심각도(severity)`
같은 항목은 드롭다운으로 선택합니다. 항목 카드는 영문 `id` 대신 **한글 표시명(label)** 을 크게 보여줍니다.

## 2. 원천 5대 구성요소

| 구성요소 | 역할 | 적재 대상 |
|---------|------|----------|
| `concept` | 개념(클래스)·속성 정의 | Neptune (그래프 스키마) |
| `relation` | 개념 간 관계 정의 | Neptune (엣지) |
| `rule` | 비즈니스 규칙·제약 | Neptune + Agent 추론 |
| `mapping` | 개념과 Databricks Gold 테이블 연결 | 적재 파이프라인 참조 |
| `prompt` | 도메인별 프롬프트 | Agent 런타임 |

## 3. 계층화 규칙

| 규칙 | 내용 |
|------|------|
| 단일 정의 | 공통 개념은 `common/` 에 한 번만 정의 |
| 상속 | 도메인 개념은 `parent: common:X` 형태로 공통 개념을 상속 |
| 승격 | 두 개 이상 도메인이 함께 쓰는 개념은 `common/` 으로 이동 |
| 격리 | 도메인 간 직접 참조 없이 `common/` 을 경유 |

## 4. 작성 규칙

| 항목 | 내용 |
|------|------|
| 형식 | 정의는 YAML, 설명은 Markdown |
| ID 규칙 | `concept` 은 PascalCase, `relation` 은 camelCase, `rule` 은 `R-###` |
| 네임스페이스 | 공통 개념은 `common:` 접두로 참조 |
| 표기 | `id` 는 영문, `label` 은 업무 용어(한글) |
| 출처 | 각 요소에 `source`(출처)를 기재하여 리니지 확보 |

### concept 확장 스키마 (Business Glossary 대응)

업무 용어집(단위·동의어·계산식·집계기준·원천시스템)을 표현하기 위해 `concept` 에 다음 선택 필드를 사용한다.

| 필드 | 설명 | 예 |
|------|------|----|
| `kind` | 개념 종류: `entity`(엔터티) / `measure`(지표) / `parameter`(기준값) | `measure` |
| `unit` | 단위 (measure 는 필수 권장) | `원/kg`, `원`, `kg`, `%`, `L` |
| `aliases` | 동의어·현업 표현 (표준용어 사전) | `[출고량, 실적]` |
| `formula` | 계산식 (다른 measure id 참조) | `ContributionMarginUnit − TMC` |
| `aggregation` | 집계 기준 | `월별/충전소별`, `건별`, `연별` |
| `note` | 주의사항·해석 기준 | `BIS 조회 조건에 따라 값 차이 가능` |

`mapping` 에는 원천 시스템·집계 단위를 위해 `system`(BIS/ERP/HMS/OCB), `grain` 필드를 추가로 사용할 수 있다.

## 5. 변경 및 검증 절차

```
[현업/개발] 수정(UI 또는 직접) → feature 브랜치 commit → Pull Request
   → 자동 검증(.ci/validate.yaml) → Domain Expert 승인
   → main 병합 → 적재 파이프라인 실행 → 적재 후 재검증
```

| 항목 | 내용 |
|------|------|
| 브랜치 | `main`(운영) / `develop` / `feature/*` |
| 버전 | Semantic Versioning (`v1.2.0`) |
| 승인 | Domain Expert 1인 이상 PR 승인 |
| 머지 조건 | 검증 통과 시에만 머지 |

**검증 항목**

| 검증 | 내용 |
|------|------|
| 스키마 유효성 | YAML 구조·필수 필드 검사 |
| 참조 무결성 | `relation` 의 from/to 가 `concept` 에 존재하는지 |
| 매핑 정합성 | `mapping` 의 catalog 경로·컬럼이 존재하는지 |
| 규칙 표현 | `rule` 의 constraint 가 해석 가능한지 |

## 6. 새 도메인 추가 방법

1. `domains/<new-domain>/` 디렉터리 생성
2. `concept.yaml` / `relation.yaml` / `rule.yaml` / `mapping.yaml` / `prompt.yaml` 작성
3. 공통 개념은 `parent: common:X` 로 상속, 도메인 고유 개념만 신규 정의
4. `.ci/validate.yaml` 기준으로 로컬 검증 후 PR
