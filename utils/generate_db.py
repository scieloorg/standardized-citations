import argparse
import csv
import logging
import pickle
import textwrap

from datetime import datetime


def clean_issn(issn: str):
    """
    Verifica se ISSN está no formato padrao 'DDDD-DDDD' e remove hífen.

    :param issn: ISSN
    :return: ISSN limpo (sem o hífen)
    """
    if len(issn) == 9 and '-' in issn:
        return ''.join([issn[:4], issn[5:]])
    elif len(issn) == 8 and '-' not in issn:
        return issn
