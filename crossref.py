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
