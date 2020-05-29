import html
import re
import unicodedata


parenthesis_pattern = re.compile(r'[-a-zA-ZÀ-ÖØ-öø-ÿ|0-9]*\([-a-zA-ZÀ-ÖØ-öø-ÿ|\W|0-9]*\)[-a-zA-ZÀ-ÖØ-öø-ÿ|0-9]*', re.UNICODE)
special_chars = ['@', '&']
special_words = ['IMPRESSO', 'ONLINE', 'CDROM', 'PRINT', 'ELECTRONIC']


def remove_invalid_chars(text):
    """
    Remove de text os caracteres que possuem código ASCII < 32 e = 127.
    :param text: texto a ser tratada
    :return: texto com caracteres ASCII < 32 e = 127 removidos
    """
    vchars = []
    for t in text:
        if ord(t) == 11:
            vchars.append(' ')
        elif ord(t) >= 32 and ord(t) != 127:
            vchars.append(t)
    return ''.join(vchars)


def remove_accents(text):
    """
    Transforma caracteres acentuados de text em caracteres sem acento.
    :param text: texto a ser tratado
    :return: texto sem caracteres acentuados
    """
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')


def alpha_num_space(text, include_special_chars=False):
    """
    Mantém em text apenas caracteres alpha, numéricos e espaços.
    Possibilita manter em text caracteres especiais na lista special_chars
    :param text: texto a ser tratado
    :param include_special_chars: booleano que indica se os caracteres especiais devem ou não ser mantidos
    :return: texto com apenas caracteres alpha e espaço mantidos (e especiais, caso solicitado)
    """
    new_str = []
    for character in text:
        if character.isalnum() or character.isspace() or (include_special_chars and character in special_chars):
            new_str.append(character)
        else:
            new_str.append(' ')
    return ''.join(new_str)


def remove_double_spaces(text):
    """
    Remove espaços duplos de text
    :param text: texto a ser tratado
    :return: texto sem espaços duplos
    """
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text.strip()


def preprocess_author_name(text):
    """
    Procedimento que trata nome de autor.
    Aplica:
        1. Remoção de acentos
        2. Manutenção de alpha e espaço
        3. Remoção de espaços duplos
    :param text: nome do autor a ser tratado
    :return: nome tratado do autor
    """
    return remove_double_spaces(alpha_num_space(remove_accents(text)))
