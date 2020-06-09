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


def main():
    usage = "normalize cited references"

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
        help='normalize cited references in documents published from a date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '-u', '--until_date',
        type=lambda x: datetime.strptime(x, '%Y-%m-%d'),
        nargs='?',
        default=datetime.now(),
        help='normalize cited references in documents published until a date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '-i', '--document_id',
        default=None,
        dest='pid',
        help='normalize the cited references in a PID (document)'
    )

    parser.add_argument(
        '-d', '--database',
        required=True,
        dest='db',
        help='binary file containing a dictionary composed of five bases: '
             'title-to-issnl, '
             'issnl-to-issns, '
             'issnl-to-data, '
             'title-year-volume, '
             'issn-year-volume, '
             'issn-year-volume-lr, '
             'issn-year-volume-lr-ml1, '
             'issn-to-equation'
    )

    parser.add_argument(
        '-z', '--fuzzy',
        default=False,
        dest='use_fuzzy',
        action='store_true',
        help='use fuzzy match techniques'
    )

    parser.add_argument(
        '-x', '--use_exact',
        default=False,
        dest='use_exact',
        action='store_true',
        help='use exact match techniques'
    )

    parser.add_argument(
        '--mongo_uri',
        default=None,
        dest='mongo_uri_std_cits',
        help='mongo uri string in the format mongodb://[username:password@]host1[:port1][,...hostN[:portN]][/[defaultauthdb][?options]]'
    )

    args = parser.parse_args()

    try:

        sz = Standardizer(
            path_db=args.db,
            use_exact=args.use_exact,
            use_fuzzy=args.use_fuzzy,
            mongo_uri_std_cits=args.mongo_uri_std_cits
        )

        art_meta = RestfulClient()

        if args.pid:
            logging.info('Running in one PID mode')
            document = art_meta.document(collection=args.col, code=args.pid)

            if document:
                logging.info('Normalizing cited references in %s ' % document.publisher_id)
                sz.standardize(document)

        else:
            logging.info('Running in many PIDs mode')
            logging.info(get_execution_mode(sz.use_exact, sz.use_fuzzy))

            start_time = time()

            if sz.use_exact or sz.use_fuzzy:
                for document in art_meta.documents(collection=args.col,
                                                   from_date=format_date(args.from_date),
                                                   until_date=format_date(args.until_date)):
                    logging.info('Normalizing cited references in %s ' % document.publisher_id)
                    sz.standardize(document)

            end_time = time()
            logging.info('Duration {0} seconds.'.format(end_time - start_time))

    except KeyboardInterrupt:
        print("Interrupt by user")


if __name__ == '__main__':
    main()
