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
