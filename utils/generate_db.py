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


def get_db_year_volume(path_db_year_volume, sep='|'):
    """
    Extrai dicionário de base de validação ISSN-ANO-VOLUME e TITULO-ANO-VOLUME.

    :param path_db_year_volume: caminho do arquivo da tabela de dados ISSN-TITULO-ANO-VOLUME
    :param sep: delimitador de campo do arquivo
    :return: tupla (base de validação ISSN-ANO-VOLUME, TITLE-ANO-VOLUME)
    """
    issn_year_volume = set()
    title_year_volume = set()

    with open(path_db_year_volume) as f:
        csv_reader = csv.DictReader(f, delimiter=sep)
        for i in csv_reader:
            issn = clean_issn(i.get('ISSN'))
            title = i.get('TITLE')

            if not issn:
                logging.error('ISSN empty: %s' % i)
            else:
                year = i.get('YEAR')
                volume = i.get('VOLUME')

                issn_year_volume.add('-'.join([issn, year, volume]))

                if not title:
                    logging.info('TITLE empty: %s' % i)
                else:
                    title_year_volume.add('-'.join([title, year, volume]))

    return issn_year_volume, title_year_volume


def get_db_year_volume_linear_regression(path_db_year_volume_linear_regression, sep='|'):
    """
    Extrai dicionário de base de validação ISSN-ANO-VOLUME e ISSN-ANO-VOLUME flexibilizada.

    :param path_db_year_volume: caminho do arquivo da tabela de dados ISSN-ANO-VOLUME
    :param sep: delimitador de campo do arquivo
    :return: tupla (base de validação ISSN-ANO-VOLUME LR, ISSN-ANO-VOLUME LR ML1)
    """
    issn_year_volume = set()
    issn_year_volume_more_or_less_one = set()

    with open(path_db_year_volume_linear_regression) as f:
        csv_reader = csv.DictReader(f, delimiter=sep)
        for i in csv_reader:
            issn = i.get('ISSN')
            year = i.get('YEAR')

            rounded_predicted_vol_ideal = i.get('ROUNDED PV')
            issn_year_volume.add('-'.join([issn, year, rounded_predicted_vol_ideal]))

            rounded_predicted_vol_minus_one = i.get('ROUNDED PV - 1')
            issn_year_volume_more_or_less_one.add('-'.join([issn, year, rounded_predicted_vol_minus_one]))

            rounded_predicted_vol_plus_one = i.get('ROUNDED PV + 1')
            issn_year_volume_more_or_less_one.add('-'.join([issn, year, rounded_predicted_vol_plus_one]))

    return issn_year_volume, issn_year_volume_more_or_less_one
