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

### NC-02 — Ausência de transições com expiração superior a 180 dias

Verificar se existem regras de expiração superiores a 180 dias sem
que exista pelo menos uma regra de transição.

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

Verificar se existe uma regra para interromper Multipart Uploads
incompletos dentro do período de até 7 dias.

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
128 KB sejam submetidos à transição.

A análise deve considerar os filtros de tamanho presentes na regra.

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
ação aplicável ao objeto.

---

### NC-13 — Permanência em STANDARD antes de Intelligent-Tiering

Verificar se uma regra mantém objetos na classe `STANDARD` por mais
de um dia antes da transição para `INTELLIGENT_TIERING`.

Uma transição para `INTELLIGENT_TIERING` no dia 0 deve ser considerada
a referência para essa análise.

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

---

## 6. Estrutura de entrada

A configuração analisada deve seguir o formato utilizado pela API
do Amazon S3.

Exemplo:

```json
{
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
