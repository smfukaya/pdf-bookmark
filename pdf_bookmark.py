#!/usr/bin/env python

# pylint: disable=invalid-name

'''
Import and export PDF bookmark
'''

import sys
import subprocess
import re
import argparse


_NUM_STYLE_MAP = {
    'DecimalArabicNumerals': 'Arabic',
    'UppercaseRomanNumerals': 'Roman',
    'LowercaseRomanNumerals': 'Roman',
    'UppercaseLetters': 'Letters',
    'LowercaseLetters': 'Letters',
}


_ROMAN_NUMERAL_PAIR = (
    ('M', 1000),
    ('CM', 900),
    ('D', 500),
    ('CD', 400),
    ('C', 100),
    ('XC', 90),
    ('L', 50),
    ('XL', 40),
    ('X', 10),
    ('IX', 9),
    ('V', 5),
    ('IV', 4),
    ('I', 1),
)

_ROMAN_NUMERAL_MAP = {pair[0]: pair[1] for pair in _ROMAN_NUMERAL_PAIR}


_ROMAN_NUMERAL_PATTERN = re.compile(
    '^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
)


BOOKMARK_DESCRIPTION = {
    'bookmark': {
        'prefix': 'Bookmark',
        'fields': {
            'Title': 'title',
            'Level': 'level',
            'PageNumber': 'page',
        },
        'handler': {
            'title': lambda s: _unicode_replace(s) if _UNICODE_REGEXP.search(s) else s,
            'level': int,
            'page': int,
        },
    },
    'page_label': {
        'prefix': 'PageLabel',
        'fields': {
            'NewIndex': 'new_index',
            'Start': 'start',
            'NumStyle': 'num_style',
        },
        'handler': {
            'new_index': int,
            'start': int,
            'num_style': lambda s: _NUM_STYLE_MAP.get(s, 'Arabic'),
        },
    },
}


_UNICODE_REGEXP = re.compile('&#([0-9]+);')


class InvalidNumeralError(Exception):
    '''Invalid numeral expression'''


class InvalidRomanNumeralError(InvalidNumeralError):
    '''Invalid roman numeral expression'''


class RomanOutOfRangeError(Exception):
    '''The roman number is out of range'''


class InvalidLettersNumeralError(InvalidNumeralError):
    '''Invalid letters numeral expression'''


class LettersOutOfRangeError(Exception):
    '''The letters number is out of range'''


def roman_to_arabic(roman):
    '''
    Convert roman to arabic
    '''
    if not roman:
        raise InvalidRomanNumeralError('No input found')

    if roman == 'N':
        return 0

    if not _ROMAN_NUMERAL_PATTERN.match(roman):
        raise InvalidRomanNumeralError(
            'Invalid Roman numeral: {}'.format(roman))

    arabic = 0
    for i, n in enumerate(roman):
        if i == len(roman)-1 or _ROMAN_NUMERAL_MAP[roman[i]] >= _ROMAN_NUMERAL_MAP[roman[i+1]]:
            arabic += _ROMAN_NUMERAL_MAP[n]
        else:
            arabic -= _ROMAN_NUMERAL_MAP[n]

    return arabic


def arabic_to_roman(arabic):
    '''
    Convert arabic to roman
    '''
    if arabic < 0 or arabic > 4999:
        raise RomanOutOfRangeError('Roman numeral must in [0, 5000)')

    if arabic == 0:
        return 'N'

    roman = ''

    remain = arabic
    for digit, unit in _ROMAN_NUMERAL_PAIR:
        digit_num = remain // unit
        roman += digit*digit_num
        remain -= unit*digit_num

    return roman


def letters_to_arabic(letters):
    '''
    Convert letters to arabic
    '''
    if not letters:
        return 0

    letter = letters[0]
    if ord(letter) < ord('A') or ord(letter) > ord('Z'):
        raise InvalidLettersNumeralError('Must be capital letter')

    for digit in letters[1:]:
        if digit != letter:
            raise InvalidLettersNumeralError('Letters are not identical')

    return len(letters)*26 - 25 + ord(letter) - ord('A')


def arabic_to_letters(arabic):
    '''
    Convert arabic to letters
    '''
    if arabic < 0:
        raise LettersOutOfRangeError('Letters numeral must >= 0')

    if arabic == 0:
        return ''

    return chr(((arabic-1) % 26) + ord('A')) * ((arabic+25) // 26)


def _unicode_replace_match(match):
    return chr(int(match.group(1)))


def _unicode_replace(string):
    return _UNICODE_REGEXP.sub(_unicode_replace_match, string)


def call(cmd, encoding=None):
    '''
    Run command
    '''
    if encoding is None:
        encoding = 'utf-8'

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    status = p.wait()

    if status != 0:
        raise Exception(
            'Invoke command {} failed with exit code {}:\n {}'.format(
                cmd, status, err.decode(encoding)))

    if encoding:
        out = out.decode(encoding)
    return out


def pdftk_to_bookmarks(data):
    '''
    Convert pdftk output to bookmark
    '''
    bookmark_types = ['bookmark', 'page_label']

    bookmarks = {}
    bookmark_info = {}

    for t in bookmark_types:
        bookmarks[t] = []
        bookmark_info[t] = {}

    for line in data.splitlines():
        try:
            key, value = line.split(': ', 1)
        except ValueError:  # e.g. line == 'InfoBegin'
            continue

        for bm_type in bookmark_types:
            bm_detail = BOOKMARK_DESCRIPTION[bm_type]

            if not key.startswith(bm_detail['prefix']):
                continue

            k = key[len(bm_detail['prefix']):]
            if k not in bm_detail['fields']:
                continue

            k = bm_detail['fields'][k]
            if k in bm_detail['handler']:
                v = bm_detail['handler'][k](value)

            bookmark_info[bm_type][k] = v

            ready_for_save = True
            for _, field in bm_detail['fields'].items():
                if field not in bookmark_info[bm_type]:
                    ready_for_save = False
                    break
            if not ready_for_save:
                continue

            bookmarks[bm_type].append(bookmark_info[bm_type])
            bookmark_info[bm_type] = {}

    return bookmarks['bookmark'], bookmarks['page_label']


def export_bookmarks(bookmarks, page_labels):
    '''
    Export to bookmark format
    '''
    bm_output = ''

    current_page_label_index = -1

    for bm in bookmarks:
        page_label_index = -1
        for i, pl in enumerate(page_labels):
            if bm['page'] >= pl['new_index']:
                page_label_index = i

        if page_label_index >= 0:
            if page_label_index != current_page_label_index:
                if current_page_label_index >= 0:
                    bm_output += '\n'

                bm_output += '!!! new_index = {}\n'.format(
                    page_labels[page_label_index]['new_index'])
                bm_output += '!!! start = {}\n'.format(
                    page_labels[page_label_index]['start'])
                bm_output += '!!! num_style = {}\n\n'.format(
                    page_labels[page_label_index]['num_style'])

                current_page_label_index = page_label_index

            page = bm['page'] - \
                page_labels[page_label_index]['new_index'] + \
                page_labels[page_label_index]['start']

            if page_labels[page_label_index]['num_style'] == 'Roman':
                page = arabic_to_roman(page)
            elif page_labels[page_label_index]['num_style'] == 'Letters':
                page = arabic_to_letters(page)
        else:
            page = bm['page']

        bm_output += '{}{}..........{}\n'.format(
            '  '*(bm['level']-1), bm['title'], page)

    return bm_output


def main():
    '''
    The main process
    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', metavar='PDF', help='an input PDF')
    parser.add_argument(
        '--expand-level', help='the max level to be expanded')

    args = parser.parse_args()

    pdftk_data = call(['pdftk', args.pdf, 'dump_data'], 'ascii')

    bookmarks, page_labels = pdftk_to_bookmarks(pdftk_data)

    print(export_bookmarks(bookmarks, page_labels))

    return 0


if __name__ == '__main__':
    sys.exit(main())
