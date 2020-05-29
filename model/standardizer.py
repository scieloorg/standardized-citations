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

    def mount_id(self, cit: Citation, collection: str):
        """
        Monta o identificador de uma referência citada.

        :param cit: referência citada
        :param collection: coleção em que a referência foi citada
        :return: código identificador da citação
        """
        cit_id = cit.data['v880'][0]['_']
        return '{0}-{1}'.format(cit_id, collection)

