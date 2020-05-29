import html
import re
import unicodedata


parenthesis_pattern = re.compile(r'[-a-zA-ZÀ-ÖØ-öø-ÿ|0-9]*\([-a-zA-ZÀ-ÖØ-öø-ÿ|\W|0-9]*\)[-a-zA-ZÀ-ÖØ-öø-ÿ|0-9]*', re.UNICODE)
special_chars = ['@', '&']
special_words = ['IMPRESSO', 'ONLINE', 'CDROM', 'PRINT', 'ELECTRONIC']
