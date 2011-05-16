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

import json
import datetime
import logging

log = logging.getLogger("guessit.guess")


class Guess(dict):
    """A Guess is a dictionary which has an associated confidence for each of its values.

    As it is a subclass of dict, you can use it everywhere you expect a simple dict"""
    def __init__(self, *args, **kwargs):
        try:
            confidence = kwargs.pop('confidence')
        except KeyError:
            confidence = 0

        dict.__init__(self, *args, **kwargs)

        self._confidence = {}
        for prop in self:
            self._confidence[prop] = confidence

    def to_json(self):
        """NB: this doesn't return a valid json, maybe it should be renamed..."""
        from guessit.language import Language
        data = dict(self)
        for prop, value in data.items():
            if isinstance(value, datetime.date):
                data[prop] = value.isoformat()
            elif isinstance(value, Language):
                data[prop] = str(value)
            elif isinstance(value, list):
                data[prop] = [ str(x) for x in value ]

        parts = json.dumps(data, indent = 4).split('\n')
        for i, p in enumerate(parts):
            if p[:5] != '    "':
                continue

            prop = p.split('"')[1]
            parts[i] = ('    [%.2f] "' % (self._confidence.get(prop) or -1)) + p[5:]

        return '\n'.join(parts)

    def confidence(self, prop):
        return self._confidence[prop]

    def set(self, prop, value, confidence = None):
        self[prop] = value
        if confidence is not None:
            self._confidence[prop] = confidence

    def set_confidence(self, prop, value):
        self._confidence[prop] = value

    def update(self, other, confidence = None):
        dict.update(self, other)
        if isinstance(other, Guess):
            for prop in other:
                self._confidence[prop] = other.confidence(prop)

        if confidence is not None:
            for prop in other:
                self._confidence[prop] = confidence

    def update_highest_confidence(self, other):
        """Update this guess with the values from the given one. In case there is
        property present in both, only the one with the highest one is kept."""
        if not isinstance(other, Guess):
            raise ValueError, 'Can only call this function on Guess instances'

        for prop in other:
            if prop in self and self._confidence[prop] >= other._confidence[prop]:
                continue
            self[prop] = other[prop]
            self._confidence[prop] = other._confidence[prop]




def choose_int(g1, g2):
    """Function used by merge_similar_guesses to choose between 2 possible properties
    when they are integers."""
    v1, c1 = g1 # value, confidence
    v2, c2 = g2
    if (v1 == v2):
        return (v1, 1 - (1-c1)*(1-c2))
    else:
        if c1 > c2:
            return (v1, c1 - c2)
        else:
            return (v2, c2 - c1)

def choose_string(g1, g2):
    """Function used by merge_similar_guesses to choose between 2 possible properties
    when they are strings."""
    v1, c1 = g1 # value, confidence
    v2, c2 = g2
    v1, v2 = v1.strip(), v2.strip()
    v1l, v2l = v1.lower(), v2.lower()

    combined_prob = 1 - (1-c1)*(1-c2)

    if v1l == v2l:
        return (v1, combined_prob)

    # check for common patterns
    elif v1l == 'the ' + v2l:
        return (v1, combined_prob)
    elif v2l == 'the ' + v1l:
        return (v2, combined_prob)

    # if one string is contained in the other, return the shortest one
    elif v2l in v1l:
        return (v2, combined_prob)
    elif v1l in v2l:
        return (v1, combined_prob)

    # in case of conflict, return the one with highest priority
    else:
        if c1 > c2:
            return (v1, c1 - c2)
        else:
            return (v2, c2 - c1)


def _merge_similar_guesses_nocheck(guesses, prop, choose):
    """Take a list of guesses and merge those which have the same properties,
    increasing or decreasing the confidence depending on whether their values
    are similar.

    This function assumes there are at least 2 valid guesses."""

    similar = [ guess for guess in guesses if prop in guess ]

    g1, g2 = similar[0], similar[1]

    if len(set(g1) & set(g2)) > 1:
        log.warning('both guesses to be merged have more than one property in common, bailing out...')
        return

    # merge all props of s2 into s1, updating the confidence for the considered property
    v1, v2 = g1[prop], g2[prop]
    c1, c2 = g1.confidence(prop), g2.confidence(prop)

    new_value, new_confidence = choose((v1, c1), (v2, c2))
    if new_confidence >= c1:
        log.debug("Updating matching property '%s' with confidence %.2f" % (prop, new_confidence))
    else:
        log.debug("Updating non-matching property '%s' with confidence %.2f" % (prop, new_confidence))

    g2[prop] = new_value
    g2.set_confidence(prop, new_confidence)

    g1.update(g2)
    guesses.remove(g2)

def merge_similar_guesses(guesses, prop, choose):
    """Take a list of guesses and merge those which have the same properties,
    increasing or decreasing the confidence depending on whether their values
    are similar."""

    similar = [ guess for guess in guesses if prop in guess ]
    if len(similar) < 2:
        # nothing to merge
        return

    if len(similar) == 2:
        _merge_similar_guesses_nocheck(guesses, prop, choose)

    if len(similar) > 2:
        log.debug('complex merge, trying our best...')
        _merge_similar_guesses_nocheck(guesses, prop, choose)
        merge_similar_guesses(guesses, prop, choose)
        return


def merge_append_guesses(guesses, prop):
    """Take a list of guesses and merge those which have the same properties by
    appending them in a list."""

    similar = [ guess for guess in guesses if prop in guess ]
    if not similar:
        return

    merged = similar[0]
    merged[prop] = [ merged[prop] ]
    # TODO: what to do with global confidence? mean of them all?

    for m in similar[1:]:
        for prop2 in m:
            if prop == prop2:
                merged[prop].append(m[prop])
            else:
                if prop2 in m:
                    log.warning('overwriting property "%s" with value ' % (prop2, m[prop2]))
                merged[prop2] = m[prop2]
                # TODO: confidence also

        guesses.remove(m)


def merge_all(guesses, append = []):
    """Merges all the guesses in a single result, removes very unlikely values, and returns it.
    You can specify a list of properties that should be appended into a list instead of being
    merged.

    >>> merge_all([ Guess({ 'season': 2 }, confidence = 0.6),
    ...             Guess({ 'episodeNumber': 13 }, confidence = 0.8) ])
    {'season': 2, 'episodeNumber': 13}

    >>> merge_all([ Guess({ 'episodeNumber': 27 }, confidence = 0.02),
    ...             Guess({ 'season': 1 }, confidence = 0.2) ])
    {'season': 1}

    """
    if not guesses:
        return Guess()

    result = guesses[0]

    for g in guesses[1:]:
        # first append our appendable properties
        for prop in append:
            if prop in g:
                result.set(prop, result.get(prop, []) + [ g[prop] ],
                           # TODO: what to do with confidence here? maybe an arithmetic mean...
                           confidence = g.confidence(prop))

                del g[prop]

        # then merge the remaining ones
        if set(result) & set(g):
            log.warning('duplicate properties %s in merged result...' % (set(result) & set(g)))

        result.update_highest_confidence(g)

    # delete very unlikely values
    for p in result.keys():
        if result.confidence(p) < 0.05:
            del result[p]

    # make sure our appendable properties contain unique values
    for prop in append:
        if prop in result:
            result[prop] = list(set(result[prop]))

    return result

