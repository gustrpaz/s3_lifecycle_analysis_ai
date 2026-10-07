# Analisador de Políticas de Lifecycle S3

## 1. Visão geral

Este projeto tem como objetivo analisar configurações de políticas de
Lifecycle do Amazon S3 e identificar situações que possam representar
inconformidades de configuração ou oportunidades de otimização financeira.

A análise considera regras de transição, expiração, versionamento,
Multipart Uploads incompletos, Delete Markers e demais características
da configuração de Lifecycle.

Este documento constitui a base de conhecimento utilizada pelas
abordagens de análise do projeto.

As regras descritas neste documento definem os critérios que devem ser
considerados durante a avaliação.

---

## 2. Glossário

| Termo               | Definição                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------- |
| Regra de Lifecycle  | Configuração do Amazon S3 que automatiza ações sobre objetos ao longo do tempo.             |
| Transição           | Movimentação de objetos entre classes de armazenamento.                                     |
| Expiração           | Exclusão de objetos ou versões após determinado período.                                    |
| Versão não atual    | Versão anterior de um objeto quando o versionamento está habilitado.                        |
| Intelligent-Tiering | Classe de armazenamento que realiza movimentação automática entre níveis de acesso.         |
| Multipart Upload    | Processo utilizado para realizar uploads de objetos em múltiplas partes.                    |
| Delete Marker       | Marcador criado quando um objeto versionado é excluído.                                     |
| Versionamento       | Recurso que permite manter múltiplas versões de um objeto.                                  |
| Filtro              | Critério utilizado para determinar quais objetos são afetados por uma regra de Lifecycle.   |
| Duração mínima      | Período mínimo associado à permanência de objetos em determinadas classes de armazenamento. |

---

## 3. Classes de armazenamento

As seguintes classes e características devem ser consideradas durante
a análise:

| Classe              | Duração mínima |
| ------------------- | -------------: |
| STANDARD            |        Nenhuma |
| INTELLIGENT_TIERING |        Nenhuma |
| STANDARD_IA         |        30 dias |
| ONEZONE_IA          |        30 dias |
| GLACIER_IR          |        90 dias |
| GLACIER             |        90 dias |
| DEEP_ARCHIVE        |       180 dias |

---

## 4. Critérios de avaliação

A análise deve verificar as seguintes situações.

### NC-01 — Ausência de regras de Lifecycle

Verificar se o bucket não possui nenhuma regra de Lifecycle habilitada.
Regras com `Status` igual a `Disabled` não contam como regras ativas.

---

### NC-02 — Expiração acima de 180 dias sem transição que a cubra

Dispara quando uma regra com `Expiration.Days > 180` não tem uma regra
de transição cujo escopo contenha o dela: prefixo igual ou mais amplo,
sem tags adicionais e filtro de tamanho igual ou mais amplo
(`ObjectSizeGreaterThan` de até 131072 é sempre aceito, pois equivale
ao padrão do S3; ver NC-09).

Exemplo: expiração global com transição só em `dados/` dispara;
expiração em `dados/` com transição em `dados/` ou global não dispara.

---

### NC-03 — Ausência de expiração para versões atuais

Verificar se não existe regra de expiração para versões atuais com
escopo global, considerando regras sem filtro.

---

### NC-04 — Ausência de expiração para versões não atuais

Quando o versionamento estiver diferente de `Disabled`, verificar se
existe uma regra habilitada de expiração para versões não atuais com
escopo global e sem retenção explícita de versões não atuais mais novas.
Uma regra com `NewerNoncurrentVersions` maior que `0` não atende a este
critério.

---

### NC-05 — Ausência de controle sobre Multipart Uploads incompletos

Verificar se existe uma regra habilitada com escopo global que
interrompa Multipart Uploads incompletos dentro do período de até
7 dias (`AbortIncompleteMultipartUpload.DaysAfterInitiation <= 7`).

O Amazon S3 não permite combinar `AbortIncompleteMultipartUpload` com
filtros de tag ou de tamanho; portanto, o escopo global exige `Filter`
ausente, vazio ou com `Prefix` vazio. Uma regra restrita por prefixo
não satisfaz este critério.

---

### NC-06 — Ausência de expiração de Delete Markers

Quando o versionamento estiver diferente de `Disabled`, verificar se
existe configuração para tratar Delete Markers expirados.

---

### NC-07 — Expiração superior ao limite definido

Verificar se alguma regra possui período de expiração superior a
3650 dias.

A verificação deve considerar tanto versões atuais quanto versões
não atuais quando aplicável.

---

### NC-08 — Retenção excessiva de versões não atuais

Verificar se alguma regra mantém versões não atuais por período
superior ao limite definido de 30 dias.

---

### NC-09 — Transição de objetos menores que 128 KB

Verificar se regras de transição permitem que objetos menores que
128 KB (131072 bytes) sejam submetidos à transição.

A análise deve considerar os filtros de tamanho presentes na regra e o
comportamento padrão de tamanho mínimo da configuração
(`TransitionDefaultMinimumObjectSize`):

| Valor                      | Comportamento do Amazon S3                                                                               |
| -------------------------- | -------------------------------------------------------------------------------------------------------- |
| `all_storage_classes_128K` | Objetos menores que 128 KB não transicionam para nenhuma classe.                                         |
| `varies_by_storage_class`  | Objetos menores que 128 KB transicionam para `GLACIER` e `DEEP_ARCHIVE`; as demais classes os bloqueiam. |
| Campo ausente              | Considerar `all_storage_classes_128K`.                                                                   |

Filtros customizados de tamanho sempre têm precedência sobre o
comportamento padrão. O critério é disparado quando:

- a regra possui `ObjectSizeLessThan` sem `ObjectSizeGreaterThan`, ou
  `ObjectSizeGreaterThan` menor que 131072; ou
- a regra não possui filtro de tamanho, a configuração usa
  `varies_by_storage_class` e a transição é para `GLACIER` ou
  `DEEP_ARCHIVE`.

Uma transição sem filtro de tamanho sob `all_storage_classes_128K` (ou
com o campo ausente) não dispara este critério.

---

### NC-10 — Transições concorrentes

Verificar se duas ou mais regras distintas de transição habilitadas
possuem filtros com escopos sobrepostos e pelo menos um valor de
`Transition.Days` igual entre as regras. A concorrência ocorre quando
as mesmas instâncias de objeto podem estar sujeitas a transições de
regras diferentes no mesmo dia.

Transições sequenciais configuradas para dias diferentes podem ser
válidas e não devem ser classificadas como concorrentes apenas por
existirem na mesma configuração.

---

### NC-11 — Transição e expiração no mesmo período

Verificar se objetos que possuem escopo sobreposto estão sujeitos a
uma transição e a uma expiração no mesmo dia.

---

### NC-12 — Duração mínima incompatível

Verificar se uma transição para determinada classe de armazenamento
é seguida por uma expiração ou nova transição antes do cumprimento
da duração mínima associada à classe.

O cálculo deve considerar o intervalo entre a transição e a próxima
ação aplicável ao objeto, ou seja, a menor data posterior à transição
entre as expirações e transições da mesma regra ou de outras regras
habilitadas com escopo sobreposto.

---

### NC-13 — Permanência em STANDARD antes de Intelligent-Tiering

Verificar se uma regra mantém objetos na classe `STANDARD` antes da
transição para `INTELLIGENT_TIERING`, ou seja, se existe transição para
`INTELLIGENT_TIERING` com `Days > 0`.

Uma transição para `INTELLIGENT_TIERING` no dia 0 deve ser considerada
a referência para essa análise.

---

### NC-14 — Transição para Intelligent-Tiering de objetos de vida curta

Dispara quando uma transição para `INTELLIGENT_TIERING` atinge objetos
que expiram menos de 30 dias depois
(`0 < Expiration.Days - Transition.Days < 30`), pois o IT só gera
economia após 30 dias sem acesso.

Não dispara se a transição for necessária para cobrir, conforme a
NC-02, uma expiração acima de 180 dias que inclua esses objetos.

---

## 5. Regras de interpretação

### 5.1 Status das regras

Somente regras de Lifecycle habilitadas devem ser consideradas na
avaliação. Regras com `Status` igual a `Disabled` devem ser ignoradas
em todos os critérios. Para NC-01, a condição ocorre quando não existe
nenhuma regra habilitada, inclusive quando a lista contém apenas regras
desabilitadas.

### 5.2 Filtros

A existência de um filtro deve ser considerada durante a determinação
do escopo de uma regra.

Quando um critério exigir uma regra de escopo global, uma regra
restrita por prefixo, tag ou outro filtro não deve ser considerada
equivalente.

Uma regra tem escopo global quando `Filter` está ausente, vazio ou
contém apenas `Prefix` vazio.

Na NC-02, a exigência não é de escopo global, e sim de cobertura do
escopo de cada expiração, conforme definido no próprio critério.

### 5.3 Versionamento

As regras relacionadas a versões não atuais e Delete Markers devem
ser avaliadas de acordo com o estado de versionamento informado.

Quando o versionamento estiver `Disabled`, essas condições não devem
ser aplicadas.

### 5.4 Múltiplas regras

A análise deve considerar todas as regras presentes na configuração.

Um mesmo cenário pode apresentar múltiplas inconformidades.

### 5.5 Sobreposição

Quando duas regras puderem atingir o mesmo conjunto de objetos, a
análise deve considerar essa sobreposição ao avaliar conflitos,
transições e expirações.

### 5.6 Conformidade

Uma configuração deve ser considerada conforme quando nenhuma das
condições de inconformidade definidas neste documento for identificada.

### 5.7 Prioridade e resolução de conflitos

Quando múltiplos cenários forem identificados simultaneamente, aplicar
as seguintes prioridades:

1. **NC-01** substitui todos os demais cenários; quando não houver
   regras habilitadas, recomendar a baseline completa.
2. **NC-11** tem precedência sobre NC-12. Se a mesma transição já foi
   identificada como ocorrendo no dia da expiração, não contabilizar
   novamente o conflito de duração mínima para essa mesma transição.
3. **NC-10** deve ser avaliada após NC-11 e somente sobre transições que
   não estejam envolvidas em conflito de mesmo dia com expiração.
4. **NC-11** tem precedência sobre NC-14. Transição e expiração no mesmo
   dia são classificadas somente como NC-11.

### 5.8 Correção possível

Uma condição só deve ser classificada como inconformidade quando
existir um ajuste nas regras de Lifecycle que a elimine sem disparar
outro critério. A única situação sem correção possível prevista nesta
base é a exceção definida na NC-14. Não aplique esta regra a outros
critérios por interpretação própria.

---

## 6. Estrutura de entrada

A configuração analisada deve seguir o formato utilizado pela API
do Amazon S3.

Exemplo:

```json
{
  "TransitionDefaultMinimumObjectSize": "all_storage_classes_128K",
  "Rules": [
    {
      "ID": "regra-01",
      "Status": "Enabled",
      "Filter": {},
      "Transitions": [],
      "Expiration": {},
      "NoncurrentVersionExpiration": {},
      "AbortIncompleteMultipartUpload": {}
    }
  ]
}
```

Além da configuração de Lifecycle, a análise pode receber informações
de contexto do bucket, como:

- nome do bucket;
- estado do versionamento;
- `TransitionDefaultMinimumObjectSize`, retornado pelo
  `GetBucketLifecycleConfiguration` (quando ausente, considerar
  `all_storage_classes_128K`);
- demais informações necessárias para interpretar as regras.

---

## 7. Estrutura de saída

A análise deve identificar:

- conformidade ou não conformidade;
- códigos das regras identificadas;
- descrição objetiva da condição encontrada;
- justificativa;
- direcionamento recomendado, quando aplicável.

A estrutura exata da saída será definida pelo processo de benchmark.

---

## 8. Limites da análise

A análise deve considerar somente os critérios definidos neste
documento.

Não devem ser criadas novas regras de inconformidade durante a
avaliação principal.

Caso seja identificada uma possível situação não contemplada nesta
base de conhecimento, ela poderá ser registrada separadamente como
"possível inconformidade adicional", sem ser contabilizada como acerto
ou erro na avaliação das regras previamente definidas.
