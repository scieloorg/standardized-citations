import argparse
import asyncio
import json
import logging
import textwrap
import time
import xmltodict

from aiohttp import ClientSession, ClientConnectorError, ServerDisconnectedError, ContentTypeError
from articlemeta.client import RestfulClient
from datetime import datetime
from json import JSONDecodeError
from pyexpat import ExpatError
from pymongo import errors, MongoClient
from utils.string_processor import preprocess_journal_title
from xylose.scielodocument import Article, Citation


DEFAULT_MONGO_DATABASE_NAME = 'citations'
DEFAULT_MONGO_COLLECTION_NAME = 'standardized'

ENDPOINT_CROSSREF_WORKS = 'https://api.crossref.org/works/{}'
ENDPOINT_CROSSREF_OPENURL = 'https://doi.crossref.org/openurl?'

SEMAPHORE_LIMIT = 20


class CrossrefAsyncCollector(object):

    def __init__(self, email: None, mongo_database, mongo_collection, mongo_host=None):
        self.email = email

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
            self.path_results = 'crossref-results-' + str(time.time()) + '.json'

    def extract_attrs(self, article: Article):
        """
        Extrai os atributos de todas as referências citadas de um documento.

        :param article: documento do qual serão extraídos os atributos das referências citadas
        :return: dicionário de ids de citações e respectivos atributos
        """
        cit_id_to_attrs = {}

        if article.citations:
            for cit in article.citations:
                if cit.publication_type == 'article':
                    cit_id = self.mount_id(cit, article.collection_acronym)
                    cit_attrs = self._extract_cit_attrs(cit)

                    cit_id_to_attrs[cit_id] = cit_attrs

        return cit_id_to_attrs

    def _extract_cit_attrs(self, cit: Citation):
        """
        Extraí os atributos de uma referência citada necessários para requisitar metadados CrossRef.

        :param cit: referência citada
        :return: dicionário de atributos para consulta no serviço CrossRef
        """
        if cit.doi:
            return {'doi': cit.doi}

        attrs = {}

        if cit.first_author:
            first_author_surname = cit.first_author.get('surname', '')
            if first_author_surname:
                attrs.update({'aulast': first_author_surname})

        journal_title = cit.source
        if journal_title:
            cleaned_journal_title = preprocess_journal_title(journal_title)
            if cleaned_journal_title:
                attrs.update({'title': cleaned_journal_title})

        publication_year = cit.publication_date
        if publication_year:
            attrs.update({'data': publication_year})

        volume = cit.volume
        if volume:
            attrs.update({'volume': volume})

        issue = cit.issue
        if issue:
            attrs.update({'issue': issue})

        first_page = cit.first_page
        if first_page:
            attrs.update({'spage': first_page})

        if attrs:
            return attrs

    def parse_crossref_openurl_result(self, text):
        """
        Converte response.text para JSON com metadados obtidos do endpoint OPENURL.

        :param response: resposta de requisição em formato de texto
        :return: JSON com metadados obtidos no serviço CrossRef
        """
        try:
            raw = xmltodict.parse(text)

            for v in raw.get('doi_records', {}).values():
                metadata = v.get('crossref')
                if metadata and 'error' not in metadata.keys():

                    owner = v.get('@owner')
                    if owner:
                        metadata.update({'owner': owner})

                    timestamp = v.get('@timestamp')
                    if timestamp:
                        metadata.update({'timestamp': timestamp})

                    return metadata

        except ExpatError as e:
            logging.warning("ExpatError {0}".format(text))
            logging.warning(e)

    def mount_id(self, cit: Citation, collection: str):
        """
        Monta o identificador de uma referência citada.

        :param cit: referência citada
        :param collection: coleção em que a referência foi citada
        :return: código identificador da citação
        """
        cit_id = cit.data['v880'][0]['_']
        return '{0}-{1}'.format(cit_id, collection)

    def save_crossref_metadata(self, id_to_metadata: dict):
        """
        Persiste os metadados da referência citada.

        :param id_to_metadata: dicionário com id da referência citada e seus respectivos metadados Crossref
        """
        if self.persist_mode == 'json':
            with open(self.path_results, 'a') as f:
                json.dump(id_to_metadata, f)
                f.write('\n')

        elif self.persist_mode == 'mongo':
            self.mongo.update_one(filter={'_id': id_to_metadata['_id']},
                                  update={'$set': {
                                      'crossref': id_to_metadata['crossref'],
                                      'update-date': datetime.now()
                                  }},
                                  upsert=True)
