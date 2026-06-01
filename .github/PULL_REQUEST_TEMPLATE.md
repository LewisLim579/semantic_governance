# 시맨틱 레이어 변경 요청

## 변경 도메인
<!-- 예: trading / finance / marketing / common -->

## 변경 유형
- [ ] concept (개념)
- [ ] relation (관계)
- [ ] rule (규칙)
- [ ] mapping (Databricks Gold 연결)
- [ ] prompt (프롬프트)

## 변경 내용 요약
<!-- 무엇을, 왜 바꾸는지 (업무 배경 포함) -->

## 출처(source)
<!-- 근거 문서/조항/Gold 테이블 경로 -->

## 체크리스트
- [ ] 각 요소에 `source`(출처) 기재
- [ ] 공통 개념은 `parent: common:X` 로 상속 (중복 정의 금지)
- [ ] `python tools/validate.py` 로컬 검증 통과
- [ ] Domain Expert 승인 대상 경로 확인 (CODEOWNERS)
