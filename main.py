import argparse
import logging
import textwrap

from articlemeta.client import RestfulClient
from datetime import datetime
from model.standardizer import Standardizer
from time import time


DEFAULT_MONGO_DATABASE_NAME = 'citations'
DEFAULT_MONGO_COLLECTION_NAME = 'standardized'


def format_date(date: datetime):
    if not date:
        return None
    return date.strftime('%Y-%m-%d')


def get_execution_mode(use_exact, use_fuzzy):
    info = []

    if use_exact:
        info.append('Exact is on')
    else:
        info.append('Exact is off')

    if use_fuzzy:
        info.append('Fuzzy is on')
    else:
        info.append('Fuzzy is off')

    return ' - '.join(info)


