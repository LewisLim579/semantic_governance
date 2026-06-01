#!/usr/bin/env python3
"""시맨틱 레이어 원천 검증기 (.ci/validate.yaml 규칙의 실제 구현).

검증 항목 (§3.7):
  1) schema_validity        - 필수 필드 존재
  2) id_naming              - concept=PascalCase, relation=camelCase, rule=R-###
  3) reference_integrity    - relation.from/to 가 정의된 concept 인지
  4) inheritance_integrity  - concept.parent 가 존재하는 개념인지
  5) rule_expression        - rule.severity 가 error|warning 인지
  6) domain_isolation       - 도메인이 다른 도메인을 직접 참조하지 않는지(common 만 허용)
  (mapping_consistency 는 Databricks 접속이 필요하여 여기서는 형식 검사만 수행)

사용:  python tools/validate.py        (저장소 루트 기준 자동 탐색)
종료코드: error 1건 이상이면 1, 아니면 0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("[FATAL] PyYAML 이 필요합니다.  pip install -r requirements.txt")
    sys.exit(2)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent

PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")
RULE_ID = re.compile(r"^R-[0-9]{3}$")
VALID_SEVERITY = {"error", "warning"}


class Issue:
    def __init__(self, severity: str, where: str, message: str):
        self.severity = severity
        self.where = where
        self.message = message

    def __str__(self) -> str:
        icon = "ERROR" if self.severity == "error" else "WARN "
        return f"[{icon}] {self.where}: {self.message}"


issues: list[Issue] = []


def err(where: str, msg: str) -> None:
    issues.append(Issue("error", where, msg))


def warn(where: str, msg: str) -> None:
    issues.append(Issue("warning", where, msg))


def load_yaml(path: Path):
    rel = path.relative_to(REPO_ROOT)
    try:
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        err(str(rel), f"YAML 파싱 실패: {e}")
        return None


def concept_ids(doc: dict) -> set[str]:
    return {c["id"] for c in (doc or {}).get("concepts", []) if isinstance(c, dict) and "id" in c}


def strip_common(ref: str) -> str:
    return ref.split(":", 1)[1] if isinstance(ref, str) and ref.startswith("common:") else ref


def main() -> int:
    common_dir = REPO_ROOT / "common"
    domains_dir = REPO_ROOT / "domains"

    # --- 공통 개념 로드 ---
    common_concept_doc = load_yaml(common_dir / "concept.yaml") if (common_dir / "concept.yaml").exists() else {}
    common_concepts = concept_ids(common_concept_doc or {})

    # --- 도메인별 개념 수집 (도메인 격리 검사에 사용) ---
    domain_concepts: dict[str, set[str]] = {}
    if domains_dir.exists():
        for d in sorted(p for p in domains_dir.iterdir() if p.is_dir()):
            cdoc = load_yaml(d / "concept.yaml") if (d / "concept.yaml").exists() else {}
            domain_concepts[d.name] = concept_ids(cdoc or {})

    # ============ 공통 계층 검사 ============
    _check_concept_file(common_dir / "concept.yaml", common_concepts, common_concepts)
    _check_relation_file(common_dir / "relation.yaml", common_concepts, common_concepts, domain_concepts, owner=None)
    _check_rule_file(common_dir / "rule.yaml", common_concepts, common_concepts)

    # ============ 도메인 계층 검사 ============
    for domain, local in domain_concepts.items():
        d = domains_dir / domain
        known = local | common_concepts  # 도메인 내에서 참조 가능한 개념
        _check_concept_file(d / "concept.yaml", local, common_concepts)
        _check_relation_file(d / "relation.yaml", known, common_concepts, domain_concepts, owner=domain)
        _check_rule_file(d / "rule.yaml", known, common_concepts)
        _check_mapping_file(d / "mapping.yaml", local)
        _check_prompt_file(d / "prompt.yaml")

    # ============ 리포트 ============
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    for i in issues:
        print(i)
    print("-" * 60)
    print(f"검증 완료: error {len(errors)}건, warning {len(warnings)}건")
    return 1 if errors else 0


def _check_concept_file(path: Path, local_ids: set[str], common_ids: set[str]) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(REPO_ROOT))
    doc = load_yaml(path)
    if doc is None:
        return
    if "domain" not in doc or "concepts" not in doc:
        err(rel, "필수 필드 누락 (domain, concepts)")
        return
    for c in doc.get("concepts", []):
        cid = c.get("id", "<no-id>")
        if "id" not in c or "label" not in c:
            err(rel, f"concept '{cid}' 필수 필드 누락 (id, label)")
        if "id" in c and not PASCAL_CASE.match(c["id"]):
            err(rel, f"concept id '{c['id']}' 는 PascalCase 여야 함")
        # 확장 스키마: kind=measure 는 unit(단위)이 있어야 함
        if c.get("kind") == "measure" and not c.get("unit"):
            warn(rel, f"measure '{cid}' 에 unit(단위) 누락")
        kind = c.get("kind")
        if kind and kind not in ("entity", "measure", "parameter"):
            warn(rel, f"concept '{cid}' 의 kind '{kind}' 는 entity|measure|parameter 권장")
        parent = c.get("parent")
        if parent:
            target = strip_common(parent)
            if target not in (local_ids | common_ids):
                err(rel, f"concept '{cid}' 의 parent '{parent}' 가 존재하지 않음")


def _check_relation_file(path: Path, known_ids: set[str], common_ids: set[str],
                         domain_concepts: dict, owner: str | None) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(REPO_ROOT))
    doc = load_yaml(path)
    if doc is None:
        return
    if "domain" not in doc or "relations" not in doc:
        err(rel, "필수 필드 누락 (domain, relations)")
        return
    for r in doc.get("relations", []):
        rid = r.get("id", "<no-id>")
        if "id" not in r or "from" not in r or "to" not in r:
            err(rel, f"relation '{rid}' 필수 필드 누락 (id, from, to)")
            continue
        if not CAMEL_CASE.match(rid):
            err(rel, f"relation id '{rid}' 는 camelCase 여야 함")
        for endpoint in ("from", "to"):
            ref = strip_common(r[endpoint])
            if ref in known_ids:
                continue
            err(rel, f"relation '{rid}' 의 {endpoint} '{r[endpoint]}' 가 정의된 concept 가 아님")
            # 도메인 격리: 다른 도메인 개념을 직접 참조했는지 추가 안내
            if owner is not None:
                for other, ids in domain_concepts.items():
                    if other != owner and ref in ids:
                        warn(rel, f"relation '{rid}' 가 다른 도메인('{other}') 개념을 직접 참조 — common 경유 필요")


def _check_rule_file(path: Path, known_ids: set[str], common_ids: set[str]) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(REPO_ROOT))
    doc = load_yaml(path)
    if doc is None:
        return
    if "domain" not in doc or "rules" not in doc:
        err(rel, "필수 필드 누락 (domain, rules)")
        return
    for r in doc.get("rules", []):
        rid = r.get("id", "<no-id>")
        if not RULE_ID.match(str(rid)):
            err(rel, f"rule id '{rid}' 는 R-### 형식이어야 함")
        if "constraint" not in r:
            err(rel, f"rule '{rid}' 에 constraint 누락")
        sev = r.get("severity")
        if sev not in VALID_SEVERITY:
            err(rel, f"rule '{rid}' 의 severity '{sev}' 는 error|warning 이어야 함")
        applies = strip_common(r.get("applies_to", ""))
        if applies and applies not in known_ids:
            warn(rel, f"rule '{rid}' 의 applies_to '{r.get('applies_to')}' 가 정의된 concept 가 아님")
        if not r.get("source"):
            warn(rel, f"rule '{rid}' 에 source(출처) 누락")


def _check_mapping_file(path: Path, local_ids: set[str]) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(REPO_ROOT))
    doc = load_yaml(path)
    if doc is None:
        return
    if "domain" not in doc or "mappings" not in doc:
        err(rel, "필수 필드 누락 (domain, mappings)")
        return
    for m in doc.get("mappings", []):
        concept = m.get("concept", "<no-concept>")
        if concept not in local_ids:
            err(rel, f"mapping 대상 concept '{concept}' 가 이 도메인에 정의되어 있지 않음")
        for field in ("catalog", "key", "property_map"):
            if field not in m:
                err(rel, f"mapping '{concept}' 필수 필드 누락 ({field})")
        catalog = m.get("catalog", "")
        if catalog and len(catalog.split(".")) != 3:
            warn(rel, f"mapping '{concept}' 의 catalog '{catalog}' 가 3단계(catalog.schema.table) 형식이 아님")


def _check_prompt_file(path: Path) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(REPO_ROOT))
    doc = load_yaml(path)
    if doc is None:
        return
    if "domain" not in doc or "prompts" not in doc:
        err(rel, "필수 필드 누락 (domain, prompts)")
        return
    for p in doc.get("prompts", []):
        pid = p.get("id", "<no-id>")
        for field in ("id", "role"):
            if field not in p:
                err(rel, f"prompt '{pid}' 필수 필드 누락 ({field})")


if __name__ == "__main__":
    sys.exit(main())
