#!/usr/bin/env python3
import json
import sys
import argparse
from typing import Any

STORAGE_CLASS_MIN_DAYS = {
    "STANDARD": 0,
    "INTELLIGENT_TIERING": 0,
    "STANDARD_IA": 30,
    "ONEZONE_IA": 30,
    "GLACIER_IR": 90,
    "GLACIER": 90,
    "GLACIER_FLEXIBLE_RETRIEVAL": 90,
    "DEEP_ARCHIVE": 180,
}


def parse_filter(rule: dict) -> dict:
    f = rule.get("Filter")
    result = {"prefix": "", "tags": [], "size_gt": None, "size_lt": None}
    if not f:
        return result
    if "Prefix" in f:
        result["prefix"] = f["Prefix"] or ""
    if "Tag" in f:
        result["tags"] = [f["Tag"]]
    if "ObjectSizeGreaterThan" in f:
        result["size_gt"] = f["ObjectSizeGreaterThan"]
    if "ObjectSizeLessThan" in f:
        result["size_lt"] = f["ObjectSizeLessThan"]
    if "And" in f:
        a = f["And"]
        result["prefix"] = a.get("Prefix", "") or ""
        result["tags"] = a.get("Tags", [])
        if "ObjectSizeGreaterThan" in a:
            result["size_gt"] = a["ObjectSizeGreaterThan"]
        if "ObjectSizeLessThan" in a:
            result["size_lt"] = a["ObjectSizeLessThan"]
    return result


def is_global_scope(flt: dict) -> bool:
    return flt["prefix"] == "" and not flt["tags"] and flt["size_gt"] is None and flt["size_lt"] is None


def is_global_scope_prefix_only(flt: dict) -> bool:
    return flt["prefix"] == "" and not flt["tags"]


def prefix_contains(outer: str, inner: str) -> bool:
    return inner.startswith(outer)


def tags_subset(outer_tags: list, inner_tags: list) -> bool:
    inner_set = {(t.get("Key"), t.get("Value")) for t in inner_tags}
    outer_set = {(t.get("Key"), t.get("Value")) for t in outer_tags}
    return outer_set <= inner_set


def size_filter_covers(outer: dict, inner: dict) -> bool:
    o_gt = outer["size_gt"]
    o_lt = outer["size_lt"]
    i_gt = inner["size_gt"]
    i_lt = inner["size_lt"]
    if o_gt is not None and o_gt <= 131072:
        o_gt = None
    if i_gt is not None and i_gt <= 131072:
        i_gt = None
    if o_gt is None and o_lt is None:
        return True
    if o_gt is not None:
        if i_gt is None:
            return False
        if i_gt < o_gt:
            return False
    if o_lt is not None:
        if i_lt is None:
            return False
        if i_lt > o_lt:
            return False
    return True


def filter_covers(outer: dict, inner: dict) -> bool:
    if not prefix_contains(outer["prefix"], inner["prefix"]):
        return False
    if not tags_subset(outer["tags"], inner["tags"]):
        return False
    if not size_filter_covers(outer, inner):
        return False
    return True


def filters_overlap(f1: dict, f2: dict) -> bool:
    t1 = {(t.get("Key"), t.get("Value")) for t in f1["tags"]}
    t2 = {(t.get("Key"), t.get("Value")) for t in f2["tags"]}
    for k1, v1 in t1:
        for k2, v2 in t2:
            if k1 == k2 and v1 != v2:
                return False
    g1 = f1["size_gt"] if f1["size_gt"] is not None else 0
    g2 = f2["size_gt"] if f2["size_gt"] is not None else 0
    l1 = f1["size_lt"] if f1["size_lt"] is not None else float("inf")
    l2 = f2["size_lt"] if f2["size_lt"] is not None else float("inf")
    low = max(g1, g2)
    high = min(l1, l2)
    if low >= high:
        return False
    return True


def get_transitions(rule: dict) -> list:
    ts = rule.get("Transitions", [])
    t = rule.get("Transition")
    if t:
        ts = ts + [t]
    return ts


def get_expiration_days(rule: dict) -> int | None:
    exp = rule.get("Expiration", {})
    if "Days" in exp:
        return exp["Days"]
    return None


def get_noncurrent_expiration_days(rule: dict) -> int | None:
    nve = rule.get("NoncurrentVersionExpiration", {})
    if "NoncurrentDays" in nve:
        return nve["NoncurrentDays"]
    if "NewerNoncurrentVersions" in nve and "NoncurrentDays" not in nve:
        return None
    return None


def get_newer_noncurrent_versions(rule: dict) -> int | None:
    nve = rule.get("NoncurrentVersionExpiration", {})
    return nve.get("NewerNoncurrentVersions")


def get_abort_days(rule: dict) -> int | None:
    ab = rule.get("AbortIncompleteMultipartUpload", {})
    return ab.get("DaysAfterInitiation")


def has_expired_delete_marker(rule: dict) -> bool:
    exp = rule.get("Expiration", {})
    return exp.get("ExpiredObjectDeleteMarker", False) is True


def analyze_bucket(bucket: dict) -> dict:
    bucket_name = bucket.get("bucket_name", "unknown")
    versioning = bucket.get("versioning", "Disabled")
    lc = bucket.get("lifecycle_configuration", bucket)
    rules_raw = lc.get("Rules", [])
    default_min_size = lc.get("TransitionDefaultMinimumObjectSize") or bucket.get("TransitionDefaultMinimumObjectSize") or "all_storage_classes_128K"
    enabled_rules = [r for r in rules_raw if r.get("Status") == "Enabled"]
    inconformidades = []

    def add(code: str, desc: str):
        inconformidades.append({"codigo": code, "descricao": desc})

    if not enabled_rules:
        add("NC-01", "Nenhuma regra de Lifecycle habilitada.")
        return {"bucket_name": bucket_name, "versioning": versioning, "inconformidades": inconformidades, "conforme": False}

    parsed_rules = []
    for r in enabled_rules:
        parsed_rules.append({
            "id": r.get("ID", ""),
            "filter": parse_filter(r),
            "transitions": get_transitions(r),
            "expiration_days": get_expiration_days(r),
            "noncurrent_expiration_days": get_noncurrent_expiration_days(r),
            "newer_noncurrent_versions": get_newer_noncurrent_versions(r),
            "abort_days": get_abort_days(r),
            "expired_delete_marker": has_expired_delete_marker(r),
            "raw": r,
        })

    for pr in parsed_rules:
        exp_days = pr["expiration_days"]
        if exp_days is not None and exp_days > 180:
            exp_filter = pr["filter"]
            covered = False
            for pr2 in parsed_rules:
                if pr2["transitions"]:
                    if filter_covers(pr2["filter"], exp_filter):
                        covered = True
                        break
            if not covered:
                add("NC-02", f"Regra '{pr['id']}' possui expiração em {exp_days} dias sem transição que a cubra.")

    has_global_expiration = any(pr["expiration_days"] is not None and is_global_scope(pr["filter"]) for pr in parsed_rules)
    if not has_global_expiration:
        add("NC-03", "Ausência de expiração para versões atuais com escopo global.")

    if versioning != "Disabled":
        has_global_noncurrent_exp = False
        for pr in parsed_rules:
            if pr["noncurrent_expiration_days"] is not None and is_global_scope(pr["filter"]):
                nnv = pr["newer_noncurrent_versions"]
                if nnv is None or nnv == 0:
                    has_global_noncurrent_exp = True
                    break
        if not has_global_noncurrent_exp:
            add("NC-04", "Ausência de expiração para versões não atuais com escopo global.")

    has_global_abort = False
    for pr in parsed_rules:
        ab = pr["abort_days"]
        if ab is not None and ab <= 7:
            flt = pr["filter"]
            if is_global_scope_prefix_only(flt) and flt["size_gt"] is None and flt["size_lt"] is None:
                has_global_abort = True
                break
    if not has_global_abort:
        add("NC-05", "Ausência de controle sobre Multipart Uploads incompletos com escopo global em até 7 dias.")

    if versioning != "Disabled":
        has_delete_marker_handling = any(pr["expired_delete_marker"] for pr in parsed_rules)
        if not has_delete_marker_handling:
            has_noncurrent_exp_global = any(
                pr["noncurrent_expiration_days"] is not None and is_global_scope(pr["filter"])
                for pr in parsed_rules
            )
            if not has_noncurrent_exp_global:
                has_delete_marker_handling = False
            else:
                has_delete_marker_handling = True
        if not has_delete_marker_handling:
            add("NC-06", "Ausência de expiração de Delete Markers.")

    for pr in parsed_rules:
        if pr["expiration_days"] is not None and pr["expiration_days"] > 3650:
            add("NC-07", f"Regra '{pr['id']}' possui expiração de versões atuais superior a 3650 dias ({pr['expiration_days']} dias).")
        if pr["noncurrent_expiration_days"] is not None and pr["noncurrent_expiration_days"] > 3650:
            add("NC-07", f"Regra '{pr['id']}' possui expiração de versões não atuais superior a 3650 dias ({pr['noncurrent_expiration_days']} dias).")

    for pr in parsed_rules:
        ncd = pr["noncurrent_expiration_days"]
        if ncd is not None and ncd > 30:
            add("NC-08", f"Regra '{pr['id']}' mantém versões não atuais por {ncd} dias, superior ao limite de 30 dias.")

    for pr in parsed_rules:
        flt = pr["filter"]
        for t in pr["transitions"]:
            sc = t.get("StorageClass", "")
            t_days = t.get("Days")
            has_custom_size = flt["size_gt"] is not None or flt["size_lt"] is not None
            if has_custom_size:
                if flt["size_lt"] is not None and flt["size_gt"] is None:
                    add("NC-09", f"Regra '{pr['id']}' permite transição de objetos menores que 128 KB (filtro ObjectSizeLessThan sem ObjectSizeGreaterThan).")
                elif flt["size_gt"] is not None and flt["size_gt"] < 131072:
                    add("NC-09", f"Regra '{pr['id']}' permite transição de objetos menores que 128 KB (ObjectSizeGreaterThan={flt['size_gt']}).")
            else:
                if default_min_size == "varies_by_storage_class" and sc in ("GLACIER", "DEEP_ARCHIVE", "GLACIER_FLEXIBLE_RETRIEVAL"):
                    add("NC-09", f"Regra '{pr['id']}' permite transição de objetos menores que 128 KB para {sc} sob varies_by_storage_class.")

    nc11_pairs = set()
    for i, pr1 in enumerate(parsed_rules):
        for t1 in pr1["transitions"]:
            d1 = t1.get("Days")
            if d1 is None:
                continue
            for j, pr2 in enumerate(parsed_rules):
                if i == j:
                    continue
                for t2 in pr2["transitions"]:
                    d2 = t2.get("Days")
                    if d2 is None:
                        continue
                    if d1 == d2 and filters_overlap(pr1["filter"], pr2["filter"]):
                        pair = tuple(sorted([pr1["id"], pr2["id"]]))
                        if pair not in nc11_pairs:
                            add("NC-10", f"Transições concorrentes no dia {d1} entre regras '{pr1['id']}' e '{pr2['id']}'.")
                            nc11_pairs.add(pair)

    nc11_transitions = set()
    for pr in parsed_rules:
        exp_days = pr["expiration_days"]
        if exp_days is None:
            continue
        for t in pr["transitions"]:
            t_days = t.get("Days")
            if t_days is not None and t_days == exp_days:
                add("NC-11", f"Regra '{pr['id']}' possui transição e expiração no mesmo dia ({t_days}).")
                nc11_transitions.add((pr["id"], t_days, t.get("StorageClass", "")))

    for i, pr1 in enumerate(parsed_rules):
        for t in pr1["transitions"]:
            t_days = t.get("Days")
            if t_days is None:
                continue
            for j, pr2 in enumerate(parsed_rules):
                if i == j:
                    continue
                exp2 = pr2["expiration_days"]
                if exp2 is not None and t_days == exp2 and filters_overlap(pr1["filter"], pr2["filter"]):
                    key = (pr1["id"], t_days, t.get("StorageClass", ""))
                    if key not in nc11_transitions:
                        add("NC-11", f"Transição da regra '{pr1['id']}' no dia {t_days} coincide com expiração da regra '{pr2['id']}'.")
                        nc11_transitions.add(key)

    for pr in parsed_rules:
        for t in pr["transitions"]:
            t_days = t.get("Days")
            sc = t.get("StorageClass", "")
            if t_days is None or sc not in STORAGE_CLASS_MIN_DAYS:
                continue
            min_stay = STORAGE_CLASS_MIN_DAYS[sc]
            if min_stay == 0:
                continue
            next_action_day = None
            exp_days = pr["expiration_days"]
            if exp_days is not None and exp_days > t_days:
                if (pr["id"], t_days, sc) not in nc11_transitions:
                    next_action_day = exp_days
            for t2 in pr["transitions"]:
                t2_days = t2.get("Days")
                if t2_days is not None and t2_days > t_days:
                    if next_action_day is None or t2_days < next_action_day:
                        next_action_day = t2_days
            for pr2 in parsed_rules:
                if pr2["id"] == pr["id"]:
                    continue
                if not filters_overlap(pr["filter"], pr2["filter"]):
                    continue
                exp2 = pr2["expiration_days"]
                if exp2 is not None and exp2 > t_days:
                    if next_action_day is None or exp2 < next_action_day:
                        next_action_day = exp2
                for t2 in pr2["transitions"]:
                    t2_days = t2.get("Days")
                    if t2_days is not None and t2_days > t_days:
                        if next_action_day is None or t2_days < next_action_day:
                            next_action_day = t2_days
            if next_action_day is not None:
                stay = next_action_day - t_days
                if stay < min_stay:
                    add("NC-12", f"Regra '{pr['id']}' transiciona para {sc} no dia {t_days}, mas próxima ação ocorre no dia {next_action_day} ({stay} dias), inferior à duração mínima de {min_stay} dias.")

    for pr in parsed_rules:
        for t in pr["transitions"]:
            sc = t.get("StorageClass", "")
            t_days = t.get("Days")
            if sc == "INTELLIGENT_TIERING" and t_days is not None and t_days > 0:
                add("NC-13", f"Regra '{pr['id']}' mantém objetos em STANDARD por {t_days} dias antes de transicionar para INTELLIGENT_TIERING.")

    for pr in parsed_rules:
        exp_days = pr["expiration_days"]
        if exp_days is None:
            continue
        for t in pr["transitions"]:
            sc = t.get("StorageClass", "")
            t_days = t.get("Days")
            if sc != "INTELLIGENT_TIERING" or t_days is None:
                continue
            diff = exp_days - t_days
            if 0 < diff < 30:
                if (pr["id"], t_days, sc) in nc11_transitions:
                    continue
                if exp_days > 180:
                    continue
                add("NC-14", f"Regra '{pr['id']}' transiciona para INTELLIGENT_TIERING no dia {t_days} com expiração no dia {exp_days} ({diff} dias em IT, inferior a 30).")

    conforme = len(inconformidades) == 0
    return {
        "bucket_name": bucket_name,
        "versioning": versioning,
        "inconformidades": inconformidades,
        "conforme": conforme,
    }


def main():
    parser = argparse.ArgumentParser(description="Analisador de políticas de Lifecycle S3")
    parser.add_argument("input_file", help="Arquivo JSON de entrada")
    parser.add_argument("--output", "-o", help="Arquivo JSON de saída (opcional)")
    args = parser.parse_args()

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(json.dumps({"erro": f"Falha ao ler arquivo de entrada: {e}"}), file=sys.stderr)
        sys.exit(1)

    is_list = isinstance(data, list)
    buckets = data if is_list else [data]
    results = []
    has_error = False

    for bucket in buckets:
        try:
            if not isinstance(bucket, dict):
                raise ValueError("Entrada de bucket inválida: não é um objeto")
            if "bucket_name" not in bucket:
                raise ValueError("Campo 'bucket_name' ausente")
            result = analyze_bucket(bucket)
            results.append(result)
        except Exception as e:
            has_error = True
            bn = bucket.get("bucket_name", "unknown") if isinstance(bucket, dict) else "unknown"
            results.append({"bucket_name": bn, "erro": str(e)})

    output = results if is_list else results[0]
    output_str = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
    else:
        print(output_str)

    if has_error:
        sys.exit(1)


if __name__ == "__main__":
    main()