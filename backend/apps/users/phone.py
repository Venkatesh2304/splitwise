import re


def normalize_phone(raw):
    """A 10-digit Indian mobile number from whatever was typed or sent, or None.

    Blinkit reports numbers in more than one shape (+91 prefix, spaces), and the
    login forms used to save anything typed into them, a server address once.
    """
    digits = re.sub(r'\D', '', str(raw or ''))
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    return digits if len(digits) == 10 else None
