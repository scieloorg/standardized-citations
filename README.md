# standardized-citations

Este repositório concentra métodos utilizados para normalizar referências citadas nos documentos SciELO. O processo de normalização consiste em duas etapas, a saber:

1. Limpar referências citadas
2. Enriquecê-las com dados coletados em bases externas (CrossRef e bases ad hoc)


## Como Usar

1. Normalizar referências citadas em PIDs publicados a partir de 2020-05-01, da coleção Uruguai, usando métodos exato e aproximado e persistindo em JSON:

    `python main.py -f 2020-05-01 -c ury -x -z`

  
2. Normalizar referências citadas em PIDs publicados a partir de 2020-05-01 usando métodos exato e fuzzy e persistindo em MongoDB:
    
    `python main.py -f 2020-05-01 -x -z -a {MONGO-ADDRESS} -m {MONGO-DATABASE} -l {MONGO-COLLECTION}`

    _Caso não sejam informados -m e -l, é considerado por padrão a base de dados "citations" e a coleção 'standardized'_
  
    
3. Coletar metadados Crossref para referências citadas em PIDs publicados a partir de 2020-05-01:

    `python crossref.py -f 2020-05-01 -a {MONGO-ADDRESS} -m {MONGO-DATABASE} -l {MONGO-COLLECTION} -e {E-MAIL}`
    
    __É preciso ter um e-mail registrado no serviço Crossref__



## Parâmetros do standardizer

| Parâmetro | Nome | Descrição |
|-----------|------|-----------|
|-z|--fuzzy|Ativa casamento aproximado de títulos de periódicos|
|-x|--fuzzy|Ativa casamento exato de títulos de periódicos|
|-a|--mongo_host|Endereço da base de dados em MongoDB|
|-m|--mongo_database|Nome da base de dados MongoDB|
|-l|--mongo_collection|Nome da coleção da base de dados MongoDB|
|-d|--database|Arquivo binário da base de correção de títulos|
|-f|--from_date|Data a partir da qual os PIDs serão coletados no ArticleMeta e suas referências citadas serão normalizadas|
|-u|--until_date|Data até a qual os PIDs serão coletados no ArticleMeta e suas referências citadas serão normalizadas|


## Parâmetros do CrossrefAsyncCollector

| Parâmetro | Nome | Descrição |
|-----------|------|-----------|
|-a|--mongo_host|Endereço da base de dados em MongoDB|
|-m|--mongo_database|Nome da base de dados MongoDB|
|-l|--mongo_collection|Nome da coleção da base de dados MongoDB|
|-e|--email|E-mail registrado no serviço Crossref|
|-f|--from_date|Data a partir da qual os PIDs serão coletados no ArticleMeta|
|-u|--until_date|Data até a qual os PIDs serão coletados no ArticleMeta|


## Referências

- [Normalização de citações](https://docs.google.com/document/d/1iwkt0Nr6P9Or2_RQbIbyA_rEiLkXIo-Yws2vw3gfDes/edit?usp=sharing)
