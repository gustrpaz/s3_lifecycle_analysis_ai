import json
import sys
from typing import Any

STORAGE_CLASS_MIN_DAYS = {
    "STANDARD": 0,
    "INTELLIGENT_TIERING": 6,
    "STANDARD_IA": 30,
    "ONEZONE_IA": 30,
    "GLACIER_IR": 90,
    "GLACIER": 90,
    "DEEP_ARCHIVE": 180,
}


def get_enabled_rules(config: dict) -> list:
    return [r for r in config.get("Rules", []) if r.get("Status") == "Enabled"]


def has_filter(rule: dict) -> bool:
    f = rule.get("Filter", {})
    if f is None:
        return False
    if not f:
        return False
    if "Prefix" in f and f["Prefix"] != "":
        return True
    if "Tag" in f or "Tags" in f:
        return True
    if "And" in f:
        and_block = f["And"]
        if and_block.get("Prefix", "") != "":
            return True
        if and_block.get("Tags"):
            return True
    if "ObjectSizeGreaterThan" in f or "ObjectSizeLessThan" in f:
        return True
    if "And" in f:
        and_block = f["And"]
        if "ObjectSizeGreaterThan" in and_block or "ObjectSizeLessThan" in and_block:
            return True
    return False


def is_global_scope(rule: dict) -> bool:
    return not has_filter(rule)

def get_filter_prefix(rule: dict) -> str:
    f = rule.get("Filter", {})
    if not f:
        return ""
    if "Prefix" in f:
        return f["Prefix"]
    if "And" in f:
        return f["And"].get("Prefix", "")
    return ""


def get_filter_tags(rule: dict) -> list:
    f = rule.get("Filter", {})
    if not f:
        return []

    if "Tag" in f:
        return [f["Tag"]]

    if "Tags" in f:
        return f["Tags"]

    if "And" in f:
        return f["And"].get("Tags", [])
    return []


def get_size_filter(rule: dict) -> tuple:
    f = rule.get("Filter", {})
    min_size = None
    max_size = None
    if not f:
        return min_size, max_size
    if "ObjectSizeGreaterThan" in f:
        min_size = f["ObjectSizeGreaterThan"]
    if "ObjectSizeLessThan" in f:
        max_size = f["ObjectSizeLessThan"]
    if "And" in f:
        and_block = f["And"]
        if "ObjectSizeGreaterThan" in and_block:
            min_size = and_block["ObjectSizeGreaterThan"]
        if "ObjectSizeLessThan" in and_block:
            max_size = and_block["ObjectSizeLessThan"]
    return min_size, max_size


def prefixes_overlap(p1: str, p2: str) -> bool:
    return p1.startswith(p2) or p2.startswith(p1)

def tags_overlap(t1: list, t2: list) -> bool:
    if not t1 or not t2:
        return True
    s1 = {(t.get("Key"), t.get("Value")) for t in t1}
    s2 = {(t.get("Key"), t.get("Value")) for t in t2}
    return bool(s1 & s2) or not s1 or not s2


def filters_overlap(r1: dict, r2: dict) -> bool:
    p1, p2 = get_filter_prefix(r1), get_filter_prefix(r2)
    if not prefixes_overlap(p1, p2):
        return False
    t1, t2 = get_filter_tags(r1), get_filter_tags(r2)
    if not tags_overlap(t1, t2):
        return False
    return True

def get_transitions(rule: dict) -> list:
    t = rule.get("Transitions", [])
    if not t:
        single = rule.get("Transition")
        if single:
            t = [single]
    return t


def get_noncurrent_transitions(rule: dict) -> list:
    t = rule.get("NoncurrentVersionTransitions", [])
    if not t:
        single = rule.get("NoncurrentVersionTransition")
        if single:
            t = [single]
    return t


def get_expiration_days(rule: dict) -> int | None:
    exp = rule.get("Expiration", {})
    if not exp:
        return None
    if "Days" in exp:
        return exp["Days"]
    return None


def get_noncurrent_expiration_days(rule: dict) -> int | None:
    exp = rule.get("NoncurrentVersionExpiration", {})
    if not exp:
        return None
    if "NoncurrentDays" in exp:
        return exp["NoncurrentDays"]
    return None

def get_newer_noncurrent_versions(rule: dict) -> int:
    exp = rule.get("NoncurrentVersionExpiration", {})  # linha 138 não aparece na foto (inferida)
    if not exp:
        return 0
    return exp.get("NewerNoncurrentVersions", 0)


def get_abort_days(rule: dict) -> int | None:
    abort = rule.get("AbortIncompleteMultipartUpload", {})
    if not abort:
        return None
    return abort.get("DaysAfterInitiation")


def has_expired_delete_marker(rule: dict) -> bool:
    exp = rule.get("Expiration", {})
    if not exp:
        return False
    return exp.get("ExpiredObjectDeleteMarker", False)


def check_nc01(rules: list) -> list:
    if not rules:
        return [{"codigo": "NC-01", "descricao": "Ausência de regras de Lifecycle habilitadas."}]
    return []


def check_nc02(rules: list) -> list:
    has_transition = any(get_transitions(r) or get_noncurrent_transitions(r) for r in rules)
    for r in rules:
        exp_days = get_expiration_days(r)
        if exp_days is not None and exp_days > 180:
            if not has_transition:
                return [{"codigo": "NC-02", "descricao": "Expiração superior a 180 dias sem regra de transição."}]
        nc_exp_days = get_noncurrent_expiration_days(r)
        if nc_exp_days is not None and nc_exp_days > 180:
            if not has_transition:
                return [{"codigo": "NC-02", "descricao": "Expiração de versões não atuais superior a 180 dias sem regra de transição."}]
    return []


def check_nc03(rules: list) -> list:
    for r in rules:
        if is_global_scope(r):
            exp_days = get_expiration_days(r)
            if exp_days is not None:
                return []
            exp = r.get("Expiration", {})
            if exp and "Date" in exp:
                return []
    return [{"codigo": "NC-03", "descricao": "Ausência de expiração para versões atuais com escopo global."}]

def check_nc04(rules: list, versioning: str) -> list:
    if versioning == "Disabled":
        return []
    for r in rules:
        if is_global_scope(r):
            nc_exp_days = get_noncurrent_expiration_days(r)
            if nc_exp_days is not None:
                newer = get_newer_noncurrent_versions(r)
                if newer == 0:
                    return []
    return [{"codigo": "NC-04", "descricao": "Ausência de expiração para versões não atuais com escopo global."}]


def check_nc05(rules: list) -> list:
    for r in rules:
        abort_days = get_abort_days(r)
        if abort_days is not None and abort_days <= 7:
            return []
    return [{"codigo": "NC-05", "descricao": "Ausência de controle sobre Multipart Uploads incompletos dentro de 7 dias."}]


def check_nc06(rules: list, versioning: str) -> list:
    if versioning == "Disabled":
        return []
    for r in rules:
        if has_expired_delete_marker(r):
            return []
        nc_exp = r.get("NoncurrentVersionExpiration", {})
        if nc_exp and nc_exp.get("NoncurrentDays") is not None:
            if has_expired_delete_marker(r):
                return []
    for r in rules:
        if has_expired_delete_marker(r):
            return []
    return [{"codigo": "NC-06", "descricao": "Ausência de expiração de Delete Markers."}]


def check_nc07(rules: list) -> list:
    results = []
    for r in rules:
        exp_days = get_expiration_days(r)
        if exp_days is not None and exp_days > 3650:
            results.append({
                "codigo": "NC-07",
                "descricao": f"Regra '{r.get('ID', 'sem ID')}' possui expiração de {exp_days} dias, superior ao limite de 3650 dias."
            })
        nc_exp_days = get_noncurrent_expiration_days(r)
        if nc_exp_days is not None and nc_exp_days > 3650:
            results.append({
                "codigo": "NC-07",
                "descricao": f"Regra '{r.get('ID', 'sem ID')}' possui expiração de versões não atuais de {nc_exp_days} dias, superior ao limite de 3650 dias."
            })
    return results

def check_nc08(rules: list) -> list:
    results = []
    for r in rules:
        nc_exp_days = get_noncurrent_expiration_days(r)
        if nc_exp_days is not None and nc_exp_days > 30:
            results.append({
                "codigo": "NC-08",
                "descricao": f"Regra '{r.get('ID', 'sem ID')}' mantém versões não atuais por {nc_exp_days} dias, superior ao limite de 30 dias."
            })
    return results


def check_nc09(rules: list) -> list:
    results = []
    for r in rules:
        transitions = get_transitions(r)
        if transitions:
            min_size, max_size = get_size_filter(r)
            if min_size is None or min_size < 128 * 1024:
                if max_size is None or max_size > 128 * 1024:
                    results.append({
                        "codigo": "NC-09",
                        "descricao": f"Regra '{r.get('ID', 'sem ID')}' permite transição de objetos menores que 128 KB."
                    })
    return results


def check_nc10(rules: list) -> list:
    results = []
    checked = set()
    for i, r1 in enumerate(rules):
        t1 = get_transitions(r1)
        if not t1:
            continue
        for j, r2 in enumerate(rules):
            if i >= j:
                continue
            t2 = get_transitions(r2)
            if not t2:
                continue
            if not filters_overlap(r1, r2):
                continue
            days1 = {tr.get("Days") for tr in t1 if tr.get("Days") is not None}
            days2 = {tr.get("Days") for tr in t2 if tr.get("Days") is not None}
            common = days1 & days2
            if common:
                key = tuple(sorted([r1.get("ID", str(i)), r2.get("ID", str(j))]))
                if key not in checked:
                    checked.add(key)
                    results.append({
                        "codigo": "NC-10",
                        "descricao": f"Transições concorrentes entre regras '{r1.get('ID', 'sem ID')}' e '{r2.get('ID', 'sem ID')}' no(s) dia(s) {sorted(common)}."
                    })
    return results

def check_nc11(rules: list) -> list:
    results = []
    for i, r1 in enumerate(rules):
        t1 = get_transitions(r1)
        trans_days = {tr.get("Days") for tr in t1 if tr.get("Days") is not None} if t1 else set()
        for j, r2 in enumerate(rules):
            exp_days = get_expiration_days(r2)
            if exp_days is None:
                continue
            if i == j:
                if exp_days in trans_days:
                    results.append({
                        "codigo": "NC-11",
                        "descricao": f"Regra '{r1.get('ID', 'sem ID')}' possui transição e expiração no mesmo dia ({exp_days})."
                    })
            else:
                if filters_overlap(r1, r2) and exp_days in trans_days:
                    results.append({
                        "codigo": "NC-11",
                        "descricao": f"Transição da regra '{r1.get('ID', 'sem ID')}' e expiração da regra '{r2.get('ID', 'sem ID')}' ocorrem no mesmo dia ({exp_days})."
                    })
    return results


def check_nc12(rules: list) -> list:
    results = []
    for r in rules:
        transitions = get_transitions(r)
        if not transitions:
            continue
        sorted_trans = sorted([t for t in transitions if t.get("Days") is not None], key=lambda x: x["Days"])
        exp_days = get_expiration_days(r)
        for idx, tr in enumerate(sorted_trans):
            tr_days = tr["Days"]
            tr_class = tr.get("StorageClass", "")
            min_duration = STORAGE_CLASS_MIN_DAYS.get(tr_class, 0)
            if min_duration == 0:
                continue
            next_action_day = None
            if idx + 1 < len(sorted_trans):
                next_action_day = sorted_trans[idx + 1]["Days"]
            if exp_days is not None:
                if next_action_day is None or exp_days < next_action_day:
                    next_action_day = exp_days
            if next_action_day is not None:
                if next_action_day - tr_days < min_duration:
                    results.append({
                        "codigo": "NC-12",
                        "descricao": f"Regra '{r.get('ID', 'sem ID')}': transição para {tr_class} no dia {tr_days} seguida de ação no dia {next_action_day}, antes da duração mínima de {min_duration} dias."
                    })
    return results

def check_nc13(rules: list) -> list:
    results = []
    for r in rules:
        transitions = get_transitions(r)
        if not transitions:
            continue
        for tr in transitions:
            if tr.get("StorageClass") == "INTELLIGENT_TIERING":
                days = tr.get("Days")
                if days is not None and days > 1:
                    results.append({
                        "codigo": "NC-13",
                        "descricao": f"Regra '{r.get('ID', 'sem ID')}' mantém objetos em STANDARD por {days} dias antes de transição para INTELLIGENT_TIERING."
                    })
    return results


def analyze(config: dict, bucket_name: str = "", versioning: str = "Enabled") -> dict:
    rules = get_enabled_rules(config)
    inconformidades = []

    nc01 = check_nc01(rules)
    if nc01:
        inconformidades.extend(nc01)
        return {
            "bucket_name": bucket_name,
            "versioning": versioning,
            "inconformidades": inconformidades,
            "conforme": False,
        }

    inconformidades.extend(check_nc02(rules))
    inconformidades.extend(check_nc03(rules))
    inconformidades.extend(check_nc04(rules, versioning))
    inconformidades.extend(check_nc05(rules))
    inconformidades.extend(check_nc06(rules, versioning))
    inconformidades.extend(check_nc07(rules))
    inconformidades.extend(check_nc08(rules))
    inconformidades.extend(check_nc09(rules))
    inconformidades.extend(check_nc11(rules))
    inconformidades.extend(check_nc12(rules))
    inconformidades.extend(check_nc10(rules))
    inconformidades.extend(check_nc13(rules))

    seen = set()
    unique = []
    for inc in inconformidades:
        key = (inc["codigo"], inc["descricao"])
        if key not in seen:
            seen.add(key)
            unique.append(inc)

    return {
        "bucket_name": bucket_name,
        "versioning": versioning,
        "inconformidades": unique,
        "conforme": len(unique) == 0,
    }

def main():
    if len(sys.argv) < 2:
        print("Uso: python analyze_s3_lifecycle.py <arquivo_config.json> [bucket_name] [versioning]", file=sys.stderr)
        sys.exit(1)
    config_file = sys.argv[1]
    bucket_name = sys.argv[2] if len(sys.argv) > 2 else ""
    versioning = sys.argv[3] if len(sys.argv) > 3 else "Enabled"
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    if isinstance(config, list):
        # Entrada em lote: lista de buckets, cada um com bucket_name, versioning e Rules
        result = [
            analyze(
                item,
                item.get("bucket_name", bucket_name),
                item.get("versioning", versioning),
            )
            for item in config
        ]
    else:
        # Entrada simples: um único bucket (objeto com "Rules")
        result = analyze(
            config,
            config.get("bucket_name", bucket_name),
            config.get("versioning", versioning),
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()