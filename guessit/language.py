#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# GuessIt - A library for guessing information from filenames
# Copyright (c) 2011 Nicolas Wack <wackou@gmail.com>
#
# GuessIt is free software; you can redistribute it and/or modify it under
# the terms of the Lesser GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# GuessIt is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Lesser GNU General Public License for more details.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals
from guessit import UnicodeMixin, base_text_type, u, s
from guessit.textutils import find_words
from babelfish import Language, LANGUAGES
from babelfish.converters.name import NameConverter
import babelfish
import re
import logging

__all__ = [ 'Language','UNDETERMINED',
            'search_language', 'guess_language' ]

log = logging.getLogger(__name__)

UNDETERMINED = babelfish.Language('und')


class INameConverter(babelfish.ReverseConverter):
    def __init__(self):
        self.nc = NameConverter()
        self.codes = self.nc.codes
        self.from_lower = { s.lower(): alpha3 for s, alpha3 in self.nc.from_name.items() }

    def convert(self, alpha3, country=None):
        return self.nc.convert(alpha3, country)

    def reverse(self, iname):
        try:
            return (self.from_lower[iname.lower()], None)
        except KeyError:
            raise babelfish.ReverseError(iname)


SYN = { ('und', None): [ 'unknown', 'inconnu', 'unk', 'un' ],
        ('gre', None): [ 'gr', 'greek' ],
        ('spa', None): [ 'esp', 'español' ],
        ('fra', None): [ 'français' ],
        ('swe', None): [ 'se' ],
        ('por', 'br'): [ 'po', 'pb', 'pob', 'br', 'brazilian' ],
        ('cat', None): [ 'català' ],
        ('cze', None): [ 'cz' ],
        ('ukr', None): [ 'ua' ],
        ('chi', None): [ 'cn' ],
        ('jpn', None): [ 'jp' ],
        ('hrv', None): [ 'scr' ]
        }

class GuessitConverter(babelfish.ReverseConverter):
    def __init__(self):
        self.codes = set()
        self.to_guessit = {}
        self.guessit_exceptions = {}

        self.alpha3b = babelfish.converters.alpha3b.Alpha3BConverter()
        self.alpha2 = babelfish.converters.alpha2.Alpha2Converter()
        self.iname = INameConverter()

        self.codes |= LANGUAGES | self.alpha3b.codes | self.alpha2.codes | self.iname.codes

        for (alpha3, country), synlist in SYN.items():
            self.to_guessit[alpha3] = synlist[0]
            for syn in synlist:
                self.guessit_exceptions[syn.lower()] = (alpha3, country)
                self.codes.add(syn)

    def convert(self, alpha3, country=None):
        return str(babelfish.Language(alpha3, country))

    def reverse(self, name):
        for conv in [ babelfish.Language,
                      babelfish.Language.fromalpha3b,
                      babelfish.Language.fromalpha2,
                      babelfish.Language.frominame ]:
            try:
                c = conv(name)
                return c.alpha3, c.country
            except (ValueError, babelfish.ReverseError):
                pass

        try:
            return self.guessit_exceptions[name.lower()]
        except KeyError:
            pass

        raise babelfish.ReverseError(name)


ALL_NAMES = frozenset(c.lower() for c in GuessitConverter().codes)

babelfish.register_converter('iname', INameConverter)
babelfish.register_converter('guessit', GuessitConverter)


class Language(UnicodeMixin):
    """This class represents a human language.

    You can initialize it with pretty much anything, as it knows conversion
    from ISO-639 2-letter and 3-letter codes, English and French names.

    You can also distinguish languages for specific countries, such as
    Portuguese and Brazilian Portuguese.

    There are various properties on the language object that give you the
    representation of the language for a specific usage, such as .alpha3
    to get the ISO 3-letter code, or .opensubtitles to get the OpenSubtitles
    language code.

    >>> Language('fr')
    Language(French)

    >>> s(Language('eng').english_name)
    'english'

    >>> s(Language('pt(br)').country.english_name)
    'Brazil'

    >>> s(Language('Español (Latinoamérica)').country.english_name)
    'Latin America'

    >>> Language('Spanish (Latin America)') == Language('Español (Latinoamérica)')
    True

    >>> s(Language('zz', strict=False).english_name)
    'Undetermined'

    >>> s(Language('pt(br)').opensubtitles)
    'pob'
    """

    _with_country_regexp = re.compile('(.*)\((.*)\)')
    _with_country_regexp2 = re.compile('(.*)-(.*)')

    def __init__(self, language, country=None, strict=False, scheme=None):
        language = u(language.strip().lower())
        with_country = (Language._with_country_regexp.match(language) or
                        Language._with_country_regexp2.match(language))
        if with_country:
            self.lang = babelfish.Language.fromguessit(with_country.group(1)).alpha3
            self.country = babelfish.Country(with_country.group(2).upper())
            return

        self.lang = None
        self.country = babelfish.Country(country.upper()) if country else None

        try:
            self.lang = babelfish.Language.fromguessit(language)
        except babelfish.ReverseError:
            pass

        msg = 'The given string "%s" could not be identified as a language' % language

        if self.lang is None and strict:
            raise ValueError(msg)

        if self.lang is None:
            log.debug(msg)
            self.lang = UNDETERMINED

    @property
    def alpha2(self):
        return self.lang.alpha2

    @property
    def alpha3(self):
        return self.lang.alpha3

    @property
    def alpha3term(self):
        return self.lang.alpha3b

    @property
    def english_name(self):
        return self.lang.name

    @property
    def opensubtitles(self):
        if self.lang == 'por' and self.country and self.country.alpha2 == 'br':
            return 'pob'
        elif self.lang in ['gre', 'srp']:
            return self.alpha3term
        return self.alpha3

    @property
    def tmdb(self):
        if self.country:
            return '%s-%s' % (self.alpha2, self.country.alpha2.upper())
        return self.alpha2

    def __hash__(self):
        return hash(self.lang)

    def __eq__(self, other):
        if isinstance(other, Language):
            return self.lang == other.lang

        if isinstance(other, base_text_type):
            try:
                return self == Language(other)
            except ValueError:
                return False

        return False

    def __ne__(self, other):
        return not self == other

    def __nonzero__(self):
        return self.lang != UNDETERMINED

    def __unicode__(self):
        if self.country:
            return '%s(%s)' % (self.english_name, self.country.alpha2)
        else:
            return self.english_name

    def __repr__(self):
        if self.country:
            return 'Language(%s, country=%s)' % (self.english_name, self.country)
        else:
            return 'Language(%s)' % self.english_name



# list of common words which could be interpreted as languages, but which
# are far too common to be able to say they represent a language in the
# middle of a string (where they most likely carry their commmon meaning)
LNG_COMMON_WORDS = frozenset([
    # english words
    'is', 'it', 'am', 'mad', 'men', 'man', 'run', 'sin', 'st', 'to',
    'no', 'non', 'war', 'min', 'new', 'car', 'day', 'bad', 'bat', 'fan',
    'fry', 'cop', 'zen', 'gay', 'fat', 'cherokee', 'got', 'an', 'as',
    'cat', 'her', 'be', 'hat', 'sun', 'may', 'my', 'mr', 'rum', 'pi',
    # french words
    'bas', 'de', 'le', 'son', 'vo', 'vf', 'ne', 'ca', 'ce', 'et', 'que',
    'mal', 'est', 'vol', 'or', 'mon', 'se',
    # spanish words
    'la', 'el', 'del', 'por', 'mar',
    # other
    'ind', 'arw', 'ts', 'ii', 'bin', 'chan', 'ss', 'san', 'oss', 'iii',
    'vi', 'ben', 'da', 'lt', 'ch',
    # new from babelfish
    'mkv', 'avi', 'dmd', 'the', 'dis', 'cut', 'stv', 'des', 'dia', 'and',
    'cab', 'sub', 'mia', 'rim', 'las', 'une', 'par', 'srt', 'ano', 'toy',
    'job', 'gag', 'reel', 'www', 'for', 'ayu', 'csi', 'ren', 'moi', 'sur',
    'fer', 'fun', 'two', 'big', 'psy', 'air'
    ])

def search_language(string, lang_filter=None, skip=None):
    """Looks for language patterns, and if found return the language object,
    its group span and an associated confidence.

    you can specify a list of allowed languages using the lang_filter argument,
    as in lang_filter = [ 'fr', 'eng', 'spanish' ]

    >>> search_language('movie [en].avi')
    (Language(English), (7, 9), 0.8)

    >>> search_language('the zen fat cat and the gay mad men got a new fan', lang_filter = ['en', 'fr', 'es'])
    (None, None, None)
    """

    sep = r'[](){} \._-+'

    if lang_filter:
        lang_filter = set(babelfish.Language.fromguessit(lang) for lang in lang_filter)

    slow = ' %s ' % string.lower()
    confidence = 1.0 # for all of them

    for lang in (set(find_words(slow)) & ALL_NAMES) - LNG_COMMON_WORDS:
        pos = slow.find(lang)

        if pos != -1:
            end = pos + len(lang)

            # skip if span in in skip list
            while skip and (pos - 1, end - 1) in skip:
                pos = slow.find(lang, end)
                if pos == -1:
                    continue
                end = pos + len(lang)
            if pos == -1:
                continue

            # make sure our word is always surrounded by separators
            if slow[pos - 1] not in sep or slow[end] not in sep:
                continue

            language = Language(slow[pos:end])
            if lang_filter and language not in lang_filter:
                continue

            # only allow those languages that have a 2-letter code, those that
            # don't are too esoteric and probably false matches
            #if language.lang not in lng3_to_lng2:
            #    continue

            # confidence depends on alpha2, alpha3, english name, ...
            if len(lang) == 2:
                confidence = 0.8
            elif len(lang) == 3:
                confidence = 0.9
            else:
                # Note: we could either be really confident that we found a
                #       language or assume that full language names are too
                #       common words and lower their confidence accordingly
                confidence = 0.3 # going with the low-confidence route here

            return language, (pos - 1, end - 1), confidence

    return None, None, None


def guess_language(text):
    """Guess the language in which a body of text is written.

    This uses the external guess-language python module, and will fail and return
    Language(Undetermined) if it is not installed.
    """
    try:
        from guess_language import guessLanguage
        return babelfish.Language.fromguessit(guessLanguage(text))

    except ImportError:
        log.error('Cannot detect the language of the given text body, missing dependency: guess-language')
        log.error('Please install it from PyPI, by doing eg: pip install guess-language')
        return UNDETERMINED
