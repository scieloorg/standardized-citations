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


