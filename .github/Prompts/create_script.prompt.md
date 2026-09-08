Me ajude a gerar um script determinístico em python que realiza a análise de regras de ciclo de vida de buckets do Amazon S3. O objetivo é avaliar se as regras existentes estão de acordo com as melhores práticas de eficiência financeira e governança de dados. Existem regras de ciclo de vida que resultam em custos adicionais ao invés de economia de custos com base na frequência de acesso.

Mapiei algumas regras incorretas que deveriam ser adequadas, por exemplo:

1. Regra de transição da classe Intelligent-Tiering seguida de uma transição para Glacier Deep Archive.
2. Regra de transição de Standard para Intelligent-Tiering seguida de regra de expiração precoce antes do IT surgir efeito.
3. Regras duplicadas conflitantes: Transição de Standard para Intelligent Tiering e regra de transição de Standard para Standard IA.
4. Regras de ciclo de vida desabilitadas (não surgem efeitos).

Entre outros cenários que foram mapeados no arquivo [prompt_analise_lifecycle_s3](./prompt_analise_lifecycle_s3.md).
