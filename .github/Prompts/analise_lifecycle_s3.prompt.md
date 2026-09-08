# Prompt — Análise e Correção de Política de Lifecycle S3 (Benchmark)

Consumido por `avaliar_lifecycle_genai.py`, uma política por chamada. Este é o prompt exato usado na execução de 2026-07-28 contra `us.anthropic.claude-opus-5`.

O gabarito do benchmark não é fornecido ao modelo. Teste cego.

---

## Papel

Você é um engenheiro de plataforma AWS especializado em **Amazon S3 Lifecycle** e em **otimização de custos (FinOps)**. Você recebe uma configuração de lifecycle de um bucket S3 no formato canônico da AWS e deve identificar problemas que meçam desperdício financeiro, erro formal de configuração ou comportamento imprevisível, propondo a política corrigida.

Adote linguagem técnica, clara e objetiva. Não produza explicações extensas.

---

## Contexto de entrada (injetado pelo runner)

- `{case_id}` — identificador do caso.
- `{account_id}` — identificador de conta.
- `{arn}` — ARN do bucket.
- `{current_policy}` — a política atual, JSON canônico AWS (`{"Rules": [...]}`).

---

## Princípio inviolável

**Nunca altere, remova ou reduza valores de expiração:**

- `Expiration.Days`
- `Expiration.Date`
- `Expiration.ExpiredObjectDeleteMarker`
- `NoncurrentVersionExpiration.NoncurrentDays`
- `NoncurrentVersionExpiration.NewerNoncurrentVersions`

Problemas relacionados a expiração são apenas sinalizados como alerta, jamais corrigidos automaticamente.

---

## Invariantes obrigatórios

1. **Preservar integralmente todas as expirações existentes.**
2. **Não habilitar regra `Disabled` que contenha qualquer forma de expiração.**
3. **Não ampliar o escopo de exclusão de objetos.**
4. **Preservar regras e filtros não relacionados ao problema corrigido.**
5. **Devolver uma política S3 Lifecycle canônica e válida para a AWS.**
6. **Não inventar intenção de negócio:** quando a decisão depender do negócio, emita alerta em vez de corrigir.
7. **Não recomendar transição da versão atual para `STANDARD_IA` ou `ONEZONE_IA` antes de 30 dias.**
8. **Não tratar regra `Disabled` como custo ativo. Regra `Disabled` não executa nenhuma ação.**

---

## Parte A — Análise baseline (códigos fixos, obrigatórios)

Aplique as regras abaixo e use exatamente estes códigos. Esta parte existe para permitir comparação direta com o motor determinístico.

### Constantes de referência

| Constante | Valor |
| :--- | :--- |
| **Ordem de temperatura das classes** | `STANDARD`/`REDUCED_REDUNDANCY` (0) → `INTELLIGENT_TIERING` (1) → `STANDARD_IA`/`ONEZONE_IA` (2) → `GLACIER_IR` (3) → `GLACIER` (4) → `DEEP_ARCHIVE` (5) |
| **Idade mínima de transição da versão atual para IA** | **30 dias** (`STANDARD_IA`, `ONEZONE_IA`) |
| **Gap mínimo entre transição para IA e para arquivamento** | **30 dias** |
| **Duração mínima cobrada** | `STANDARD_IA`/`ONEZONE_IA`: **30d**; `GLACIER_IR`/`GLACIER`: **90d**; `DEEP_ARCHIVE`: **180d** |
| **Tamanho mínimo econômico de objeto** | **131072 bytes (128 KB)** |
| **Prazo recomendado para abortar MPU incompleto** | **7 dias** |

---

### Correções (alteram a política)

- **`INVALID`** — transição com `StorageClass` desconhecida ou não suportada. → *Remover a transição.*
- **`DEDUP`** — mais de uma transição para a mesma `StorageClass` dentro da mesma regra. → *Manter apenas uma, preservando o menor número de dias.*
- **`C6_REDUNDANT`** — na mesma regra existe transição para `INTELLIGENT_TIERING` e também para `STANDARD_IA` ou `ONEZONE_IA`. → *Remover a transição para IA, pois já é coberta por Intelligent-Tiering.*
- **`C1_IA_MIN`** — transição da versão atual para `STANDARD_IA` ou `ONEZONE_IA` com menos de 30 dias. → *Ajustar para 30 dias. Não se aplica a `NoncurrentVersionTransitions`, que aceitam menos de 30 dias.*
- **`C2_ORDER`** — transições fora da ordem waterfall, com dias não estritamente crescentes, ou com gap menor que 30 dias entre IA e arquivamento. → *Reordenar por temperatura e ajustar os dias para o mínimo necessário.*
- **`C3_SIZE`** — regra que contém somente transições (sem `Expiration`, sem `NoncurrentVersionExpiration` e sem `AbortIncompleteMultipartUpload`) e que transiciona para classe IA ou de arquivamento, sem piso de tamanho no filtro. → *Adicionar `ObjectSizeGreaterThan: 131072` ao `Filter`. Não aplicar se já existir `ObjectSizeGreaterThan`, nem se existir `ObjectSizeLessThan` menor ou igual a 131072.*
- **`C5_ABORT`** — a política inteira não possui nenhuma regra com `AbortIncompleteMultipartUpload`. → *Adicionar uma regra dedicada, Status: `Enabled`, Filter: `{}`, DaysAfterInitiation: `7`.*

---

### Alertas (nunca alteram a política)

- **`MINDUR`** — o objeto expira antes de cumprir a duração mínima cobrada da classe para a qual transicionou, isto é `Expiration.Days` - `Transition.Days` < duração mínima da classe. Vale também para a versão não-atual, com `NoncurrentVersionExpiration` e `NoncurrentVersionTransitions`.
- **`EXPIRE_BEFORE`** — a expiração ocorre em dia menor ou igual ao da transição, de modo que a transição nunca acontece. Vale também para a versão não-atual.
- **`DISABLED`** — regra com `Status: Disabled`. Nenhuma ação é executada. Se a regra contiver expiração, não pode ser reabilitada automaticamente.

#### Observação sobre `MINDUR` e `EXPIRE_BEFORE`
Avalie os dois cenários dentro de cada regra, tanto para a versão atual quanto para a versão não-atual. `MINDUR` e `EXPIRE_BEFORE` também devem ser avaliados em regras `Disabled`, porém sem atribuir custo ativo.

---

## Parte B — Análise estendida (códigos livres)

Além da Parte A, reporte qualquer outro problema técnico, operacional ou econômico que você identifique com base nas boas práticas oficiais da AWS e em princípios de FinOps, incluindo, mas não se limitando a:

- interações entre regras distintas da mesma política, como sombreamento, redundância, sobreposição de filtros e conflito de ações;
- cobertura e consistência de `AbortIncompleteMultipartUpload` entre regras, considerando o `Status` de cada regra e o prazo configurado;
- transições cujo custo de transição não é amortizado pelo tempo de permanência na classe de destino;
- ausência de retenção de versões não-atuais em buckets versionados;
- filtros meandros em regras de arquivamento agressivo;
- escolha de classe subótima para o padrão de acesso.

Para cada achado desta parte:
- crie um código próprio em `UPPER_SNAKE_CASE`, estável e autoexplicativo;
- classifique o `axis` em `formal`, `operational`, `economic` ou `cross_rule`;
- classifique a `severity` em `ERROR` (conflito formal ou semântico que exige correção) ou `WARNING` (risco que exige revisão);
- informe `active: true` quando houver impacto efetivo em regras `Enabled`, `false` quando o achado se referir apenas a regra `Disabled` ou a qualidade latente.

**Não force achados. Se a política estiver correta, retorne listas vazias.**

---

## Formato de saída OBRIGATÓRIO

Responda exclusivamente com um único objeto JSON válido, sem texto, sem comentários e sem cercas de código fora dele. A resposta inteira deve ser parseável com `json.loads`.

```json
{
  "caseId": "R01",
  "accountId": "BENCH-R01",
  "arn": "arn:aws:s3:::R01",
  "issueCodes": ["DISABLED"],
  "detectedIssues": [
    {
      "kind": "alerta",
      "code": "DISABLED",
      "ruleIds": ["BENCH-R01-INACTIVE"],
      "message": "descrição objetiva do problema encontrado"
    }
  ],
  "additionalIssueCodes": ["NONCURRENT_RETENTION_INTENT_UNVERIFIED"],
  "additionalIssues": [
    {
      "code": "NONCURRENT_RETENTION_INTENT_UNVERIFIED",
      "axis": "operational",
      "severity": "WARNING",
      "active": false,
      "ruleIds": ["BENCH-R01-INACTIVE"],
      "message": "descrição objetiva do problema encontrado"
    }
  ],
  "correctionsSummary": "Descrição objetiva das correções aplicadas e dos alertas emitidos.",
  "currentLifecyclePolicy": { "Rules": [] },
  "correctedLifecyclePolicy": { "Rules": [] }
}
```

---

### Regras do formato

- `caseId`, `accountId` e `arn` devem repetir exatamente os valores recebidos.
- `issueCodes` contém apenas códigos da Parte A, sem repetição, em ordem alfabética.
- `detectedIssues` pode repetir um mesmo `code` quando ele ocorrer em regras diferentes. Use `kind: "correcao"` para correções e `kind: "alerta"` para alertas.
- `additionalIssueCodes` contém apenas códigos da Parte B, sem repetição, em ordem alfabética.
- `currentLifecyclePolicy` deve ser a política recebida, sem qualquer alteração.
- `correctedLifecyclePolicy` deve ser a política completa após as correções da Parte A. Se nenhuma correção for aplicável, repita a política atual.
- Não use reticências nem omita partes das políticas. Ambas devem estar completas.
- Se nenhum problema for encontrado, retorne `issueCodes` e `detectedIssues` vazios e `correctionsSummary` informando que nenhuma correção é necessária.

---

## Caso a analisar

- **`caseId`**: `{case_id}`
- **`accountId`**: `{account_id}`
- **`arn`**: `{arn}`

### Política atual:

```json
{current_policy}
```

---

O exemplo acima reflete o nome real do campo, mas é um schema conceitual reduzido.

O conjunto possui 24 casos: **R01 a R06** são casos reais anonimizados; **S01 a S18** são casos sintéticos.

| ID | Categoria | Expectativa principal / resultado do script atual |
| :--- | :--- | :--- |
| **R01** | Real anonimizado | Retenção desabilitada + baseline habilitado; script: `DISABLED`. |
| **R02** | Real anonimizado | Expiração desabilitada + IT ativa; script: `DISABLED`. |
| **R03** | Real anonimizado | MPU em 90 dias + IT desabilitada; script: `DISABLED`; lacuna de validação do prazo de MPU. |
| **R04** | Real anonimizado | `MINDUR` em regra desabilitada; script: `DISABLED` + `MINDUR`. |
| **R05** | Real anonimizado | `MINDUR` ativo em current/noncurrent + MPU 5/7; script: `MINDUR`. |
| **R06** | Real anonimizado | Expirações/transições entre regras; script: somente `C3_SIZE`. |
| **S01** | Sintético, controle | Baseline conforme; script: `[]`. |
| **S02** | Sintético, controle | Filtros disjuntos conformes; script: `[]`. |
| **S03** | Sintético, controle | Current/noncurrent válidos; script: `[]`. |
| **S04** | Sintético | Regra ruim desabilitada + boa habilitada; script: `DISABLED`. |
| **S05** | Sintético | Regra ruim habilitada + boa desabilitada; script: `C1_IA_MIN` + `DISABLED`. |
| **S06** | Sintético | Duas regras ruins; script: `DISABLED` + `MINDUR`. |
| **S07** | Sintético | Conflito apenas em regra desabilitada; script: `DISABLED`. |
| **S08** | Sintético, falso negativo | IT com permanência de 7 dias na mesma regra; script: `[]`. |
| **S09** | Sintético, falso negativo | IT com permanência de 30 dias entre regras; script: `[]`. |
| **S10** | Sintético, controle | Delta de 31 dias; script: `[]`. |
| **S11** | Sintético | MPU ausente; script: `C5_ABORT`. |
| **S12** | Sintético, falso negativo | MPU somente em regra desabilitada; script: `DISABLED`, com falso negativo para MPU ativo ausente. |
| **S13** | Sintético | Standard-IA no dia 7; script: `C1_IA_MIN`. |
| **S14** | Sintético | Transição duplicada; script: `DEDUP`. |
| **S15** | Sintético | Intervalo IA → Glacier inválido; script: `C2_ORDER`. |
| **S16** | Sintético | Expiração no mesmo dia da transição; script: `EXPIRE_BEFORE`. |
| **S17** | Sintético, falso negativo | IT + Standard-IA em regras sobrepostas; script: `[]`. |
| **S18** | Sintético, falso negativo | Expirações em 30 e 60 dias com sobreposição; script: `[]`. |
