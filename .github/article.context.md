# Contexto do Projeto — Artigo Acadêmico sobre IA e Armazenamento em Objetos

## 1. Identificação do projeto

**Tema atual do artigo:** Inteligência Artificial como mecanismo para otimizar estratégia de armazenamento em objetos.

**Título atual em português:**
> INTELIGÊNCIA ARTIFICIAL COMO MECANISMO PARA OTIMIZAR ESTRATÉGIA DE ARMAZENAMENTO EM OBJETOS

**Título atual em inglês:**
> ARTIFICIAL INTELLIGENCE AS A MECHANISM FOR OPTIMIZING OBJECT STORAGE STRATEGIES

**Autores:**
- Gustavo Rezende Paz
- Marcia Narumi Shiraishi Kondo

**Área:** Tecnologia da Informação / Sistemas de Informação / Computação em Nuvem / Armazenamento / Inteligência Artificial.

---

## 2. Diretrizes de escrita acadêmica

As respostas e textos produzidos para este projeto devem seguir estas orientações:

- Linguagem acadêmica, clara e acessível.
- Evitar textos excessivamente longos.
- Preferir parágrafos curtos e objetivos.
- Evitar repetições.
- Manter coerência entre teoria e aplicação prática.
- Não escrever de forma genérica ou excessivamente padronizada.
- Priorizar clareza em vez de complexidade desnecessária.
- Sempre que um conceito, método, tecnologia ou afirmação não for de autoria dos pesquisadores, utilizar referência adequada no texto.
- Priorizar referências acadêmicas reais e, quando pertinente, fontes primárias.
- Não inventar autores, artigos, livros, resultados ou referências.
- Quando houver uma referência principal indicada pelo projeto, priorizá-la na fundamentação.
- Em introdução, desenvolvimento e conclusão, conectar teoria com a aplicação prática do trabalho.
- Para slides, utilizar apenas palavras-chave e conteúdos curtos, pensando na explicação oral.

---

## 3. Palavras-chave

**Português:**
- Armazenamento em objetos
- Aprendizado de máquina
- Redução de custos

**Inglês:**
- Object storage
- Machine learning
- Cost reduction

> Observação: embora o artigo tenha inicialmente considerado aprendizado supervisionado e classificação de objetos, o escopo foi posteriormente alterado para comparar uma abordagem determinística com uma abordagem baseada em LLM. A terminologia das palavras-chave ainda pode ser revisada para refletir o escopo final do experimento.

---

## 4. Evolução do problema de pesquisa

### Escopo inicial

O trabalho começou com a ideia de utilizar aprendizado supervisionado para classificar objetos em perfis de acesso (quente, morno e frio) e recomendar classes de armazenamento do Amazon S3.

A metodologia inicial previa:
- dataset sintético;
- Random Forest e XGBoost;
- classificação quente/morno/frio;
- recomendação de storage class;
- análise de small files;
- simulação financeira.

### Crítica recebida do professor

O professor apontou que o uso de machine learning para indicar classes de armazenamento poderia ser resolvido por scripts, pois muitas regras são claras e determinísticas. Também destacou que, em buckets com milhões de objetos, falsos positivos, custo computacional e consumo de recursos poderiam não apresentar um trade-off válido.

A crítica também se aplicava ao problema de small files, pois suas regras de identificação podem ser implementadas diretamente em scripts.

### Escopo atual

O trabalho foi reformulado para investigar **quando uma abordagem baseada em inteligência artificial pode complementar uma abordagem determinística na análise de políticas de ciclo de vida do Amazon S3**.

O problema central passou a ser a **complexidade crescente da manutenção de regras determinísticas**, especialmente quando é necessário considerar múltiplos critérios, exceções, recomendações e contexto operacional.

A ideia não é afirmar que IA é sempre melhor que scripts. A proposta é comparar as abordagens e identificar em quais situações a IA pode agregar valor.

---

## 5. Problema atual do trabalho

Muitas organizações administram grandes volumes de dados em armazenamento em objetos e precisam definir e validar políticas de ciclo de vida para controlar retenção, transição entre classes e custos.

Abordagens determinísticas podem validar regras por meio de estruturas condicionais, mas a complexidade aumenta conforme surgem:
- novos critérios;
- exceções;
- combinações entre regras;
- recomendações específicas;
- requisitos de negócio e operação.

A hipótese é que um modelo de linguagem de grande porte, apoiado por conhecimento específico do domínio, possa interpretar configurações de forma contextualizada, identificar inconsistências e produzir recomendações sem exigir que cada nova condição seja transformada manualmente em uma nova sequência de regras no código.

O trabalho, portanto, investiga o equilíbrio entre previsibilidade e simplicidade das regras determinísticas e a capacidade de interpretação e adaptação de uma abordagem baseada em LLM.

---

## 6. Objetivo atual

**Objetivo geral atual:**

> Analisar o uso de técnicas de inteligência artificial como apoio à avaliação e otimização de políticas de ciclo de vida em armazenamento em objetos, comparando-as com abordagens determinísticas tradicionais.

A pesquisa deve avaliar:
- capacidade de identificar inconsistências;
- aderência às boas práticas documentadas;
- adaptabilidade a novos contextos;
- esforço de manutenção;
- transparência das decisões;
- potencial de aplicação em ambientes corporativos.

---

## 7. Conceitos essenciais para a introdução

### Armazenamento de dados

A introdução apresenta o armazenamento como uma questão que envolve não apenas guardar dados, mas compreender como eles são utilizados ao longo do tempo.

### Três modelos principais

São apresentados três modelos de armazenamento:
- armazenamento em bloco;
- armazenamento em arquivos;
- armazenamento em objeto.

A justificativa é que diferentes aplicações possuem diferentes necessidades de acesso e organização dos dados.

### Hardware físico

Independentemente de o dado estar em ambiente local (*on-premise*) ou na nuvem, a informação é, em última instância, armazenada fisicamente em hardware, como:
- HDD (*Hard Disk Drive*);
- SSD (*Solid State Drive*).

O que varia é a forma como os dados são organizados e acessados pelos sistemas.

### Protocolos e interfaces

Na introdução são citados exemplos de mecanismos/protocolos:
- bloco: iSCSI (*Internet Small Computer System Interface*) e FC (*Fibre Channel*);
- arquivos: NFS (*Network File System*) e SMB (*Server Message Block*);
- objetos: interfaces compatíveis com a S3 API.

### Armazenamento em objetos

A introdução atribui a origem acadêmica do conceito a pesquisas conduzidas na Carnegie Mellon University, especialmente ao trabalho de Gibson et al. (1996), ligado ao projeto NASD.

### Políticas de ciclo de vida e tierização

O trabalho precisa explicar que políticas de ciclo de vida automatizam o gerenciamento dos dados ao longo do tempo, incluindo ações como:
- exclusão automática;
- movimentação entre classes de armazenamento.

A movimentação entre classes é tratada como *tierização*.

No Amazon S3, a ideia é relacionar frequência de acesso e classe de armazenamento, buscando equilibrar desempenho e custo.

### Inteligência artificial e LLMs

O escopo atual não é mais focado em machine learning supervisionado tradicional. O foco da implementação é o uso de um **modelo de linguagem de grande porte (LLM)**.

A introdução deve explicar brevemente o que é um LLM e por que ele é relevante para tarefas que exigem interpretação de contexto, análise de configurações e geração de recomendações.

---

## 8. Introdução — estrutura lógica desejada

A introdução atual segue, em essência, esta ordem:

1. Crescimento do volume de dados e necessidade de estratégias eficientes.
2. Diferentes modelos de armazenamento e seus diferentes usos.
3. Armazenamento físico em hardware, mesmo na nuvem.
4. Protocolos/mecanismos de acesso de cada modelo.
5. Origem acadêmica do armazenamento em objetos.
6. Políticas de ciclo de vida e tierização.
7. Inteligência artificial e LLMs.
8. Problema da complexidade das regras determinísticas.
9. Justificativa para investigar IA como abordagem complementar.
10. Objetivo do trabalho.

O final da introdução deve evitar redundância entre “este trabalho investiga” e “este trabalho tem como objetivo”. O objetivo deve aparecer de forma clara e formal no último parágrafo.

---

## 9. Justificativa para uso de IA

A justificativa atual do projeto é:

> Enquanto abordagens determinísticas exigem atualização explícita do código para incorporar novas regras e exceções, sistemas apoiados por inteligência artificial e bases de conhecimento especializadas apresentam potencial para interpretar configurações de forma contextualizada, reduzindo o esforço de manutenção e ampliando a capacidade adaptativa da solução.

Essa justificativa deve ser apresentada com cautela. O trabalho **não deve afirmar que regras determinísticas são ineficientes por definição**. Elas continuam adequadas para situações simples e previsíveis.

O ponto central é que a manutenção pode se tornar complexa quando aumenta o número de critérios, exceções e relações contextuais.

---

## 10. Experimento atual

O experimento atual **não utiliza MCP nem RAG**.

A implementação realizada consiste em duas abordagens:

### Abordagem A — script determinístico

Foi utilizado um prompt para auxiliar na geração de um script de análise.

O script produzido contém regras determinísticas, principalmente estruturas condicionais, para verificar as políticas de ciclo de vida conforme os critérios estabelecidos.

É importante diferenciar:
- a IA generativa foi usada como **ferramenta de desenvolvimento do script**;
- depois de gerado, o script executa as regras de forma determinística.

O trabalho não deve chamar essa abordagem de “script determinístico de GenAI”. A expressão preferida é:

> **script baseado em regras determinísticas, desenvolvido com auxílio de inteligência artificial generativa.**

### Abordagem B — LLM

Foi utilizado um modelo de linguagem da família Claude, via Amazon Bedrock, para avaliar os mesmos cenários.

O mesmo conjunto de instruções utilizado para orientar a geração do script também serviu de base para o contexto fornecido ao modelo.

O modelo foi instruído a:
- analisar as configurações;
- identificar inconsistências;
- verificar aderência às regras/boas práticas fornecidas;
- produzir recomendações fundamentadas.

### Equivalência do experimento

Os mesmos cenários e critérios devem ser usados nas duas abordagens para reduzir diferenças causadas pela formulação do problema.

O fato observado até o momento é que **ambas as abordagens produziram a mesma saída solicitada no prompt** nos cenários avaliados. Isso é um resultado do experimento e deve ser tratado como tal, sem concluir antecipadamente que uma abordagem é superior.

---

## 11. Cenários do experimento

Foram definidos **20 cenários de configuração**.

Os cenários incluem:
- situações aderentes às boas práticas;
- inconsistências intencionais;
- transições inadequadas entre classes;
- períodos de retenção incompatíveis;
- regras redundantes;
- regras conflitantes;
- situações com diferentes níveis de complexidade.

O experimento deve registrar, para cada cenário:
- inconsistência esperada;
- resultado do script;
- resultado do LLM;
- recomendação produzida;
- aderência à regra de referência;
- observações relevantes.

---

## 12. Critérios de comparação

A comparação atual considera:

### Critérios quantitativos possíveis
- quantidade de inconsistências identificadas corretamente;
- percentual de cenários avaliados corretamente;
- taxa de concordância entre as abordagens;
- tempo de execução/análise, caso seja medido;
- quantidade de alterações necessárias quando novas regras são introduzidas.

### Critérios qualitativos
- qualidade das recomendações;
- aderência às boas práticas documentadas;
- adaptabilidade a novos contextos;
- transparência das decisões;
- esforço de manutenção;
- utilidade prática em ambientes corporativos.

### Critério de aderência

Considera-se aderente a recomendação que estiver de acordo com as boas práticas e critérios previamente documentados na base de referência construída para o experimento.

---

## 13. Tipo de pesquisa

A classificação metodológica atualmente considerada mais adequada é:

> **Pesquisa aplicada, de caráter experimental e abordagem quali-quantitativa.**

Justificativa:
- **Aplicada:** busca investigar uma solução para um problema concreto de análise e governança de armazenamento em nuvem.
- **Experimental:** as duas abordagens são submetidas aos mesmos cenários sob condições definidas e comparáveis.
- **Quanti-qualitativa:** combina medidas objetivas de desempenho/concordância com análise qualitativa das recomendações, adaptabilidade e manutenção.

---

## 14. Metodologia — estrutura atual

### Etapa 1 — Revisão bibliográfica

Levantamento de literatura científica e técnica sobre:
- armazenamento em objetos;
- gerenciamento do ciclo de vida;
- classes de armazenamento em nuvem;
- políticas de retenção;
- inteligência artificial;
- LLMs;
- análise/otimização de custos.

Também são analisadas soluções comerciais do Amazon S3.

### Etapa 2 — Construção dos cenários

Construção dos 20 cenários representativos de ambientes corporativos, incluindo cenários corretos e cenários com inconsistências intencionais.

### Etapa 3 — Implementação das abordagens

Implementação de:
1. script determinístico desenvolvido com auxílio de IA generativa;
2. abordagem baseada em LLM, usando Claude e as mesmas instruções/contextos do experimento.

Não utilizar MCP ou RAG na descrição da metodologia, pois eles não fizeram parte do experimento efetivamente executado.

### Etapa 4 — Execução dos experimentos

Aplicação das duas abordagens aos mesmos 20 cenários e registro dos resultados.

### Etapa 5 — Análise comparativa

Comparação dos resultados segundo critérios quantitativos e qualitativos, com foco em identificar em quais situações a IA pode complementar a abordagem determinística.

---

## 15. Referências atuais e função de cada uma

### ANTHROPIC — Model Context Protocol Specification (2025)

Função original: fundamentar MCP.

**Status atual:** não deve ser usada como referência metodológica se MCP não estiver presente no experimento. Pode ser removida do conjunto final caso também não seja mencionada em outras seções.

### ANTHROPIC — Claude Documentation (2025)

Função: documentar a tecnologia/modelo Claude utilizada no experimento.

### AWS — Amazon S3 Storage Classes (2026)

Função: fonte técnica oficial para classes de armazenamento e aspectos do Amazon S3.

### GIBSON et al. (1996)

Função: fonte primária para a origem acadêmica do armazenamento baseado em objetos.

### GIL (2008)

Função: fundamentar a classificação metodológica da pesquisa.

### IBM Think (2025)

Função: apoio introdutório para explicar diferenças entre armazenamento em bloco, arquivo e objeto.

### KHAN et al. (2024)

Função: referência principal do artigo sobre otimização de armazenamento e classificação de objetos/camadas.

**Referência principal indicada originalmente pelo projeto:**
> KHAN, Akif Quddus et al. Cloud storage tier optimization through storage object classification. *Computing*, v. 106, n. 11, p. 3389–3418, 2024.

### LIU; PAN; LIU (2023)

Função: survey acadêmica sobre otimização de custos em armazenamento em nuvem. Deve ser utilizada para justificar a importância de estratégias de tierização, políticas de retenção e otimização de custos.

### MISHRA (2021)

Função: referência sobre mecanismos de armazenamento em objetos e grandes volumes de dados.

### ZHAO et al. (2026)

Função: fundamentação acadêmica para o conceito de modelos de linguagem de grande porte (LLMs).

Referência identificada:
> ZHAO, Wayne Xin et al. A survey of large language models. *Frontiers of Computer Science*, v. 20, n. 12, p. 2012627, 2026.

### SAMUEL (1967)

Função original: origem histórica do termo machine learning.

**Status atual:** pode deixar de ser necessária, pois o experimento atual não é baseado em aprendizado supervisionado tradicional. Só deve permanecer se o conceito de machine learning continuar sendo tratado de forma relevante no artigo.

---

## 16. Referências primárias mais relevantes

Entre as referências atuais, as fontes consideradas primárias ou oficiais para os respectivos assuntos são:

- Gibson et al. (1996) — conceito/origem acadêmica do armazenamento baseado em objetos.
- AWS (2026) — documentação oficial do Amazon S3.
- Anthropic — documentação oficial do Claude.
- Zhao et al. (2026) — artigo acadêmico de referência sobre LLMs, embora seja uma survey e não fonte primária do conceito.
- Khan et al. (2024) — estudo científico diretamente relacionado à classificação de objetos e otimização de armazenamento.

Liu, Pan e Liu (2023) é uma survey e deve ser tratado como fonte secundária.

Gil (2008) é uma referência metodológica.

IBM Think é fonte técnica institucional, não artigo científico.

---

## 17. Pontos que NÃO devem ser afirmados sem evidência experimental

Evitar afirmar como fato que:
- IA é mais eficiente que scripts;
- LLM reduz custos diretamente;
- LLM elimina a necessidade de regras;
- LLM sempre consegue interpretar corretamente as políticas;
- a abordagem de IA é mais barata computacionalmente;
- a IA é mais escalável para milhões de objetos;
- houve redução real de custos financeiros, caso isso não tenha sido efetivamente medido.

O artigo deve distinguir claramente entre:
- hipótese;
- resultado observado;
- interpretação dos autores;
- possibilidade futura.

---

## 18. Pergunta central sugerida para orientar o restante do artigo

> **Em quais condições uma abordagem baseada em modelo de linguagem de grande porte pode complementar uma solução determinística na análise de políticas de ciclo de vida do Amazon S3?**

Essa pergunta está mais alinhada ao experimento atual do que uma pergunta genérica sobre “usar IA para otimizar armazenamento”.

---

## 19. Próximos passos do projeto

1. Confirmar exatamente qual versão/modelo do Claude foi utilizada no experimento e registrar essa informação de forma reprodutível.
2. Registrar os 20 cenários e seus resultados esperados.
3. Executar os 20 cenários nas duas abordagens.
4. Criar uma tabela de comparação por cenário.
5. Definir critérios objetivos para “recomendação correta”.
6. Medir, quando possível, tempo de execução, quantidade de regras e esforço de manutenção.
7. Analisar casos em que as abordagens divergem.
8. Escrever a seção de resultados com base nos dados reais do experimento.
9. Revisar resumo, introdução e palavras-chave para garantir que reflitam o escopo final.
10. Revisar referências e manter apenas aquelas efetivamente utilizadas no texto.

---

## 20. Regra geral para futuras alterações

Qualquer mudança no experimento deve ser refletida de forma consistente em:

- título;
- resumo;
- abstract;
- palavras-chave;
- introdução;
- objetivo;
- metodologia;
- resultados;
- conclusão;
- referências.

Não reintroduzir conceitos ou ferramentas abandonados (por exemplo, MCP, RAG, Random Forest, XGBoost ou dataset sintético para classificação) sem que tenham sido efetivamente utilizados na versão final do experimento.
