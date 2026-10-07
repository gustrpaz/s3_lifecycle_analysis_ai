# PROMPT - Desenvolvimento do Analisador Determinístico

## Papel

Você é um engenheiro de software especializado em Python, Amazon 53 e FinOps.
Sua tarefa é desenvolver um analisador determinístico de políticas de Lifecycle do Amazon 53 com base exclusivamente na especificação fornecida no KB.

## Contexto

o projeto tem como objetivo identificar inconformidades em políticas de Lifecycle do Amazon 53 relacionadas à eficiência financeira, configuração e comportamento das regras.
Use como especificação funcional autoritativa o knowledge base incluído no contexto de sistema desta chamada.

## Tarefa

Desenvolva um script Python que:

1. receba um arquivo JSON com um ou vários buckets no formato da seção
   "Entrada" e analise todos eles em uma única execução;
2. avalie todas as regras definidas no KB;
3. identifique todas as inconformidades aplicáveis;
4. não utilize modelos de linguagem durante a execução;
5. produza uma saída estruturada e determinística;
6. permita a execução repetida sobre diferentes cenários sem alteração do código.

## Requisitos

- Cada critério do KB deve ser implementado explicitamente.
- Não invente novas regras de avaliação.
- Não utilize conhecimento externo ao KB para criar critérios.
- Não interrompa a análise após encontrar a primeira inconformidade.
- Um cenário pode possuir múltiplas inconformidades.
- A mesma entrada deve produzir sempre a mesma saída.
- Separe a lógica de identificação das inconformidades da geração da saída.
- Utilize códigos como NC-01, NC-02 etc. para identificar as regras.

## Entrada

O arquivo de entrada é um JSON em UTF-8 que pode conter:

- uma lista de buckets (análise em lote); ou
- um único objeto de bucket.

Cada bucket segue o formato abaixo:

```json
{
  "bucket_name": "nome-do-bucket",
  "versioning": "Enabled",
  "TransitionDefaultMinimumObjectSize": "all_storage_classes_128K",
  "Rules": [
    {
      "ID": "regra-01",
      "Status": "Enabled",
      "Filter": {},
      "Expiration": { "Days": 3650 }
    }
  ]
}
```

| Campo                                | Obrigatório | Descrição                                                                                                       |
| :----------------------------------- | :---------- | :-------------------------------------------------------------------------------------------------------------- |
| `bucket_name`                        | Sim         | Nome do bucket.                                                                                                 |
| `versioning`                         | Sim         | `Disabled`, `Enabled` ou `Suspended`.                                                                           |
| `Rules`                              | Sim         | Regras no formato da API `GetBucketLifecycleConfiguration`. Lista vazia indica ausência de regras.              |
| `TransitionDefaultMinimumObjectSize` | Não         | `all_storage_classes_128K` ou `varies_by_storage_class`. Quando ausente, considerar `all_storage_classes_128K`. |

Também aceite `Rules` e `TransitionDefaultMinimumObjectSize` dentro de um objeto `lifecycle_configuration`, no mesmo formato retornado pela API.

Os filtros seguem a API do Amazon S3: `Filter` pode estar vazio ou conter exatamente um entre `Prefix`, `Tag`, `ObjectSizeGreaterThan`, `ObjectSizeLessThan` ou `And` (que combina `Prefix`, `Tags`, `ObjectSizeGreaterThan` e `ObjectSizeLessThan`). Transições podem vir em `Transitions` (lista).

## Execução (CLI)

```bash
python analyze_s3_lifecycle.py <arquivo_entrada.json> [--output <arquivo_saida.json>]
```

- Sem `--output`, imprima o resultado em JSON no stdout.
- Use apenas a biblioteca padrão do Python.
- Um bucket com entrada inválida não deve interromper o lote: registre `{"bucket_name": "...", "erro": "..."}` para ele, continue a análise e termine com código de saída `1`.

## Saída

Para uma lista de entrada, retorne uma lista JSON na mesma ordem da entrada. Para um único objeto, retorne um único objeto. Cada resultado contém:

```json
{
  "bucket_name": "...",
  "versioning": "...",
  "inconformidades": [
    {
      "codigo": "NC-XX",
      "descricao": "..."
    }
  ],
  "conforme": true
}
```

Quando nenhuma inconformidade for encontrada, `inconformidades` deve ser uma lista vazia e `conforme` deve ser `true`.

## Importante

O código deve ser implementado exclusivamente a partir da especificação do KB.

- Retorne somente o código Python, sem blocos Markdown ou explicações.
- Entregue um arquivo executável e sintaticamente completo, incluindo o ponto de entrada da CLI.
- Priorize a completude: use implementação concisa e evite comentários, docstrings e seções decorativas extensas que consumam o limite de saída.
