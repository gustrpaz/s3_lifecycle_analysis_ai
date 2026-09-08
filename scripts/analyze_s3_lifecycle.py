#!/usr/bin/env python3
"""
Análise determinística de políticas de lifecycle do Amazon S3.

O script avalia uma política AWS S3 Lifecycle seguindo os critérios do benchmark
referenciado no prompt interno do repositório. Ele produz um JSON compatível com
os campos obrigatórios: issueCodes, detectedIssues, correctionsSummary,
currentLifecyclePolicy e correctedLifecyclePolicy.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

TEMP_ORDER = {
    "STANDARD": 0,
    "REDUCED_REDUNDANCY": 0,
    "INTELLIGENT_TIERING": 1,
    "STANDARD_IA": 2,
    "ONEZONE_IA": 2,
    "GLACIER_IR": 3,
    "GLACIER": 4,
    "DEEP_ARCHIVE": 5,
}

IA_CLASSES = {"STANDARD_IA", "ONEZONE_IA"}
ARCHIVE_CLASSES = {"GLACIER_IR", "GLACIER", "DEEP_ARCHIVE"}
MINIMUM_DURATION = {
    "STANDARD_IA": 30,
    "ONEZONE_IA": 30,
    "GLACIER_IR": 90,
    "GLACIER": 90,
    "DEEP_ARCHIVE": 180,
}

IA_MINIMUM_DAYS = 30
GAP_MINIMUM_DAYS = 30
SIZE_FLOOR_BYTES = 131072


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Converte valores numéricos ou strings em inteiro, sem lançar exceção."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_rule_id(rule: Dict[str, Any], index: int) -> str:
    """Retorna o identificador da regra, com fallback determinístico."""
    return str(rule.get("ID") or rule.get("RuleId") or f"rule-{index + 1}")


def sort_unique(values: Iterable[str]) -> List[str]:
    """Remove duplicatas e ordena alfabeticamente."""
    return sorted(set(value for value in values if value))


def is_disabled(rule: Dict[str, Any]) -> bool:
    """Verifica se a regra está desabilitada."""
    return str(rule.get("Status", "Enabled")).lower() == "disabled"


def get_expiration_days(rule: Dict[str, Any]) -> Optional[int]:
    """Retorna os dias de expiração da regra atual."""
    expiration = rule.get("Expiration") or {}
    return safe_int(expiration.get("Days"), default=None)


def get_noncurrent_expiration_days(rule: Dict[str, Any]) -> Optional[int]:
    """Retorna os dias de expiração da versão não-atual."""
    expiration = rule.get("NoncurrentVersionExpiration") or {}
    return safe_int(expiration.get("NoncurrentDays"), default=None)


def get_transition_days(transition: Dict[str, Any]) -> Optional[int]:
    """Retorna os dias da transição, considerando Days ou Date quando aplicável."""
    days = safe_int(transition.get("Days"), default=None)
    if days is not None:
        return days
    return None


def collect_rule_transitions(rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Agrupa todas as transições da regra para análise uniforme."""
    transitions: List[Dict[str, Any]] = []
    for transition in rule.get("Transitions") or []:
        transitions.append({"kind": "current", **transition})
    for transition in rule.get("NoncurrentVersionTransitions") or []:
        transitions.append({"kind": "noncurrent", **transition})
    return transitions


def normalize_filter(filter_value: Any) -> Dict[str, Any]:
    """Converte um filtro em dicionário, preservando o formato AWS esperado."""
    if isinstance(filter_value, dict):
        return filter_value
    if filter_value is None:
        return {}
    return {"Prefix": filter_value}


def has_abort_rule(policy: Dict[str, Any]) -> bool:
    """Indica se a política já possui alguma regra com AbortIncompleteMultipartUpload."""
    for rule in policy.get("Rules") or []:
        if rule.get("AbortIncompleteMultipartUpload") is not None:
            return True
    return False


def add_issue(
    issue_map: Dict[str, List[Dict[str, Any]]],
    code: str,
    kind: str,
    rule_ids: List[str],
    message: str,
) -> None:
    """Acumula um achado no formato da resposta final."""
    issue_map.setdefault(code, []).append(
        {
            "kind": kind,
            "code": code,
            "ruleIds": sort_unique(rule_ids),
            "message": message,
        }
    )


def add_dedup_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, bad_transition: Dict[str, Any]) -> None:
    """Cria alerta/ajuste para transições duplicadas na mesma regra."""
    add_issue(
        issue_map,
        "DEDUP",
        "correcao",
        [rule_id],
        (
            f"Regra {rule_id} contém transições duplicadas para {bad_transition.get('StorageClass')}; "
            "mantém apenas a transição com menor prazo."
        ),
    )


def add_invalid_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, class_name: str) -> None:
    """Cria alerta/ajuste para storage class inválida."""
    add_issue(
        issue_map,
        "INVALID",
        "correcao",
        [rule_id],
        (
            f"Regra {rule_id} contém transição para classe não suportada ({class_name}); "
            "a transição foi removida."
        ),
    )


def add_c6_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str) -> None:
    """Cria alerta/ajuste para redundância Intelligent-Tiering + IA."""
    add_issue(
        issue_map,
        "C6_REDUNDANT",
        "correcao",
        [rule_id],
        (
            f"Regra {rule_id} combina Intelligent-Tiering com IA; a transição para IA foi removida "
            "porque fica coberta pelo serviço de tiering inteligente."
        ),
    )


def add_c1_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, storage_class: str, days: int) -> None:
    """Cria ajuste para IA mínima em version current."""
    add_issue(
        issue_map,
        "C1_IA_MIN",
        "correcao",
        [rule_id],
        (
            f"Regra {rule_id} transiciona para {storage_class} em {days} dias; o mínimo obrigatório "
            "para versão atual foi ajustado para 30 dias."
        ),
    )


def add_c2_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, message: str) -> None:
    """Cria ajuste para ordem de transições."""
    add_issue(
        issue_map,
        "C2_ORDER",
        "correcao",
        [rule_id],
        message,
    )


def add_c3_issues(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str) -> None:
    """Cria ajuste para piso de tamanho em transições pesadas."""
    add_issue(
        issue_map,
        "C3_SIZE",
        "correcao",
        [rule_id],
        (
            f"Regra {rule_id} contém apenas transições para classes frias sem filtro de tamanho; "
            f"foi incluído ObjectSizeGreaterThan={SIZE_FLOOR_BYTES}."
        ),
    )


def add_c5_issues(issue_map: Dict[str, List[Dict[str, Any]]], message: str) -> None:
    """Cria ajuste para regra de abort de MPU incompleto."""
    add_issue(
        issue_map,
        "C5_ABORT",
        "correcao",
        ["POLICY"],
        message,
    )


def add_disabled_issue(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str) -> None:
    """Cria aviso para regra desabilitada."""
    add_issue(
        issue_map,
        "DISABLED",
        "alerta",
        [rule_id],
        (
            f"Regra {rule_id} está desabilitada; nenhuma ação executa e o custo de acesso não é ativo."
        ),
    )


def add_mindur_issue(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, target: str, exp_days: int, trans_days: int) -> None:
    """Cria alerta para expiração antes da duração mínima cobrada."""
    add_issue(
        issue_map,
        "MINDUR",
        "alerta",
        [rule_id],
        (
            f"Regra {rule_id} expira em {exp_days} dias e transiciona para {target} em {trans_days} dias; "
            f"o intervalo não cumpre a permanência mínima de {MINIMUM_DURATION.get(target, 0)} dias."
        ),
    )


def add_expire_before_issue(issue_map: Dict[str, List[Dict[str, Any]]], rule_id: str, target: str, exp_days: int, trans_days: int) -> None:
    """Cria alerta para expiração no mesmo dia da transição ou antes dela."""
    add_issue(
        issue_map,
        "EXPIRE_BEFORE",
        "alerta",
        [rule_id],
        (
            f"Regra {rule_id} expira em {exp_days} dias, enquanto a transição para {target} ocorre em {trans_days} dias; "
            "a transição nunca será executada."
        ),
    )


def rule_contains_lifecycle_actions(rule: Dict[str, Any]) -> bool:
    """Verifica se a regra contém qualquer ação de lifecycle relevante."""
    return bool(
        rule.get("Transitions")
        or rule.get("NoncurrentVersionTransitions")
        or rule.get("Expiration")
        or rule.get("NoncurrentVersionExpiration")
        or rule.get("AbortIncompleteMultipartUpload")
    )


def analyze_policy(case_id: str, account_id: str, arn: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia uma política e devolve o JSON de saída requerido."""
    current_policy = copy.deepcopy(policy)
    corrected_policy = copy.deepcopy(policy)
    policy_rules = corrected_policy.get("Rules") or []

    issue_map: Dict[str, List[Dict[str, Any]]] = {}
    issue_codes: Set[str] = set()

    for index, rule in enumerate(policy_rules):
        rule_id = get_rule_id(rule, index)
        if not isinstance(rule, dict):
            continue
        if is_disabled(rule):
            add_disabled_issue(issue_map, rule_id)

        transitions = rule.get("Transitions") or []
        noncurrent_transitions = rule.get("NoncurrentVersionTransitions") or []

        # Invalid storage class and dedup within rule.
        seen_current_classes: Dict[str, Dict[str, Any]] = {}
        for transition in transitions:
            storage_class = transition.get("StorageClass")
            if storage_class not in TEMP_ORDER:
                add_invalid_issues(issue_map, rule_id, str(storage_class))
                continue
            if storage_class in seen_current_classes:
                existing = seen_current_classes[storage_class]
                existing_days = get_transition_days(existing)
                current_days = get_transition_days(transition)
                if current_days is None:
                    continue
                if existing_days is None or current_days < existing_days:
                    seen_current_classes[storage_class] = transition
                add_dedup_issues(issue_map, rule_id, transition)
            else:
                seen_current_classes[storage_class] = transition

        seen_noncurrent_classes: Dict[str, Dict[str, Any]] = {}
        for transition in noncurrent_transitions:
            storage_class = transition.get("StorageClass")
            if storage_class not in TEMP_ORDER:
                add_invalid_issues(issue_map, rule_id, str(storage_class))
                continue
            if storage_class in seen_noncurrent_classes:
                existing = seen_noncurrent_classes[storage_class]
                existing_days = get_transition_days(existing)
                current_days = get_transition_days(transition)
                if current_days is None:
                    continue
                if existing_days is None or current_days < existing_days:
                    seen_noncurrent_classes[storage_class] = transition
                add_dedup_issues(issue_map, rule_id, transition)
            else:
                seen_noncurrent_classes[storage_class] = transition

        current_class_names = {item.get("StorageClass") for item in transitions if item.get("StorageClass") is not None}
        if "INTELLIGENT_TIERING" in current_class_names and any(
            item.get("StorageClass") in IA_CLASSES for item in transitions
        ):
            add_c6_issues(issue_map, rule_id)

        noncurrent_class_names = {item.get("StorageClass") for item in noncurrent_transitions if item.get("StorageClass") is not None}
        if "INTELLIGENT_TIERING" in noncurrent_class_names and any(
            item.get("StorageClass") in IA_CLASSES for item in noncurrent_transitions
        ):
            add_c6_issues(issue_map, rule_id)

        # Correção de IA mínima para versão atual.
        for transition in transitions:
            storage_class = transition.get("StorageClass")
            days = get_transition_days(transition)
            if storage_class in IA_CLASSES and days is not None and days < IA_MINIMUM_DAYS:
                add_c1_issues(issue_map, rule_id, storage_class, int(days))

        # MINDUR e EXPIRE_BEFORE aplicados sob as mesmas regras, inclusive em regras disabled.
        expiration_days = get_expiration_days(rule)
        if expiration_days is not None:
            for transition in transitions:
                storage_class = transition.get("StorageClass")
                trans_days = get_transition_days(transition)
                if storage_class in MINIMUM_DURATION and trans_days is not None:
                    if expiration_days - trans_days < MINIMUM_DURATION[storage_class]:
                        add_mindur_issue(issue_map, rule_id, storage_class, expiration_days, trans_days)
                    if expiration_days <= trans_days:
                        add_expire_before_issue(issue_map, rule_id, storage_class, expiration_days, trans_days)

        noncurrent_expiration_days = get_noncurrent_expiration_days(rule)
        if noncurrent_expiration_days is not None:
            for transition in noncurrent_transitions:
                storage_class = transition.get("StorageClass")
                trans_days = get_transition_days(transition)
                if storage_class in MINIMUM_DURATION and trans_days is not None:
                    if noncurrent_expiration_days - trans_days < MINIMUM_DURATION[storage_class]:
                        add_mindur_issue(issue_map, rule_id, storage_class, noncurrent_expiration_days, trans_days)
                    if noncurrent_expiration_days <= trans_days:
                        add_expire_before_issue(issue_map, rule_id, storage_class, noncurrent_expiration_days, trans_days)

        # C3_SIZE: regra com somente transições e sem expiração/MPU.
        if isinstance(rule, dict):
            has_expiration = bool(rule.get("Expiration")) or bool(rule.get("NoncurrentVersionExpiration"))
            has_abort = rule.get("AbortIncompleteMultipartUpload") is not None
            if not has_expiration and not has_abort and (
                transitions or noncurrent_transitions
            ):
                all_transition_classes = {item.get("StorageClass") for item in transitions + noncurrent_transitions if item.get("StorageClass")}
                if all_transition_classes & (IA_CLASSES | ARCHIVE_CLASSES):
                    filter_value = rule.get("Filter")
                    filter_dict = normalize_filter(filter_value)
                    if "ObjectSizeGreaterThan" not in filter_dict:
                        if (
                            filter_dict.get("ObjectSizeLessThan") is None
                            or safe_int(filter_dict.get("ObjectSizeLessThan"), default=0) > SIZE_FLOOR_BYTES
                        ):
                            add_c3_issues(issue_map, rule_id)

    # C5_ABORT: política sem nenhuma regra de abort.
    if not has_abort_rule(corrected_policy):
        add_c5_issues(issue_map, "Nenhuma regra de AbortIncompleteMultipartUpload foi encontrada; foi adicionada uma regra dedicada com 7 dias.")

    # Transformações corretivas na política final.
    corrected_rules: List[Dict[str, Any]] = []
    for index, rule in enumerate(policy_rules):
        current_rule = copy.deepcopy(rule)
        rule_id = get_rule_id(current_rule, index)

        if not isinstance(current_rule, dict):
            corrected_rules.append(rule)
            continue

        # Remove storage classes inválidas.
        current_rule["Transitions"] = [
            transition for transition in (current_rule.get("Transitions") or [])
            if transition.get("StorageClass") in TEMP_ORDER
        ]
        current_rule["NoncurrentVersionTransitions"] = [
            transition for transition in (current_rule.get("NoncurrentVersionTransitions") or [])
            if transition.get("StorageClass") in TEMP_ORDER
        ]

        # Remove transições redundantes para a mesma classe, mantendo a menor duração.
        for key in ("Transitions", "NoncurrentVersionTransitions"):
            candidate_list = current_rule.get(key) or []
            best: Dict[str, Dict[str, Any]] = {}
            for transition in candidate_list:
                storage_class = transition.get("StorageClass")
                if not storage_class:
                    continue
                current_days = get_transition_days(transition)
                existing = best.get(storage_class)
                if existing is None or (current_days is not None and (get_transition_days(existing) is None or current_days < get_transition_days(existing))):
                    best[storage_class] = transition
            current_rule[key] = list(best.values())

        # Remove IA redundante quando houver Intelligent-Tiering na mesma regra.
        for key in ("Transitions", "NoncurrentVersionTransitions"):
            candidate_list = current_rule.get(key) or []
            if "INTELLIGENT_TIERING" in {item.get("StorageClass") for item in candidate_list} and any(
                item.get("StorageClass") in IA_CLASSES for item in candidate_list
            ):
                current_rule[key] = [
                    transition for transition in candidate_list
                    if not (
                        transition.get("StorageClass") in IA_CLASSES
                        and "INTELLIGENT_TIERING" in {item.get("StorageClass") for item in candidate_list}
                    )
                ]

        # Ajusta IA mínima para a versão atual.
        for transition in current_rule.get("Transitions") or []:
            storage_class = transition.get("StorageClass")
            days = get_transition_days(transition)
            if storage_class in IA_CLASSES and days is not None and days < IA_MINIMUM_DAYS:
                transition["Days"] = IA_MINIMUM_DAYS

        # Reordena transições por temperatura e respeita gap mínimo de 30 dias para IA -> arquivamento.
        for key in ("Transitions", "NoncurrentVersionTransitions"):
            transitions_list = current_rule.get(key) or []
            if not transitions_list:
                continue
            sorted_list = sorted(
                transitions_list,
                key=lambda item: (
                    TEMP_ORDER.get(item.get("StorageClass"), 999),
                    get_transition_days(item) if get_transition_days(item) is not None else 999999,
                ),
            )
            previous_days = -1
            previous_class = None
            for transition in sorted_list:
                storage_class = transition.get("StorageClass")
                days = get_transition_days(transition)
                if days is None:
                    continue
                if previous_class is not None and previous_days >= 0 and TEMP_ORDER.get(storage_class, 999) > TEMP_ORDER.get(previous_class, 999):
                    if previous_class in IA_CLASSES and storage_class in ARCHIVE_CLASSES and days < previous_days + GAP_MINIMUM_DAYS:
                        transition["Days"] = previous_days + GAP_MINIMUM_DAYS
                previous_class = storage_class
                previous_days = days
            current_rule[key] = sorted_list

        # Ajusta o filtro de tamanho para regras compostas só por transições para IA/arquivamento.
        if current_rule.get("Expiration") is None and current_rule.get("NoncurrentVersionExpiration") is None and current_rule.get("AbortIncompleteMultipartUpload") is None:
            transitions_list = (current_rule.get("Transitions") or []) + (current_rule.get("NoncurrentVersionTransitions") or [])
            if transitions_list:
                classes = {item.get("StorageClass") for item in transitions_list if item.get("StorageClass")}
                if classes & (IA_CLASSES | ARCHIVE_CLASSES):
                    filter_value = current_rule.get("Filter")
                    filter_dict = normalize_filter(filter_value)
                    if "ObjectSizeGreaterThan" not in filter_dict:
                        if (
                            filter_dict.get("ObjectSizeLessThan") is None
                            or safe_int(filter_dict.get("ObjectSizeLessThan"), default=0) > SIZE_FLOOR_BYTES
                        ):
                            filter_dict["ObjectSizeGreaterThan"] = SIZE_FLOOR_BYTES
                            current_rule["Filter"] = filter_dict

        corrected_rules.append(current_rule)

    corrected_policy["Rules"] = corrected_rules

    # Adiciona regra de abort quando a política inteira não possuir nenhuma.
    if not has_abort_rule(corrected_policy):
        existing_rules = corrected_policy.get("Rules") or []
        corrected_policy["Rules"] = [
            *existing_rules,
            {
                "ID": "AUTO_ABORT_7D",
                "Status": "Enabled",
                "Filter": {},
                "DaysAfterInitiation": 7,
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            },
        ]

    # Monta a lista final de códigos e ocorrências.
    all_issues: List[Dict[str, Any]] = []
    for code in sorted(issue_map.keys()):
        issue_codes.add(code)
        all_issues.extend(issue_map[code])

    if not issue_codes:
        corrections_summary = "Nenhuma correção é necessária. A política atual está conforme as regras de lifecycle da AWS e os critérios de eficiência financeira e governança de dados."
    else:
        corrections_summary = (
            "Correções aplicadas: removidas transições inválidas ou redundantes, ajustados limites mínimos para "
            "classes de armazenamento mais frias, preservadas as expirações existentes e adicionada a regra de MPU incompleto "
            "quando necessário. Alertas emitidos para regras desabilitadas, expiração antes da transição e permanência mínima insuficiente."
        )

    result = {
        "caseId": case_id,
        "accountId": account_id,
        "arn": arn,
        "issueCodes": sorted(issue_codes),
        "detectedIssues": all_issues,
        "additionalIssueCodes": [],
        "additionalIssues": [],
        "correctionsSummary": corrections_summary,
        "currentLifecyclePolicy": current_policy,
        "correctedLifecyclePolicy": corrected_policy,
    }
    return result


def load_policy_from_text(raw_text: str) -> Dict[str, Any]:
    """Carrega uma política no formato JSON canônico da AWS."""
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("A política deve ser um objeto JSON.")
    if "Rules" not in parsed:
        parsed["Rules"] = []
    return parsed


def parse_args() -> argparse.Namespace:
    """Coleta os argumentos do CLI."""
    parser = argparse.ArgumentParser(description="Analisa regras de lifecycle S3.")
    parser.add_argument("--case-id", default="R01")
    parser.add_argument("--account-id", default="BENCH-R01")
    parser.add_argument("--arn", default="arn:aws:s3:::R01")
    parser.add_argument("--policy-file", help="Caminho para um arquivo JSON contendo a política S3 Lifecycle.")
    parser.add_argument("--policy-json", help="JSON da política S3 Lifecycle em uma string.")
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada do script."""
    args = parse_args()

    try:
        if args.policy_json:
            policy = load_policy_from_text(args.policy_json)
        elif args.policy_file:
            with open(args.policy_file, "r", encoding="utf-8") as handle:
                policy = load_policy_from_text(handle.read())
        else:
            stdin_text = sys.stdin.read().strip()
            if not stdin_text:
                raise ValueError("Nenhuma política informada. Use --policy-file, --policy-json ou stdin.")
            policy = load_policy_from_text(stdin_text)

        result = analyze_policy(args.case_id, args.account_id, args.arn, policy)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - recuperação operacional
        print(json.dumps({
            "error": str(exc),
            "caseId": args.case_id,
            "accountId": args.account_id,
            "arn": args.arn,
            "issueCodes": [],
            "detectedIssues": [],
            "additionalIssueCodes": [],
            "additionalIssues": [],
            "correctionsSummary": "Falha ao processar a política de lifecycle informada.",
            "currentLifecyclePolicy": {"Rules": []},
            "correctedLifecyclePolicy": {"Rules": []},
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
