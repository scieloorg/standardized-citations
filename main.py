import argparse
import logging
import textwrap

from articlemeta.client import RestfulClient
from datetime import datetime
from model.standardizer import Standardizer
from time import time


DEFAULT_MONGO_DATABASE_NAME = 'citations'
DEFAULT_MONGO_COLLECTION_NAME = 'standardized'

