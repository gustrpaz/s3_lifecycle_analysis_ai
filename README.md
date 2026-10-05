# Analisador de Políticas de Lifecycle S3

## Visão Geral

Este projeto implementa uma analise configurações de lifecycle de buckets AWS S3 e recomenda políticas otimizadas do ponto de vista de eficiência financeira. O sistema identifica inconformidades nas regras existentes e gera recomendações acionáveis.s

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

### NC-02 — Sem regras de transição e expiração configurada acima de 180 dias

**Descrição:** O bucket possui regras de expiração mas nenhuma regra de transição, e a expiração está configurada para mais de 180 dias.
**Recomendação:** Adicionar transição para Intelligent-Tiering no dia 0.
**Condição de disparo:** Nenhuma regra com ação `Transition` existe E alguma regra de expiração possui `Days > 180`

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

**Descrição:** Nenhuma regra de lifecycle cancela MPUs incompletos dentro de 7 dias.
**Recomendação:** Adicionar `AbortIncompleteMultipartUpload` com `DaysAfterInitiation=7`.
**Condição de disparo:** Nenhuma regra com `AbortIncompleteMultipartUpload` onde `DaysAfterInitiation <= 7`

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

**Descrição:** Uma regra de transição não possui filtro de tamanho mínimo, permitindo que objetos menores que 128 KB sejam transicionados. Isso é ineficiente pois as durações mínimas das classes tornam a transição de objetos pequenos mais cara do que mantê-los em STANDARD.
**Recomendação:** Adicionar filtro `ObjectSizeGreaterThan=131072` (128 KB em bytes) à regra de transição.
**Condição de disparo:** Qualquer regra com ação `Transition` E `Filter` não inclui `ObjectSizeGreaterThan >= 131072`

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
**Condição de disparo:** `(dia_expiracao OU dia_proxima_transicao) - dia_transicao < duracao_minima[classe]`
**Durações mínimas de referência:** STANDARD_IA/ONEZONE_IA = 30d, GLACIER_IR/GLACIER = 90d, DEEP_ARCHIVE = 180d

---

### NC-13 — Regras de transição que mantêm o objeto em STANDARD por mais de 1 dia antes da transição para Intelligent-Tiering

**Descrição:** Uma transição para INTELLIGENT_TIERING está configurada com `Days > 0`, fazendo com que os objetos permaneçam desnecessariamente em STANDARD (custo mais alto) antes de serem movidos.
**Recomendação:** Definir `Transition.Days=0` para regras de Intelligent-Tiering.
**Condição de disparo:** Qualquer regra com `Transition.StorageClass == "INTELLIGENT_TIERING"` E `Transition.Days > 0`

---

## Regras de interpretação

1. Considere somente regras com `Status == "Enabled"` na avaliação dos cenários. Para NC-01, isso significa que a inconformidade ocorre quando não há regras habilitadas, mesmo que existam regras desabilitadas.
2. Considere os filtros ao determinar se regras afetam o mesmo escopo. Para critérios que exigem escopo global, regras restritas por prefixo, tag ou outro filtro não são equivalentes.
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
ambiente e confirme que a conta tem acesso ao Claude Opus no Bedrock. O modelo padrão é o inference profile regional `us.anthropic.claude-opus-5-5`, pois o foundation model direto não aceita throughput on-demand. Informe a região explicitamente com `--region` ou configure `AWS REGION`/ `AWS_DEFAULT_REGION`. Outro model ID ou inference profile pode ser selecionado com `--model-id`

### Gerar o script determinístico

O modo de geração usa `.github/Prompts/script-deterministico.prompt.md` e
`knowledge_base.md`. Grave inicialmente em outro caminho para revisar e testar
o resultado sem substituir `scripts/analyze_s3_lifecycle.py`:

```bash
python scripts/orchestrate_bedrock.py generate-script \
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
  --region SUA_REGIAO_AWS
```

Cada execução faz uma chamada independente por bucket. Por padrão, os resultados
são gravados em `datasets/lifecycle_rules_genai_results.jsonl`, uma linha JSON
por case, incluindo análise validada, resposta bruta, uso de tokens e modelo.
Para escolher outro destino ou limitar um teste:

```bash
python scripts/orchestrate_bedrock.py analyze \
  --limit 3 \
  --output results/lote.jsonl \
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
```

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

---
