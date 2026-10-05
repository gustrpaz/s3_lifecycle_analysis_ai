"""Orchestrate S3 lifecycle analysis and script-generation calls to Bedrock."""

from __future__ import annotations

import argparse
from importlib import import_module
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "datasets" / "lifecycle_rules_model_input.json"
DEFAULT_ANALYSIS_OUTPUT = PROJECT_ROOT / "datasets" / "lifecycle_rules_genai_results.jsonl"
DEFAULT_KB = PROJECT_ROOT / "knowledge_base.md"
DEFAULT_ANALYSIS_PROMPT = PROJECT_ROOT / ".github" / "Prompts" / "analise_genai.prompt.md"
DEFAULT_SCRIPT_PROMPT = PROJECT_ROOT / ".github" / "Prompts" / "script-deterministico.prompt.md"
SYSTEM_INSTRUCTIONS = (
    "You analyze Amazon S3 Lifecycle configurations. The knowledge base in this "
    "system context is the sole authority for NC-01 through NC-13. Follow the "
    "task instructions in the user message. Do not use benchmark labels, expected "
    "results, or external criteria."
)
ANALYSIS_PLACEHOLDER = "[INSERIR JSON DO CENÁRIO]"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler JSON válido em {path}: {exc}") from exc


def load_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Não foi possível ler o prompt {path}: {exc}") from exc


def get_lifecycle_rules(record: dict[str, Any]) -> list[dict[str, Any]]:
    lifecycle = record.get("lifecycle_configuration")
    if isinstance(lifecycle, dict):
        rules = lifecycle.get("Rules")
    else:
        rules = record.get("Rules", record.get("lifecycle_rules"))
    if not isinstance(rules, list):
        raise ValueError("Cada entrada precisa conter Rules ou lifecycle_configuration.Rules.")
    if not all(isinstance(rule, dict) for rule in rules):
        raise ValueError("Cada item de Rules precisa ser um objeto JSON.")
    return rules


def normalize_case(record: dict[str, Any], request_bucket_name: str) -> dict[str, Any]:
    versioning = record.get("versioning")
    if versioning not in {"Disabled", "Enabled", "Suspended"}:
        raise ValueError(f"Estado de versionamento inválido: {versioning!r}.")
    return {
        "bucket_name": request_bucket_name,
        "versioning": versioning,
        "lifecycle_configuration": {"Rules": get_lifecycle_rules(record)},
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    cases = data if isinstance(data, list) else [data]
    if not all(isinstance(case, dict) for case in cases):
        raise ValueError("O arquivo de entrada deve conter um objeto ou uma lista de objetos.")
    return cases


def build_system_message(
    knowledge_base: str,
    use_cache: bool,
    cache_ttl: str,
) -> Any:
    system_message_type = import_module("langchain_core.messages").SystemMessage

    content: list[dict[str, Any]] = [
        {"type": "text", "text": SYSTEM_INSTRUCTIONS},
        {"type": "text", "text": knowledge_base},
    ]
    if use_cache:
        cache_point: dict[str, str] = {"type": "default"}
        if cache_ttl == "1h":
            cache_point["ttl"] = "1h"
        content.append({"cachePoint": cache_point})
    return system_message_type(content=content)


def create_chat_model(model_id: str, region: str | None, max_tokens: int, read_timeout: int) -> Any:
    try:
        chat_bedrock_converse = import_module("langchain_aws").ChatBedrockConverse
        botocore_config = import_module("botocore.config").Config
    except ImportError as exc:
        raise RuntimeError(
            "Dependências ausentes. Instale-as com: pip install -r requirements.txt"
        ) from exc

    model_options: dict[str, Any] = {
        "model_id": model_id,
        "temperature": 0,
        "max_tokens": max_tokens,
        "config": botocore_config(read_timeout=read_timeout, connect_timeout=10,retries={"max_attempts": 3, "mode": "standard"}),
    }
    if region:
        model_options["region_name"] = region
    return chat_bedrock_converse(**model_options)


def render_analysis_prompt(template: str, case_data: dict[str, Any]) -> str:
    if ANALYSIS_PLACEHOLDER not in template:
        raise ValueError(f"O prompt GenAI precisa conter {ANALYSIS_PLACEHOLDER}.")
    return template.replace(
        ANALYSIS_PLACEHOLDER,
        json.dumps(case_data, ensure_ascii=False, indent=2),
    )


def render_script_prompt(template: str, additional_instructions: str | None) -> str:
    if additional_instructions:
        return f"{template.rstrip()}\n\n## Solicitação adicional\n\n{additional_instructions.strip()}\n"
    return template


def response_text(response: Any) -> str:
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_blocks = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        return "\n".join(text_blocks).strip()
    raise ValueError("A resposta do modelo não contém texto reconhecível.")


def parse_json_response(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    start = candidate.find("{")
    if start < 0:
        raise ValueError("A resposta do modelo não contém um objeto JSON.")
    try:
        parsed, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"A resposta do modelo não é JSON válido: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("A resposta GenAI deve ser um objeto JSON.")

    required = {"bucket_name", "versioning", "conforme", "inconformidades"}
    missing = required - parsed.keys()
    if missing:
        raise ValueError(f"A resposta GenAI não contém os campos obrigatórios: {sorted(missing)}")
    if not isinstance(parsed["inconformidades"], list):
        raise ValueError("O campo inconformidades deve ser uma lista.")
    if not isinstance(parsed["conforme"], bool):
        raise ValueError("O campo conforme deve ser booleano.")
    if parsed["conforme"] != (len(parsed["inconformidades"]) == 0):
        raise ValueError("O campo conforme contradiz a lista inconformidades.")
    for finding in parsed["inconformidades"]:
        if not isinstance(finding, dict) or not re.fullmatch(r"NC-\d{2}", str(finding.get("codigo", ""))):
            raise ValueError("Cada inconformidade precisa conter um código NC-XX válido.")
    return parsed


def usage_metadata(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage
    metadata = getattr(response, "response_metadata", {})
    if isinstance(metadata, dict):
        usage = metadata.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def invoke_model(
    model: Any,
    system_message: Any,
    user_prompt: str,
) -> tuple[Any, str, str, int]:
    human_message_type = import_module("langchain_core.messages").HumanMessage

    started_at = datetime.now(timezone.utc)
    started_monotonic = time.perf_counter()

    response = model.invoke(
        [system_message, human_message_type(content=user_prompt)]
    )

    finished_at = datetime.now(timezone.utc)
    duration_ms = round(
        (time.perf_counter() - started_monotonic) * 1000
    )

    return (
        response,
        started_at.isoformat(),
        finished_at.isoformat(),
        duration_ms,
    )


def analyze_cases(args: argparse.Namespace) -> int:
    knowledge_base = args.knowledge_base.read_text(encoding="utf-8")
    template = load_prompt(args.prompt)
    records = load_cases(args.input)
    if args.bucket_name:
        records = [record for record in records if record.get("bucket_name") == args.bucket_name]
        if not records:
            raise ValueError(f"Bucket não encontrado no arquivo: {args.bucket_name}")
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit deve ser maior que zero.")
        records = records[: args.limit]

    model = create_chat_model(args.model_id, args.region, args.max_tokens, args.read_timeout)
    system_message = build_system_message(knowledge_base, args.cache, args.cache_ttl)
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed_buckets: set[str] = set()
    if args.resume and output_path.exists():
        for line_number, line in enumerate(output_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                previous = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Resultado JSONL inválido na linha {line_number} de {output_path}: {exc}"
                ) from exc
            if isinstance(previous, dict) and isinstance(previous.get("analysis"), dict):
                completed_buckets.add(str(previous.get("bucket_name", "")))

    output_mode = "a" if args.resume else "w"
    failures = 0
    processed = 0

    with output_path.open(output_mode, encoding="utf-8") as output_file:
        for index, record in enumerate(records, start=1):
            source_bucket_name = str(record.get("bucket_name", f"record-{index:04d}"))
            if source_bucket_name in completed_buckets:
                print(f"[{index}/{len(records)}] Já concluído: {source_bucket_name}", file=sys.stderr)
                continue

            model_bucket_name = (
                f"evaluation-record-{index:04d}" if args.blind else source_bucket_name
            )
            case_data = normalize_case(record, model_bucket_name)
            user_prompt = render_analysis_prompt(template, case_data)
            print(f"[{index}/{len(records)}] Enviando {source_bucket_name} ao Bedrock...", file=sys.stderr)
            try:
                (
                    response,
                    started_at,
                    finished_at,
                    duration_ms,
                ) = invoke_model(model, system_message, user_prompt)

                raw_response = response_text(response)
                analysis = parse_json_response(raw_response)
                analysis["bucket_name"] = source_bucket_name
                row = {
                    "bucket_name": source_bucket_name,
                    "analysis": analysis,
                    "raw_response": raw_response,
                    "usage": usage_metadata(response),
                    "model_id": args.model_id,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                }
                print(f"[{index}/{len(records)}] Concluído: {source_bucket_name}", file=sys.stderr)
            except Exception as exc:
                failures += 1
                row = {
                    "bucket_name": source_bucket_name,
                    "error": str(exc),
                    "model_id": args.model_id,
                }
                print(f"[{index}/{len(records)}] Falha em {source_bucket_name}: {exc}", file=sys.stderr)

            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            output_file.flush()
            processed += 1

    print(
        f"Processamento finalizado: {processed} chamada(s), {failures} falha(s). "
        f"Resultados em {output_path}",
        file=sys.stderr,
    )
    return 1 if failures else 0


def generate_script(args: argparse.Namespace) -> int:
    knowledge_base = args.knowledge_base.read_text(encoding="utf-8")
    template = load_prompt(args.prompt)
    extra = args.instructions
    if args.instructions_file:
        extra = args.instructions_file.read_text(encoding="utf-8")

    model = create_chat_model(args.model_id, args.region, args.max_tokens, args.read_timeout)
    system_message = build_system_message(knowledge_base, args.cache, args.cache_ttl)
    user_prompt = render_script_prompt(template, extra)
    (
        response,
        started_at,
        finished_at,
        duration_ms,
    ) = invoke_model(model, system_message, user_prompt)

    generated = response_text(response)
    try:
        compile(generated, str(args.output or "<generated_script>"), "exec")
    except SyntaxError as exc:
        raise ValueError(f"O script gerado não é sintaticamente válido: {exc}") from exc

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(generated + "\n", encoding="utf-8")
        print(f"Script gerado em {args.output}", file=sys.stderr)
    else:
        print(generated)
    print(
        json.dumps(
            {
                "model_id": args.model_id,
                "usage": usage_metadata(response),
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 0


def add_model_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model-id",
        default=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-5-5"),
        help="ID do modelo ou inference profile do Bedrock.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        help="Região AWS; usa AWS_REGION/AWS_DEFAULT_REGION ou a configuração AWS padrão.",
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--read-timeout", type=int, default=900, help="Tempo máximo, em segundos, aguardando a resposta do Bedrock (padrão: 900).")
    parser.add_argument("--no-cache", dest="cache", action="store_false")
    parser.set_defaults(cache=True)
    parser.add_argument("--cache-ttl", choices=("5m", "1h"), default="5m")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Orquestra prompts de Lifecycle S3 usando LangChain e Amazon Bedrock."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="Avalia um caso ou um arquivo de casos com GenAI.")
    analyze.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    analyze.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB)
    analyze.add_argument("--prompt", type=Path, default=DEFAULT_ANALYSIS_PROMPT)
    analyze.add_argument("--output", type=Path, default=DEFAULT_ANALYSIS_OUTPUT)
    analyze.add_argument("--bucket-name", help="Avalia somente este bucket do arquivo de entrada.")
    analyze.add_argument("--limit", type=int, help="Limita o número de entradas processadas.")
    analyze.add_argument(
        "--resume",
        action="store_true",
        help="Anexa ao JSONL existente e pula buckets que já têm análise concluída.",
    )
    analyze.add_argument(
        "--expose-bucket-name",
        dest="blind",
        action="store_false",
        help="Envia o nome original ao modelo. Por padrão, os nomes são anonimizados.",
    )
    analyze.set_defaults(blind=True, handler=analyze_cases)
    add_model_options(analyze)

    generate = commands.add_parser(
        "generate-script", help="Solicita ao modelo a geração/revisão do analisador determinístico."
    )
    generate.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB)
    generate.add_argument("--prompt", type=Path, default=DEFAULT_SCRIPT_PROMPT)
    generate.add_argument("--instructions", help="Instruções específicas adicionais.")
    generate.add_argument("--instructions-file", type=Path)
    generate.add_argument("--output", type=Path)
    add_model_options(generate)
    generate.set_defaults(handler=generate_script, max_tokens=8192)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cache_ttl == "1h" and not args.cache:
        parser.error("--cache-ttl 1h não pode ser usado com --no-cache.")
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())