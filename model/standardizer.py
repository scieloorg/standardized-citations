import json
import logging
import pickle
import re
import time

from datetime import datetime
from pymongo import errors, MongoClient
from utils.string_processor import preprocess_journal_title
from xylose.scielodocument import Citation


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
                 mongo_database,
                 mongo_collection,
                 use_exact=False,
                 use_fuzzy=False,
                 mongo_host=None):

        self.use_exact = use_exact
        self.use_fuzzy = use_fuzzy

        if mongo_host:
            try:
                self.persist_mode = 'mongo'
                self.mongo = MongoClient(mongo_host)[mongo_database][mongo_collection]
                total_docs = self.mongo.count_documents({})
                logging.info('There are {0} documents in the mongo {1}.{2}'.format(total_docs, mongo_database, mongo_collection))
            except errors.ConnectionFailure as e:
                logging.error('ConnectionFailure %s' % e)
        else:
            self.persist_mode = 'json'
            self.path_results = 'std-results-' + str(time.time()) + '.json'

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

    def get_citation_mongo_status(self, cit_id: str):
        """
        Obtém o status atual de normalização da referência citada.

        :param cit_id: id da referência citada
        :return: status atual de normalização da referência citada
        """
        if self.persist_mode == 'mongo':
            cit_standardized = self.mongo.find_one({'_id': cit_id})
            if cit_standardized:
                return cit_standardized.get('status', STATUS_NOT_NORMALIZED)
        return STATUS_NOT_NORMALIZED
