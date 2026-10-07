# Analisador de Políticas de Lifecycle S3

## Visão Geral

Este projeto implementa uma analise configurações de lifecycle de buckets AWS S3 e recomenda políticas otimizadas do ponto de vista de eficiência financeira. O sistema identifica inconformidades nas regras existentes e gera recomendações acionáveis.

---

## Glossário do Domínio

| Termo                               | Definição                                                                                                   |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Regra de Lifecycle**              | Configuração do AWS S3 que automatiza transições e expirações de objetos                                    |
| **Transição**                       | Movimentação de objetos entre classes de armazenamento (ex: STANDARD → INTELLIGENT_TIERING)                 |
| **Expiração**                       | Exclusão de versões atuais de objetos após N dias                                                           |
| **Versão não atual**                | Versões anteriores de um objeto quando o versionamento está ativo                                           |
| **Intelligent-Tiering (IT)**        | Classe de armazenamento do S3 que move objetos automaticamente entre tiers de acesso                        |
| **MPU**                             | Multipart Upload Incomplete — uploads iniciados mas nunca concluídos                                        |
| **Delete Marker**                   | Marcador deixado quando um objeto versionado é deletado                                                     |
| **Versionamento**                   | Funcionalidade do S3 que mantém múltiplas versões de um objeto. Estados: `Disabled`, `Enabled`, `Suspended` |
| **Duração mínima de armazenamento** | Período mínimo cobrado por classe de armazenamento (ver tabela abaixo)                                      |

### Durações Mínimas por Classe de Armazenamento S3

| Classe de Armazenamento | Duração Mínima |
| ----------------------- | -------------- |
| STANDARD                | Nenhuma        |
| INTELLIGENT_TIERING     | Nenhuma        |
| STANDARD_IA             | 30 dias        |
| ONEZONE_IA              | 30 dias        |
| GLACIER_IR              | 90 dias        |
| GLACIER                 | 90 dias        |
| DEEP_ARCHIVE            | 180 dias       |

---

### Ordem de temperatura das classes

`STANDARD` (0) → `STANDARD_IA` (1)→ `INTELLIGENT_TIERING` (2) → `ONEZONE_IA` (3) → `GLACIER_IR` (4) → `GLACIER` (5) → `DEEP_ARCHIVE` (6)

## Cenários de Inconformidade

Cada cenário possui:

- Um identificador único (`NC-XX`)
- Descrição da inconformidade
- Recomendação esperada

---

### NC-01 — Sem regras de ciclo de vida habilitadas

**Descrição:** O bucket não possui nenhuma regra de lifecycle.
**Recomendação:** Adicionar transição para Intelligent-Tiering no dia 0 + expiração em 3650 dias.
**Condição de disparo:** Não existe nenhuma regra com `Status == "Enabled"`.

---

### NC-02 — Expiração acima de 180 dias sem transição que a cubra

**Descrição:** O bucket possui regra de expiração acima de 180 dias cujo escopo não é coberto por nenhuma regra de transição, deixando esses objetos em STANDARD até a expiração.
**Recomendação:** Adicionar transição para Intelligent-Tiering no dia 0 com escopo que cubra o da expiração (global, quando a expiração for global).
**Condição de disparo:** Alguma regra habilitada possui `Expiration.Days > 180` E nenhuma regra habilitada com ação `Transition` cobre o escopo dessa expiração. A transição cobre a expiração quando, simultaneamente:

- o prefixo da transição é vazio ou é o início do prefixo da expiração;
- as tags da transição estão contidas nas tags da expiração;
- a transição não tem `ObjectSizeLessThan`, ou ele é `>=` ao da expiração;
- a transição não tem `ObjectSizeGreaterThan`, ou ele é `<= 131072` ou `<=` ao da expiração.

A cobertura é verificada por uma única regra de transição; a soma de transições por prefixo não conta. Exemplo: expiração global de 3650 dias com transição só em `dados/` dispara; expiração em `dados/` com transição em `dados/` não dispara.

---

### NC-03 — Sem regra de expiração para versões atuais sem filtro

**Descrição:** Nenhuma regra de lifecycle cobre a expiração de versões atuais em escopo global (sem filtro de prefixo ou tag).
**Recomendação:** Adicionar expiração em 3650 dias ou regra de arquivamento sem filtro.
**Condição de disparo:** Nenhuma regra com ação `Expiration` E `Filter` ausente ou vazio

---

### NC-04 — Sem regra de expiração para versões não atuais quando versionamento é diferente de `Disabled`

**Descrição:** O versionamento está `Enabled` ou `Suspended`, mas nenhuma regra expira versões não atuais em escopo global (sem filtro) sem retenção de últimas versões mais novas.
**Recomendação:** Adicionar `NoncurrentVersionExpiration` em até 30 dias, sem filtro.
**Condição de disparo:** `versioning != "Disabled"` E nenhuma regra habilitada com `NoncurrentVersionExpiration`, filtro global e sem `NewerNoncurrentVersions` maior que `0`.

---

### NC-05 — Sem regra para expirar Multipart Uploads incompletos em no máximo 7 dias

**Descrição:** Nenhuma regra de lifecycle com escopo global cancela MPUs incompletos dentro de 7 dias.
**Recomendação:** Adicionar `AbortIncompleteMultipartUpload` com `DaysAfterInitiation=7`, sem filtro.
**Condição de disparo:** Nenhuma regra habilitada com `AbortIncompleteMultipartUpload` onde `DaysAfterInitiation <= 7` E `Filter` ausente, vazio ou com `Prefix` vazio. O S3 não permite combinar essa ação com filtros de tag ou tamanho, então regras com prefixo não satisfazem o critério.

---

### NC-06 — Sem regra de expiração de Delete Marker quando versionamento está ativo

**Descrição:** O versionamento está ativo mas nenhuma regra está configurada para limpar delete markers expirados.
**Recomendação:** Adicionar `Expiration` com `ExpiredObjectDeleteMarker=true`.
**Condição de disparo:** `versioning != "Disabled"` E nenhuma regra com `Expiration.ExpiredObjectDeleteMarker == true`

---

### NC-07 — Expiração configurada acima de 3650 dias

**Descrição:** Alguma regra de expiração define exclusão após mais de 3650 dias (~10 anos).
**Recomendação:** Reduzir expiração para 3650 dias.
**Condição de disparo:** Qualquer regra com `Expiration.Days > 3650` OU `NoncurrentVersionExpiration.NoncurrentDays > 3650`

---

### NC-08 — Retenção de versões não atuais acima de 30 dias

**Descrição:** Uma regra mantém versões não atuais por mais de 30 dias, prolongando retenção e custo de armazenamento sem necessidade definida.
**Recomendação:** Reduzir `NoncurrentVersionExpiration.NoncurrentDays` para 30 dias ou menos, respeitando requisitos legais e operacionais de retenção.
**Condição de disparo:** Qualquer regra com `NoncurrentVersionExpiration.NoncurrentDays > 30`

---

### NC-09 — Regra de transição aplicável a objetos menores que 128 KB

**Descrição:** Uma regra de transição permite que objetos menores que 128 KB sejam transicionados, seja por filtro de tamanho customizado abaixo de 128 KB, seja pelo comportamento padrão `varies_by_storage_class`. Isso é ineficiente pois as durações mínimas das classes tornam a transição de objetos pequenos mais cara do que mantê-los em STANDARD.
**Recomendação:** Ajustar o filtro para `ObjectSizeGreaterThan=131072` (128 KB em bytes) ou usar `TransitionDefaultMinimumObjectSize=all_storage_classes_128K`.
**Condição de disparo:** Qualquer regra com ação `Transition` em que:

- o `Filter` possui `ObjectSizeLessThan` sem `ObjectSizeGreaterThan`, ou `ObjectSizeGreaterThan < 131072`; OU
- o `Filter` não possui filtro de tamanho, `TransitionDefaultMinimumObjectSize == "varies_by_storage_class"` e a transição é para `GLACIER` ou `DEEP_ARCHIVE`.

**Comportamento padrão da AWS (`TransitionDefaultMinimumObjectSize`):** `all_storage_classes_128K` impede a transição de objetos menores que 128 KB para qualquer classe; `varies_by_storage_class` permite essa transição apenas para `GLACIER` e `DEEP_ARCHIVE`. Filtros customizados de tamanho sempre têm precedência. Campo ausente é tratado como `all_storage_classes_128K`.

---

### NC-10 — Regras de transição concorrentes no mesmo dia para objetos sobrepostos

**Descrição:** Duas ou mais regras distintas de transição cobrem objetos sobrepostos e definem uma transição no mesmo dia. O S3 aplica a transição mais restritiva; regras concorrentes tornam o resultado ambíguo e podem provocar armazenamento numa classe não pretendida.
**Recomendação:** Consolidar as regras ou remover a transição concorrente menos restritiva.
**Condição de disparo:** Duas ou mais regras distintas com ação `Transition`, filtros com escopos sobrepostos e pelo menos um `Transition.Days` igual entre as regras. Transições sequenciais em dias diferentes não disparam NC-10.

---

### NC-11 — Transição e expiração no mesmo dia para objetos sobrepostos

**Descrição:** Uma regra transiciona objetos para outra classe no mesmo dia em que outra regra os expira, tornando a transição inútil e podendo gerar cobranças de duração mínima desnecessárias.
**Recomendação:** Remover a regra de transição.
**Condição de disparo:** Qualquer `Transition.Days` igual a `Expiration.Days` em regras com filtros sobrepostos ou sem filtro

---

### NC-12 — Transição para classe com duração mínima incompatível com expiração ou próxima transição

**Descrição:** Um objeto é transicionado para uma classe com duração mínima de armazenamento (ex: GLACIER = 90 dias), mas a expiração ou próxima transição ocorre antes desse mínimo ser atingido, gerando cobrança antecipada.
**Recomendação:** Ajustar a regra para respeitar a duração mínima de cada classe.
**Condição de disparo:** `(dia_expiracao OU dia_proxima_transicao) - dia_transicao < duracao_minima[classe]`, onde a próxima ação é a menor data posterior à transição entre as expirações e transições da mesma regra ou de outras regras habilitadas com escopo sobreposto. Transições que já disparam NC-11 não são reavaliadas na NC-12.
**Durações mínimas de referência:** STANDARD_IA/ONEZONE_IA = 30d, GLACIER_IR/GLACIER = 90d, DEEP_ARCHIVE = 180d

---

### NC-13 — Regras de transição que mantêm o objeto em STANDARD antes da transição para Intelligent-Tiering

**Descrição:** Uma transição para INTELLIGENT_TIERING está configurada com `Days > 0`, fazendo com que os objetos permaneçam desnecessariamente em STANDARD (custo mais alto) antes de serem movidos.
**Recomendação:** Definir `Transition.Days=0` para regras de Intelligent-Tiering.
**Condição de disparo:** Qualquer regra com `Transition.StorageClass == "INTELLIGENT_TIERING"` E `Transition.Days > 0`

---

### NC-14 — Transição para Intelligent-Tiering de objetos de vida curta

**Descrição:** Uma transição para INTELLIGENT_TIERING atinge objetos que expiram menos de 30 dias depois. O Intelligent-Tiering só move objetos para um nível mais barato após 30 dias consecutivos sem acesso, então esses objetos geram cobrança de transição e de monitoramento sem economia de armazenamento.
**Recomendação:** Remover a transição ou restringi-la a prefixos ou tags de objetos de vida longa.
**Condição de disparo:** Uma regra com `Transition.StorageClass == "INTELLIGENT_TIERING"` e uma regra de expiração com escopos sobrepostos, onde `0 < Expiration.Days - Transition.Days < 30`. Transição e expiração no mesmo dia são classificadas só como NC-11.
**Exceção (sem correção possível):** não dispara quando a transição cobre, conforme a NC-02, uma expiração com `Days > 180` cujo escopo se sobrepõe ao da expiração de vida curta. Remover ou restringir a transição dispararia a NC-02, e filtros de lifecycle não permitem excluir os objetos de vida curta. Exemplo: expiração global de 3650 dias + `tmp/` com 7 dias + transição global para IT no dia 0 não dispara; com expiração global de 90 dias, dispara.

---

## Regras de interpretação

1. Considere somente regras com `Status == "Enabled"` na avaliação dos cenários. Para NC-01, isso significa que a inconformidade ocorre quando não há regras habilitadas, mesmo que existam regras desabilitadas.
2. Considere os filtros ao determinar se regras afetam o mesmo escopo. Para critérios que exigem escopo global, regras restritas por prefixo, tag ou outro filtro não são equivalentes. **Escopo global:** `Filter` ausente, vazio ou com `Prefix` vazio. A NC-02 não exige escopo global, e sim que a transição cubra o escopo de cada expiração acima de 180 dias.
3. Avalie regras de versões não atuais e Delete Markers somente quando `versioning != "Disabled"`.
4. Uma configuração pode apresentar múltiplas inconformidades, aplicando as prioridades de resolução abaixo.

---

## Orquestrador Bedrock

O arquivo `scripts/orchestrate_bedrock.py` tem dois modos independentes:

- `generate-script`: envia ao Claude o prompt de desenvolvimento junto com o
  `knowledge_base.md`, para gerar ou revisar o analisador determinístico.
- `analyze`: envia uma chamada ao Bedrock por bucket do arquivo de entrada,
  recebe a avaliação GenAI e registra cada resposta no arquivo de resultados.

### Preparação

Instale as dependências no ambiente Python do projeto:

```bash
pip install -r requirements.txt
```

Configure credenciais AWS pelo perfil padrão do SDK ou pelas variáveis de
ambiente e confirme que a conta tem acesso ao Claude Opus no Bedrock. O modelo é escolhido com `--model-id` (ou pela variável `BEDROCK_MODEL_ID`).
O benchmark usa o inference profile `us.anthropic.claude-opus-4-5-20251101-v1:0`; passe-o explicitamente nos dois modos para manter a comparabilidade com a primeira rodada. Sem o parâmetro, o orquestrador usa `us.anthropic.claude-opus-5-5`. Informe a região explicitamente com `--region` ou configure `AWS_REGION`/`AWS_DEFAULT_REGION`.

### Gerar o script determinístico

O modo de geração usa `.github/Prompts/script-deterministico.prompt.md` e
`knowledge_base.md`. Grave inicialmente em outro caminho para revisar e testar
o resultado sem substituir `scripts/analyze_s3_lifecycle.py`:

```bash
python scripts/orchestrate_bedrock.py generate-script \
  --model-id us.anthropic.claude-opus-4-5-20251101-v1:0 \
  --output scripts/analyze_s3_lifecycle_generated.py \
  --region SUA_REGIAO_AWS
```

Também é possível acrescentar instruções específicas:

```bash
python scripts/orchestrate_bedrock.py generate-script \
  --instructions "Inclua testes unitários para cada NC" \
  --output scripts/analyze_s3_lifecycle_generated.py \
  --region SUA_REGIAO_AWS
```

Esse comando apenas gera o código; não o executa nem o valida automaticamente.
Revise e teste o arquivo gerado antes de adotá-lo.

Saída:

```bash
$ python scripts/orchestrate_bedrock.py generate-script \
  --model-id us.anthropic.claude-opus-4-5-20251101-v1:0 \
  --output scripts/analyze_s3_lifecycle_generated.py \
  --region us-east-1
Script gerado em scripts\analyze_s3_lifecycle_generated.py
{"model_id": "us.anthropic.claude-opus-4-5-20251101-v1:0", "usage": {"input_tokens": 5080, "output_tokens": 5348, "total_tokens": 10428, "input_token_details": {"cache_creation": 0, "cache_read": 0}}, "started_at": "2026-10-06T19:07:44.766571+00:00", "finished_at": "2026-10-06T19:08:44.660661+00:00", "duration_ms": 59895}
```

O prompt define o formato de entrada, a CLI e a análise em lote. Para avaliar a saída bruta do modelo, execute o script gerado sem editá-lo:

```bash
python scripts/analyze_s3_lifecycle_generated.py \
  datasets/lifecycle_rules_model_input.json \
  --output results/analysis_script_result.json
```

### Analisar com GenAI

O modo `analyze` usa `.github/Prompts/analise_genai.prompt.md`, o
`knowledge_base.md` e `datasets/lifecycle_rules_model_input.json`. Por padrão,
o modelo recebe um nome neutro (`evaluation-record-XXXX`) para não revelar o ID
do case. O nome original, como `bucket-case-27`, fica apenas no resultado local
para permitir o cruzamento com o gabarito.

Analise um bucket:

```bash
python scripts/orchestrate_bedrock.py analyze \
  --bucket-name bucket-case-27 \
  --region SUA_REGIAO_AWS
```

Analise todo o arquivo de entrada:

```bash
python scripts/orchestrate_bedrock.py analyze \
  --model-id us.anthropic.claude-opus-4-5-20251101-v1:0 \
  --output results/analysis_genai_results.json \
  --region SUA_REGIAO_AWS
```

Execute mais de uma vez para medir a variação entre execuções.

Cada execução faz uma chamada independente por bucket. Por padrão, os resultados
são gravados em `datasets/lifecycle_rules_genai_results.json`, um array JSON com
um item por case, incluindo análise validada, uso de tokens e modelo; a resposta
bruta só é incluída com `--include-raw-response`.
Para escolher outro destino ou limitar um teste:

```bash
python scripts/orchestrate_bedrock.py analyze \
  --limit 3 \
  --output results/lote.json \
  --region SUA_REGIAO_AWS
```

Se a execução for interrompida, `--resume` anexa ao arquivo de saída e pula
buckets que já tenham uma análise válida registrada:

```bash
python scripts/orchestrate_bedrock.py analyze --resume --region SUA_REGIAO_AWS
```

Sem `--resume`, o arquivo de saída é recriado. O cache do KB fica habilitado
por padrão com TTL de 5 minutos; use `--cache-ttl 1h` para o TTL de uma hora,
quando suportado pelo modelo, ou `--no-cache` para desativá-lo. O gabarito não
é enviado ao modelo; ele deve ser usado apenas posteriormente, em uma etapa
local de comparação.

Cada resposta é validada contra o schema definido no prompt antes de ser aceita. São rejeitadas as respostas em que:

- o `checklist` não contém exatamente os booleanos de NC-01 a NC-14;
- a lista `inconformidades` diverge dos itens `true` do checklist;
- o campo `conforme` contradiz o checklist;
- há códigos repetidos;
- uma inconformidade registrada tem justificativa afirmando que ela não se aplica;
- uma possível inconformidade adicional usa código NC-XX.

Respostas rejeitadas são gravadas com `error` e reprocessadas com `--resume`.

### Comparar os resultados

O `scripts/compare_results.py` cruza as saídas com `datasets/lifecycle_rules_gabarito.json`, sem chamar o Bedrock. Aceita a saída JSON do script e as saídas JSON do orquestrador, uma por execução:

```bash
python scripts/compare_results.py \
  --script results/rev/script.json \
  --genai results/rev/genai_run1.json results/rev/genai_run2.json results/rev/genai_run3.json \
  --output results/rev/comparacao.md
```

O relatório traz:

- métricas por fonte: acerto exato, classificação conforme / não conforme, precisão, recall, falsos positivos e negativos e respostas sem resultado;
- a tabela por cenário, com divergências em negrito;
- os erros por NC;
- os cenários em que as fontes divergem entre si;
- o consumo de tokens e o tempo das chamadas ao modelo.

Respostas rejeitadas pela validação de schema contam como "sem resultado".

---

## Saída Esperada por Cenário

Para cada cenário, a IA deve gerar três artefatos:

### 1. JSON de lifecycle conforme (válido — NÃO deve disparar a inconformidade)

```json
{
  "scenario": "NC-01",
  "conformity": "compliant",
  "lifecycle_configuration": {
    "Rules": []
  }
}
```

### 2. JSON de lifecycle não conforme (inválido — DEVE disparar a inconformidade)

```json
{
  "scenario": "NC-01",
  "conformity": "non_compliant",
  "expected_recommendation": "Adicionar transição IT dia 0 + expiração 3650 dias",
  "lifecycle_configuration": {
    "Rules": []
  }
}
```

---

## Contrato de Entrada Script Determinístico

O analisador recebe um objeto `BucketConfig` com a seguinte estrutura:

```python
@dataclass
class BucketConfig:
    name: str                        # Nome do bucket
    versioning: str                  # "Disabled" | "Enabled" | "Suspended"
    tags: dict[str, str]             # Tags do bucket
    lifecycle_rules: list[dict]      # Regras de lifecycle no formato da API AWS S3
    transition_default_minimum_object_size: str = "all_storage_classes_128K"  # ou "varies_by_storage_class"
```

`transition_default_minimum_object_size` corresponde ao campo `TransitionDefaultMinimumObjectSize` retornado por `GetBucketLifecycleConfiguration`. Nos datasets, o campo é opcional (`TransitionDefaultMinimumObjectSize` no nível do bucket); quando ausente, vale `all_storage_classes_128K`.

### Formato das regras de lifecycle (API AWS S3):

```json
{
  "ID": "id-da-regra",
  "Status": "Enabled",
  "Filter": {
    "Prefix": "",
    "ObjectSizeGreaterThan": 131072
  },
  "Transitions": [{ "Days": 0, "StorageClass": "INTELLIGENT_TIERING" }],
  "Expiration": { "Days": 3650 },
  "NoncurrentVersionExpiration": {
    "NoncurrentDays": 30,
    "NewerNoncurrentVersions": 0
  },
  "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 1 }
}
```

---

## Contrato de Saída

O analisador retorna um objeto `ResultadoAnalise`:

```python
@dataclass
class Recomendacao:
    scenario_id: str                 # ex: "NC-01"
    descricao: str                   # Descrição legível da inconformidade
    regra_recomendada: dict          # Regra de lifecycle compatível com a API AWS S3

@dataclass
class ResultadoAnalise:
    nome_bucket: str
    inconformidades: list[str]       # IDs dos cenários disparados, ex: ["NC-01", "NC-11"]
    recomendacoes: dict[str, Recomendacao]
    conforme: bool                   # True somente se inconformidades estiver vazio
```

---

## Prioridade e Resolução de Conflitos

Quando múltiplos cenários são disparados simultaneamente, aplicar nesta ordem:

1. **NC-01** sempre substitui todos os outros — se não há regras habilitadas, recomendar a baseline completa
2. **NC-11** tem precedência sobre NC-12— corrigir o conflito de mesmo dia antes de verificar durações mínimas
3. **NC-10** deve ser avaliado após NC-11— a análise de regras concorrentes só se aplica a regras não conflitantes
4. **NC-11** tem precedência sobre NC-14 — transição e expiração no mesmo dia contam só como NC-11
5. **Correção possível** — uma condição só é inconformidade se houver ajuste nas regras de lifecycle que a elimine sem disparar outro critério. A única situação sem correção prevista é a exceção da NC-14; não estender a outros critérios por interpretação

---
