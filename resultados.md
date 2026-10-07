# Diagnóstico do Benchmark: Script Determinístico vs. GenAI

## 1. Objetivo e método

O benchmark compara duas abordagens para identificar desperdício financeiro em regras de Lifecycle do Amazon S3, ambas orientadas pela mesma base de conhecimento (`knowledge_base.md`, critérios NC-01 a NC-14):

- **Script determinístico**: código Python gerado pelo modelo a partir da base e executado sem edições manuais.
- **GenAI**: Claude Opus 4.5 (Amazon Bedrock) avaliando cada bucket diretamente, com saída estruturada e validação de schema.

Os resultados foram confrontados com um gabarito de 34 cenários (16 conformes e 18 não conformes, totalizando 19 inconformidades esperadas). Considera-se acerto exato quando o conjunto de NCs reportado é idêntico ao esperado.

## 2. Resultados

| Métrica                               | Script            | GenAI                                 |
| ------------------------------------- | ----------------- | ------------------------------------- |
| Acerto exato                          | **32/34 (94,1%)** | 21/34 (61,8%)                         |
| Classificação conforme / não conforme | **32/34 (94,1%)** | 25/34 (73,5%)                         |
| Precisão                              | **100%**          | 57,1%                                 |
| Recall                                | **89,5%**         | 63,2%                                 |
| Falsos positivos                      | **0**             | 9                                     |
| Falsos negativos                      | **2**             | 7                                     |
| Tempo por bucket                      | milissegundos     | 3,5 a 13 s                            |
| Custo marginal por execução           | nulo              | ~5,2 mil tokens de entrada por bucket |

### Cenários com divergência em relação ao gabarito

| Caso    | Esperado | Script           | GenAI            |
| ------- | -------- | ---------------- | ---------------- |
| CASE_04 | NC-02    | ✓                | – (não detectou) |
| CASE_06 | NC-03    | ✓                | NC-02            |
| CASE_09 | conforme | ✓                | NC-02            |
| CASE_12 | NC-06    | – (não detectou) | NC-06 + NC-12    |
| CASE_13 | conforme | ✓                | NC-02            |
| CASE_16 | NC-09    | ✓                | NC-02            |
| CASE_17 | conforme | ✓                | NC-12            |
| CASE_21 | conforme | ✓                | NC-12            |
| CASE_22 | NC-12    | ✓                | – (não detectou) |
| CASE_26 | conforme | ✓                | NC-02            |
| CASE_27 | NC-08    | ✓                | NC-02            |
| CASE_29 | NC-03    | ✓                | – (não detectou) |
| CASE_32 | NC-14    | – (não detectou) | – (não detectou) |

## 3. Análise

**Script determinístico.** Os dois erros têm origem identificável e são reproduzíveis. No CASE_12, o script interpretou que uma expiração global de versões não atuais equivale a tratar Delete Markers, lacuna decorrente da redação genérica da NC-06 na base. No CASE_32, a verificação da NC-14 limitou-se a transição e expiração na mesma regra, sem cruzar regras com escopo sobreposto. Em ambos os casos o erro é sistemático: uma vez identificado, é corrigível de forma definitiva e não varia entre execuções.

**GenAI.** Os erros concentram-se em três padrões:

1. **Desvio de regra explícita (NC-02).** Em 7 dos 13 cenários com erro, o modelo considerou que um filtro `ObjectSizeGreaterThan: 131072` não cobre o escopo global, embora a base estabeleça essa equivalência textualmente. Em alguns casos a justificativa cita a regra correta e conclui em sentido oposto. Nos casos 06, 16 e 27, esse equívoco ainda substituiu a inconformidade correta.
2. **Incoerência entre decisão e justificativa (NC-12).** Nos casos 12 e 17, o modelo registrou NC-12, mas a própria justificativa conclui que não há violação. No CASE_21, combinou critérios não previstos na base (transição de versões atuais com expiração de versões não atuais).
3. **Omissões em casos simples.** Os casos 04 e 29 apresentam violações diretas (expiração de 365 dias sem transição; ausência de expiração global) e foram classificados como conformes, com respostas mínimas e sem raciocínio explícito.

Esses padrões indicam que o modelo não aplica a base de forma consistente: ora é mais restritivo que a regra, ora mais permissivo, e a decisão nem sempre é sustentada pela justificativa que ele mesmo produz.

## 4. Limitações

- Uma única execução do modelo foi avaliada; não se mediu a variância entre execuções, ainda que observações anteriores indiquem respostas diferentes para entradas idênticas mesmo com `temperature = 0`.
- O gabarito foi elaborado pela equipe e reflete uma interpretação da base; algumas divergências (como NC-06) derivam de redação ambígua, não necessariamente de erro da abordagem.
- O script foi gerado pelo próprio modelo, de modo que sua qualidade também depende de GenAI, embora a etapa de execução seja determinística.

## 5. Conclusão

Para a verificação de conformidade de regras de Lifecycle, um problema de regras bem definidas e verificáveis, a abordagem determinística foi superior em todas as dimensões medidas: acurácia (94,1% vs. 61,8%), precisão (100% vs. 57,1%), reprodutibilidade, custo e tempo. Seus erros são pontuais, explicáveis e corrigíveis de forma permanente.

A avaliação direta por GenAI mostrou-se inadequada como mecanismo principal de auditoria: produz falsos positivos frequentes, contradições internas e omissões em casos triviais. Seu valor está em etapas complementares, como a geração do próprio script a partir da base e a identificação de ambiguidades na especificação, e não na classificação final.

A recomendação é adotar o script determinístico como mecanismo de avaliação, mantendo o GenAI como apoio no desenvolvimento e na revisão da base de conhecimento.
