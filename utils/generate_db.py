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


def get_db_issnl_and_db_title(path_db_issnl, sep='|'):
    """
    Extrai dicionário de base de correção ISSN-L-TO-DATA, TITLE-TO-ISSN-L e ISSN-TO-ISSN-L.

    :param path_db_year_volume: caminho do arquivo da tabela de dados ISSN-L-ATRIBUTOS
    :param sep: delimitador de campo do arquivo
    :return: tupla (base de correção ISSN-L-TO-DATA, TITLE-TO-ISSN-L e ISSN-TO-ISSN-L)
    """
    issnl_to_data = {}
    title_to_issnl = {}
    issn_to_issnl = {}

    with open(path_db_issnl) as f:
        csv_reader = csv.DictReader(f, delimiter=sep)
        for i in csv_reader:
            issnl = i.get('ISSNL', '')
            main_title = i.get('MAIN_TITLE', '').split('#')
            main_abbrev_title = i.get('MAIN_ABBREV_TITLE', '').split('#')
            issns = i.get('ISSNS', '').split('#')
            alternative_titles = i.get('TITLES', '').split('#')

            if issnl != '' and issnl not in issnl_to_data:
                issnl_to_data[issnl] = {
                    'main-title': main_title,
                    'main-abbrev-title': main_abbrev_title,
                    'issns': issns,
                    'alternative-titles': alternative_titles
                }

                for ti in set(main_title + main_abbrev_title + alternative_titles):
                    if ti not in title_to_issnl:
                        title_to_issnl[ti] = set()
                    title_to_issnl[ti].add(issnl)
            else:
                logging.info('ISSN-L %s is already in the list' % issnl)

            for j in issns:
                if j not in issn_to_issnl:
                    issn_to_issnl[j] = issnl
                else:
                    logging.info('ISSN %s is associated with %s (beyond %s)' % (j, issnl, issn_to_issnl[j]))

    return issnl_to_data, title_to_issnl, issn_to_issnl


def get_equations(path_equations, sep='|'):
    """
    Extrai dicionário de base de predição de volume ISSN-TO-EQUATION.

    :param path_equations: caminho do arquivo da tabela de equações
    :param sep: delimitador de campo do arquivo
    :return: dicionário ISSN-TO-EQUATION
    """
    issn_to_equation = {}
    with open(path_equations) as f:
        csv_reader = csv.DictReader(f, delimiter=sep)
        for i in csv_reader:
            issn = i.get('ISSN')
            a = float(i.get('a'))
            b = float(i.get('b'))
            r = float(i.get('r2'))
            if issn not in issn_to_equation:
                issn_to_equation[issn] = (a, b, r)

    return issn_to_equation


def save(db_data, path_db):
    """
    Persiste base de correção no disco, em formato binário.

    :param db_data: dados a serem persistidos
    :param path_db: nome do arquivo a ser persistido
    """
    with open(path_db, 'wb') as f:
        pickle.dump(db_data, f)
