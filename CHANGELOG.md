# Changelog

이 저장소(시맨틱 레이어 원천)의 변경 이력을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/)을 따릅니다.

## [Unreleased]
### Added
- 관리 UI 한글 병기: 도메인·파일 유형·필드명을 한글(영문) 형태로 표시, 파일 유형 설명 배너, `kind`·`severity` 드롭다운
- 도메인 `station_sales`(충전소 영업분석/TMC), `membership`(멤버십) — 데이터 항목 정의서 기반
- 공통 개념 승격: `Station`(충전소), `Dealer`(거래처), `SalesVolume`(C4 판매량), `InternalInterestRate`(사내이자율)
- concept 확장 스키마: `kind`(entity/measure/parameter), `unit`, `aliases`, `formula`, `aggregation`
- 검증기: measure 의 `unit` 누락 경고, `kind` 값 권장 검사

## [0.1.0] - 2026-05-29
### Added
- 저장소 초기 구조 (`common/`, `domains/`, `.ci/`)
- 공통 계층 개념: `Transaction`, `Party`, `Customer`, `Product`
- 도메인: `trading`(거래), `finance`(재무), `marketing`(마케팅)
- 실행 가능한 검증기 `tools/validate.py` 및 CI 워크플로
- 현업용 간단 관리 UI (`ui/`)
- 도메인 레지스트리 `manifest.yaml`
