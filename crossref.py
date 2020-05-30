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

    logging.basicConfig(level=logging.INFO)

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
                    cit_attrs = {}

                    if self.persist_mode == 'json':
                        cit_attrs = self._extract_cit_attrs(cit)
                    elif self.persist_mode == 'mongo':
                        if not self.mongo.find_one({'_id': cit_id}):
                            cit_attrs = self._extract_cit_attrs(cit)

                    if cit_attrs:
                        cit_id_to_attrs[cit_id] = cit_attrs

        return cit_id_to_attrs

    def _extract_cit_attrs(self, cit: Citation):
        """
        Extrai os atributos de uma referência citada necessários para requisitar metadados CrossRef.

        :param cit: referência citada
        :return: dicionário de atributos para consulta no serviço CrossRef
        """
        if cit.doi:
            valid_doi = preprocess_doi(cit.doi)
            if valid_doi:
                return {'doi': valid_doi}

        attrs = {}

        if cit.first_author:
            first_author_surname = cit.first_author.get('surname', '')
            cleaned_author_surname = preprocess_author_name(first_author_surname)
            if cleaned_author_surname:
                attrs.update({'aulast': cleaned_author_surname})

        journal_title = cit.source
        if journal_title:
            cleaned_journal_title = preprocess_journal_title(journal_title)
            if cleaned_journal_title:
                attrs.update({'title': cleaned_journal_title})

        publication_date = html.unescape(cit.publication_date) if cit.publication_date else None
        if publication_date and len(publication_date) >= 4:
            publication_year = publication_date[:4]
            if publication_year.isdigit():
                attrs.update({'data': publication_year})

        volume = html.unescape(cit.volume) if cit.volume else None
        if volume:
            attrs.update({'volume': volume})

        issue = html.unescape(cit.issue) if cit.issue else None
        if issue:
            attrs.update({'issue': issue})

        first_page = html.unescape(cit.first_page) if cit.first_page else None
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

    async def run(self, citations_attrs: dict):
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
        tasks = []

        async with ClientSession(headers={'mailto:': self.email}) as session:
            for cit_id, attrs in citations_attrs.items():
                if 'doi' in attrs:
                    url = ENDPOINT_CROSSREF_WORKS.format(attrs['doi'])
                    mode = 'doi'

                else:
                    url = ENDPOINT_CROSSREF_OPENURL
                    for k, v in attrs.items():
                        if k != 'doi':
                            url += '&' + k + '=' + v
                    url += '&pid=' + self.email
                    url += '&format=unixref'
                    url += '&multihit=false'
                    mode = 'attrs'

                task = asyncio.ensure_future(self.bound_fetch(cit_id, url, sem, session, mode))
                tasks.append(task)
            responses = asyncio.gather(*tasks)
            await responses

    async def bound_fetch(self, cit_id, url, semaphore, session, mode):
        async with semaphore:
            await self.fetch(cit_id, url, session, mode)

    async def fetch(self, cit_id, url, session, mode):
        try:
            async with session.get(url) as response:
                try:
                    logging.info('Trying to collect metadata for %s' % cit_id)

                    if mode == 'doi':
                        metadata = await response.json()

                    else:
                        raw_metadata = await response.text()
                        metadata = self.parse_crossref_openurl_result(raw_metadata)

                    if metadata:
                        id_to_metadata = {'_id': cit_id, 'crossref': metadata}
                        self.save_crossref_metadata(id_to_metadata)
                except JSONDecodeError as e:
                    logging.warning('JSONDecodeError: %s' % cit_id)
        except ContentTypeError as e:
            logging.warning('ContentTypeError: %s' % cit_id)
        except ServerDisconnectedError as e:
            logging.warning('ServerDisconnectedError: %s' % cit_id)
        except TimeoutError as e:
            logging.warning('TimeoutError: %s' % cit_id)
        except ClientConnectorError as e:
            logging.warning('ClientConectorError: %s' % cit_id)


def format_date(date: datetime):
    if not date:
        return None
    return date.strftime('%Y-%m-%d')


def main():
    usage = "collect metadata from the Crossref Service"

    parser = argparse.ArgumentParser(textwrap.dedent(usage))

    parser.add_argument(
        '-c', '--col',
        default=None,
        dest='col',
        help='normalize cited references in an entire collection'
    )

    parser.add_argument(
        '-f', '--from_date',
        type=lambda x: datetime.strptime(x, '%Y-%m-%d'),
        nargs='?',
        help='collect metadata for cited references in documents published from a date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '-u', '--until_date',
        type=lambda x: datetime.strptime(x, '%Y-%m-%d'),
        nargs='?',
        default=datetime.now(),
        help='collect metadata for cited references in documents published until a date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '-i', '--document_id',
        default=None,
        dest='pid',
        help='collect metadata for cited for the cited references in a PID (document)'
    )

    parser.add_argument(
        '-a', '--mongo_host',
        default=None,
        dest='mongo_host',
        help='MongoDB host address'
    )

    parser.add_argument(
        '-m', '--mongo_database',
        default=DEFAULT_MONGO_DATABASE_NAME,
        dest='mongo_database',
        help='MongoDB database name'
    )

    parser.add_argument(
        '-l', '--mongo_collection',
        default=DEFAULT_MONGO_COLLECTION_NAME,
        dest='mongo_collection',
        help='MongoDB collection name'
    )

    parser.add_argument(
        '-e', '--email',
        required=True,
        default=None,
        dest='email',
        help='an e-mail registered in the Crossref service'
    )

    args = parser.parse_args()

    try:

        art_meta = RestfulClient()
        cac = CrossrefAsyncCollector(email=args.email,
                                     mongo_host=args.mongo_host,
                                     mongo_database=args.mongo_database,
                                     mongo_collection=args.mongo_collection)

        cit_ids_to_attrs = {}

        start_time = time.time()

        if args.pid:
            logging.info('Running in one PID mode')
            document = art_meta.document(collection=args.col, code=args.pid)

            if document:
                logging.info('Extracting info from cited references in %s ' % document.publisher_id)
                cit_ids_to_attrs = cac.extract_attrs(document)
        else:
            logging.info('Running in many PIDs mode')

            for document in art_meta.documents(collection=args.col,
                                               from_date=format_date(args.from_date),
                                               until_date=format_date(args.until_date)):
                logging.info('Extracting info from cited references in %s ' % document.publisher_id)
                cit_ids_to_attrs.update(cac.extract_attrs(document))

        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(cac.run(cit_ids_to_attrs))
        loop.run_until_complete(future)

        end_time = time.time()
        logging.info('Duration {0} seconds.'.format(end_time - start_time))

    except KeyboardInterrupt:
        print("Interrupt by user")


if __name__ == '__main__':
    main()
