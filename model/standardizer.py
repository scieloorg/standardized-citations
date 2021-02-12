import json
import logging
import os
import pickle
import re
import time

from datetime import datetime
from pymongo import errors, MongoClient, uri_parser
from utils.string_processor import preprocess_journal_title
from xylose.scielodocument import Citation


DIR_DATA = os.environ.get('DIR_DATA', '/opt/data')
MONGO_STDCITS_COLLECTION = os.environ.get('MONGO_STDCITS_COLLECTION', 'standardized')

MIN_CHARS_LENGTH = 6
MIN_WORDS_COUNT = 2

STATUS_NOT_NORMALIZED = 0
STATUS_EXACT = 1
STATUS_EXACT_VALIDATED = 2
STATUS_EXACT_VALIDATED_LR = 3
STATUS_EXACT_VALIDATED_LR_ML1 = 4
STATUS_EXACT_VOLUME_INFERRED_VALIDATED = 5
STATUS_EXACT_VOLUME_INFERRED_VALIDATED_LR = 6
STATUS_EXACT_VOLUME_INFERRED_VALIDATED_LR_ML1 = 7
STATUS_FUZZY_VALIDATED = 8
STATUS_FUZZY_VALIDATED_LR = 9
STATUS_FUZZY_VALIDATED_LR_ML1 = 10
STATUS_FUZZY_VOLUME_INFERRED_VALIDATED = 11
STATUS_FUZZY_VOLUME_INFERRED_VALIDATED_LR = 12
STATUS_FUZZY_VOLUME_INFERRED_VALIDATED_LR_ML1 = 13

VOLUME_IS_ORIGINAL = 0
VOLUME_IS_INFERRED = 1
VOLUME_NOT_USED = -1


class Standardizer:

    logging.basicConfig(level=logging.INFO)

    def __init__(self,
                 path_db,
                 use_exact=False,
                 use_fuzzy=False,
                 mongo_uri_std_cits=None):

        self.use_exact = use_exact
        self.use_fuzzy = use_fuzzy

        if mongo_uri_std_cits:
            try:
                self.persist_mode = 'mongo'
                mongo_col = uri_parser.parse_uri(mongo_uri_std_cits).get('collection')
                if not mongo_col:
                    mongo_col = MONGO_STDCITS_COLLECTION
                self.standardizer = MongoClient(mongo_uri_std_cits).get_database().get_collection(mongo_col)

                total_docs = self.standardizer.count_documents({})
                logging.info(
                    'There are {0} documents in the collection {1}'.format(total_docs, mongo_col))
            except ConnectionError as e:
                logging.error('ConnectionError %s' % mongo_uri_std_cits)
                logging.error(e)

        else:
            self.persist_mode = 'json'
            file_name_results = 'std-results-' + str(time.time()) + '.json'
            self.path_results = os.path.join(DIR_DATA, file_name_results)

        if path_db:
            logging.info('Loading %s' % path_db)
            self.db = self.load_database(path_db)

    def add_hifen_issn(self, issn: str):
        """
        Insere hífen no ISSN.

        :param issn: ISSN sem hífen
        :return: ISSN com hífen
        """
        if issn:
            return issn[:4] + '-' + issn[4:]

    def load_database(self, path_db: str):
        """
        Carrega na memória o arquivo binário das bases de correção e validação.

        :param path_db: caminho do arquivo binário
        :return: base carregada em formato de dicionário
        """
        try:
            with open(path_db, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            logging.error('File {0} does not exist'.format(path_db))

    def extract_issnl_from_valid_match(self, valid_match: str):
        """
        Extrai ISSN-L a partir de uma chave ISSN-ANO-VOLUME.
        Caso o ISSN não exista no dicionário issn-to-issnl, considera o próprio ISSN como ISSN-L.

        :param valid_match: chave validada no formato ISSN-ANO-VOLUME
        :return: ISSN-L
        """
        issn, year, volume = valid_match.split('-')

        issnl = self.db['issn-to-issnl'].get(issn, '')

        if not issnl:
            issnl = issn

        return issnl

    def extract_issn_year_volume_keys(self, cit: Citation, issns: set):
        """
        Extrai chaves ISSN-YEAR-VOLUME para uma referência citada e lista de ISSNs.

        :param cit: referência citada
        :param issns: set de possíveis ISSNs
        :return: set de chaves ISSN-ANO-VOLUME
        """
        keys = set()

        cit_year = cit.publication_date

        if cit_year:
            if len(cit_year) > 4:
                cit_year = cit_year[:4]

            if len(cit_year) == 4 and cit_year.isdigit():
                cit_vol = cit.volume

                if cit_vol and cit_vol.isdigit():
                    for i in issns:
                        keys.add('-'.join([i, cit_year, cit_vol]))
                    return keys, VOLUME_IS_ORIGINAL
                else:
                    for i in issns:
                        cit_vol_inferred = self.infer_volume(i, cit_year)
                        if cit_vol_inferred:
                            keys.add('-'.join([i, cit_year, cit_vol_inferred]))
                    return keys, VOLUME_IS_INFERRED

        return keys, VOLUME_NOT_USED

    def get_issns(self, matched_issnls: set):
        """
        Obtém todos os ISSNs associados a um set de ISSN-Ls.

        :param matched_issnls: ISSN-Ls casados para uma dada referência citada
        :return: set de ISSNs vinculados aos ISSNL-s
        """
        possible_issns = set()

        for mi in matched_issnls:
            possible_issns = possible_issns.union(
                set(
                    [j for j in self.db['issnl-to-data'].get(mi, {}).get('issns', [])]
                )
            )

        return possible_issns

    def get_status(self, match_mode: str, mount_mode: int, db_used: str):
        """
        Obtém o status com base no modo de casamento, de volume utilizado e de base de validação utilizada.

        :param match_mode: modo de casamento ['exact', 'fuzzy']
        :param mount_mode: modo de obtenção da chave de validação ['VOLUME_IS_ORIGINAL', VOLUME_IS_INFERRED']
        :param db_used: base de validação utilizada ['lr', 'lr-ml1', 'default']
        :return: código de status conforme método utilizado
        """
        if mount_mode == VOLUME_IS_ORIGINAL:
            if match_mode == 'exact':
                if db_used == 'lr':
                    return STATUS_EXACT_VALIDATED_LR
                elif db_used == 'lr-ml1':
                    return STATUS_EXACT_VALIDATED_LR_ML1
                elif db_used == 'default':
                    return STATUS_EXACT_VALIDATED
            else:
                if db_used == 'lr':
                    return STATUS_FUZZY_VALIDATED_LR
                elif db_used == 'lr-ml1':
                    return STATUS_FUZZY_VALIDATED_LR_ML1
                elif db_used == 'default':
                    return STATUS_FUZZY_VALIDATED
        elif mount_mode == VOLUME_IS_INFERRED:
            if match_mode == 'exact':
                if db_used == 'lr':
                    return STATUS_EXACT_VOLUME_INFERRED_VALIDATED_LR
                elif db_used == 'lr-ml1':
                    return STATUS_EXACT_VOLUME_INFERRED_VALIDATED_LR_ML1
                elif db_used == 'default':
                    return STATUS_EXACT_VOLUME_INFERRED_VALIDATED
            else:
                if db_used == 'lr':
                    return STATUS_FUZZY_VOLUME_INFERRED_VALIDATED_LR
                elif db_used == 'lr-ml1':
                    return STATUS_FUZZY_VOLUME_INFERRED_VALIDATED_LR_ML1
                elif db_used == 'default':
                    return STATUS_FUZZY_VOLUME_INFERRED_VALIDATED

    def infer_volume(self, issn: str, year: str):
        """
        Infere o volume de um periódico a partir de issn-to-equation.

        :param issn: issn para o qual o volume será inferido
        :return: str do volume inferido arredondado para valor inteiro (se volume inferido for maior que 0)
        """
        equation = self.db['issn-to-equation'].get(issn)

        if equation:
            a, b, r2 = equation
            volume = a + (b * int(year))

            if volume > 0:
                return str(round(volume))

    def match_exact(self, journal_title: str):
        """
        Procura journal_title de forma exata no dicionário title-to-issnl.

        :param journal_title: título do periódico citado
        :return: set de ISSN-Ls associados de modo exato ao título do periódico citado
        """
        return self.db['title-to-issnl'].get(journal_title, set())

    def match_fuzzy(self, journal_title: str):
        """
        Procura journal_title de forma aproximada no dicionário title-to-issnl.

        :param journal_title: título do periódico citado
        :return: set de ISSN-Ls associados de modo aproximado ao título do periódico citado
        """
        matches = set()

        words = journal_title.split(' ')

        # Para a comparação ser possível, é preciso que o título tenha pelo menos MIN_CHARS_LENGTH letras e seja
        # formado por pelo menos MIN_WORDS_COUNT palavras.
        if len(journal_title) > MIN_CHARS_LENGTH and len(words) >= MIN_WORDS_COUNT:
            # O título oficial deve iniciar com a primeira palavra do título procurado
            pattern = r'[\w|\s]*'.join([word for word in words]) + '[\w|\s]*'
            title_pattern = re.compile(pattern, re.UNICODE)

            # O título oficial deve iniciar com a primeira palavra do título procurado
            for official_title in [ot for ot in self.db['title-to-issnl'].keys() if ot.startswith(words[0])]:
                if title_pattern.fullmatch(official_title):
                    matches = matches.union(self.db['title-to-issnl'][official_title])
        return matches

    def mount_id(self, cit: Citation, collection: str):
        """
        Monta o identificador de uma referência citada.

        :param cit: referência citada
        :param collection: coleção em que a referência foi citada
        :return: código identificador da citação
        """
        cit_id = cit.data['v880'][0]['_']
        return '{0}-{1}'.format(cit_id, collection)

    def mount_standardized_citation_data(self, status: int, key=None, issn_l=None):
        """
        Consulta issn_l (oriundo de key ou de issn_l) no dicionário issnl-to-data para formar a estrutura normalizada da
        referencia citada. Monta estrutura normalizada da referencia citada, conforme os campos a seguir:

            cit-id: identificador da referência citada (str)

            issn-l: ISSN-Link do periódico citado (str)

            issns: ISSNs associados ao ISSN-L (list de strs)

            official-journal-title: títulos oficiais do periódico citado (str)

            official-abbreviated-journal-title: títulos abreviados oficiais do periódico citado (lista de str)

            alternative-journal-title: títulos alternativos do periódico citado (lista de str)

            status: código indicador do méetodo para normalizar

            update-date: data de normalização

        :param cit: referência citada
        :param status: código indicador do método aplicado para normalizar
        :param key: chave da qual o issn-l é extraído e buscado na base de correção
        :param issn_l: issn-l a ser buscado na base de correção
        :return: dicionário composto por pares chave-valor de dados normalizados
        """
        if not issn_l:
            issn_l = self.extract_issnl_from_valid_match(key)

        attrs = self.db['issnl-to-data'][issn_l]

        data = {'issn-l': self.add_hifen_issn(issn_l),
                'issn': [self.add_hifen_issn(i) for i in attrs['issns']],
                'official-journal-title': attrs['main-title'],
                'official-abbreviated-journal-title': attrs['main-abbrev-title'],
                'alternative-journal-titles': attrs['alternative-titles'],
                'status': status,
                'update-date': datetime.now().strftime('%Y-%m-%d')
                }

        return data

    def save_standardized_citations(self, std_citations: dict):
        """
        Persiste as referências citadas normalizadas.

        :param std_citations: dicionário de referências citadas normalizadas
        """
        if self.persist_mode == 'json':
            with open(self.path_results, 'a') as f:
                json.dump(std_citations, f)
                f.write('\n')

        elif self.persist_mode == 'mongo':
            for v in std_citations.values():
                self.standardizer.update_one(
                    filter={'_id': v['_id']},
                    update={'$set': v},
                    upsert=True)

    def get_citation_mongo_status(self, cit_id: str):
        """
        Obtém o status atual de normalização da referência citada.

        :param cit_id: id da referência citada
        :return: status atual de normalização da referência citada
        """
        if self.persist_mode == 'mongo':
            cit_standardized = self.standardizer.find_one({'_id': cit_id})
            if cit_standardized:
                return cit_standardized.get('status', STATUS_NOT_NORMALIZED)
        return STATUS_NOT_NORMALIZED

    def validate_match(self, keys, use_lr=False, use_lr_ml1=False):
        """
        Valida chaves ISSN-ANO-VOLUME nas bases de validação
        :param keys: chaves em formato ISSN-ANO-VOLUME
        :param use_lr: valida com dados de regressão linear de ISSN-ANO-VOLUME
        :param use_lr_ml1: valida com dados de regressão linear de ISSN-ANO-VOLUME mais ou menos 1
        :return: chaves validadas
        """
        valid_matches = set()

        if use_lr:
            validating_base = self.db['issn-year-volume-lr']
        elif use_lr_ml1:
            validating_base = self.db['issn-year-volume-lr-ml1']
        else:
            validating_base = self.db['issn-year-volume']

        for k in keys:
            if k in validating_base:
                valid_matches.add(k)

        return valid_matches

    def _standardize(self, cit, cleaned_cit_journal_title, mode='exact'):
        """
        Processo auxiliar que realiza casamento de um título de periódico citado e valida casamentos, se houver
        mais de um. O processo de validação consiste em desambiguar os possíveis ISSN-Ls associados a um periódico
        citado usando dados de ano e volume da referência citada.

        :param cit: referência citada
        :param mode: mode de execução de casamento ['exact', 'fuzzy']
        :param cleaned_cit_journal_title: título limpo do periódico citado
        :return: dicionário composto por dados normalizados
        """
        if mode == 'fuzzy':
            matches = self.match_fuzzy(cleaned_cit_journal_title)
        else:
            matches = self.match_exact(cleaned_cit_journal_title)

        # Verifica se houve casamento com apenas com um ISSN-L e se é casamento exato
        if len(matches) == 1 and mode == 'exact':
            return self.mount_standardized_citation_data(status=STATUS_EXACT, issn_l=matches.pop())

        # Verifica se houve casamento com mais de um ISSN-L ou se é casamento aproximado e houve apenas um casamento
        elif len(matches) > 1 or (mode == 'fuzzy' and len(matches)) == 1:
            # Carrega todos os ISSNs possiveis associados aos ISSN-Ls casados
            possible_issns = self.get_issns(matches)

            if possible_issns:
                # Monta chaves ISSN-ANO-VOLUME
                keys, mount_mode = self.extract_issn_year_volume_keys(cit, possible_issns)

                if keys:
                    # Valida chaves na base de ano e volume
                    cit_valid_matches = self.validate_match(keys)

                    if len(cit_valid_matches) == 1:
                        status = self.get_status(mode, mount_mode, 'default')
                        return self.mount_standardized_citation_data(status, cit_valid_matches.pop())

                    elif len(cit_valid_matches) == 0:
                        # Valida chaves na base de regressão linear
                        cit_valid_matches = self.validate_match(keys, use_lr=True)

                        if len(cit_valid_matches) == 1:
                            status = self.get_status(mode, mount_mode, 'lr')
                            return self.mount_standardized_citation_data(status, cit_valid_matches.pop())

                        elif len(cit_valid_matches) == 0:
                            # Valida chaves na base de regressão linear com volume flexibilizado
                            cit_valid_matches = self.validate_match(keys, use_lr_ml1=True)

                            if len(cit_valid_matches) == 1:
                                status = self.get_status(mode, mount_mode, 'lr-ml1')
                                return self.mount_standardized_citation_data(status, cit_valid_matches.pop())

    def standardize(self, document):
        """
        Normaliza referências citadas de um artigo.
        Atua de duas formas: exata e aproximada.
        Persiste resultados em arquivo JSON ou em MongoDB.

        :param document: Article dos quais as referências citadas serão normalizadas
        """
        std_citations = {}

        if document.citations:
            for c, cit in enumerate([dc for dc in document.citations if dc.publication_type == 'article']):
                cit_id = self.mount_id(cit, document.collection_acronym)
                cit_current_status = self.get_citation_mongo_status(cit_id)

                if cit_current_status == STATUS_NOT_NORMALIZED:
                    cleaned_cit_journal_title = preprocess_journal_title(cit.source)

                    if cleaned_cit_journal_title:

                        if self.use_exact:
                            exact_match_result = self._standardize(cit, cleaned_cit_journal_title)
                            if exact_match_result:
                                exact_match_result.update({'_id': cit_id, 'cited-journal-title': cleaned_cit_journal_title})
                                std_citations[cit_id] = exact_match_result
                                cit_current_status = exact_match_result['status']

                        if self.use_fuzzy:
                            if cit_current_status == STATUS_NOT_NORMALIZED:
                                fuzzy_match_result = self._standardize(cit, cleaned_cit_journal_title, mode='fuzzy')
                                if fuzzy_match_result:
                                    fuzzy_match_result.update({'_id': cit_id, 'cited-journal-title': cleaned_cit_journal_title})
                                    std_citations[cit_id] = fuzzy_match_result
                                    cit_current_status = fuzzy_match_result['status']

                        if cit_current_status == STATUS_NOT_NORMALIZED and (self.use_exact or self.use_fuzzy):
                            unmatch_result = {'_id': cit_id,
                                              'cited-journal-title': cleaned_cit_journal_title,
                                              'status': STATUS_NOT_NORMALIZED,
                                              'update-date': datetime.now().strftime('%Y-%m-%d')}
                            std_citations[cit_id] = unmatch_result

        if std_citations:
            self.save_standardized_citations(std_citations)
