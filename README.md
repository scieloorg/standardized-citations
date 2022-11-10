# standardized-citations (repositório descontinuado em favor de https://github.com/scieloorg/cited-references)

Este repositório concentra métodos utilizados para normalizar referências citadas nos documentos SciELO. O processo de normalização consiste em duas etapas, a saber:

1. Limpar referências citadas
2. Enriquecê-las com dados coletados em bases externas (CrossRef e bases ad hoc)


## Instalação
`docker build --tag standardized-citations:0.1 .`

__Insumos__
- Arquivo binário contendo bases de correção de periódicos (`bc-v1.bin`)

## Como Usar

1. Normalizar referências citadas em PIDs publicados de 2021-02-01 a 2021-02-07 usando métodos exato e aproximado e persistindo em JSON:

`docker run --rm -v {HOST_DIR_DATA}:/opt/data standardized-citations:0.1 normalize -f 2021-02-01 -u 2021-02-07 -x -z -d /opt/data/bc-v1.bin`

2. Coletar metadados Crossref para referências citadas em PIDs publicados entre 2021-02-01 e 2021-02-07:

`docker run --rm -v {HOST_DIR_DATA}:/opt/data standardized-citations:0.1 crossref -f 2021-02-01 -u 2021-02-07`

__Notas__
- É preciso ter um e-mail registrado no serviço Crossref
- Os resultados, por padrão, são persistidos em arquivos JSON no diretório DIR_DATA
- É possível persistir os resultados em um banco de dados MongoDB (ao informar uma string de conexão)



## Parâmetros do standardizer

| Parâmetro | Nome | Descrição |
|-----------|------|-----------|
|-z|--fuzzy|Ativa casamento aproximado de títulos de periódicos|
|-x|--fuzzy|Ativa casamento exato de títulos de periódicos|
||--mongo_uri|String de conexão com banco de dados MongoDB|
|-d|--database|Arquivo binário da base de correção de títulos|
|-f|--from_date|Data a partir da qual os PIDs serão coletados no ArticleMeta e suas referências citadas serão normalizadas|
|-u|--until_date|Data até a qual os PIDs serão coletados no ArticleMeta e suas referências citadas serão normalizadas|


## Parâmetros do CrossrefAsyncCollector

| Parâmetro | Nome | Descrição |
|-----------|------|-----------|
||--mongo_uri|String de conexão com banco de dados MongoDB|
|-e|--email|E-mail registrado no serviço Crossref|
|-f|--from_date|Data a partir da qual os PIDs serão coletados no ArticleMeta|
|-u|--until_date|Data até a qual os PIDs serão coletados no ArticleMeta|


## Referências

- [Normalização de citações](https://docs.google.com/document/d/1iwkt0Nr6P9Or2_RQbIbyA_rEiLkXIo-Yws2vw3gfDes/edit?usp=sharing)
