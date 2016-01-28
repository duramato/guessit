#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API functions that can be used by external software
"""
try:
    from collections import OrderedDict
except ImportError:  # pragma: no-cover
    from ordereddict import OrderedDict  # pylint:disable=import-error

import six

from rebulk.introspector import introspect

from .rules import rebulk_builder
from .options import parse_options


def guessit(string, options=None):
    """
    Retrieves all matches from string as a dict
    :param string: the filename or release name
    :type string: str
    :param options: the filename or release name
    :type options: str|dict
    :return:
    :rtype:
    """
    return default_api.guessit(string, options)


def properties(options=None):
    """
    Retrieves all properties with possible values that can be guessed
    :param options:
    :type options:
    :return:
    :rtype:
    """
    return default_api.properties(options)


class GuessItApi(object):
    """
    An api class that can be configured with custom Rebulk configuration.
    """

    def __init__(self, rebulk):
        """
        :param rebulk: Rebulk instance to use.
        :type rebulk: Rebulk
        :return:
        :rtype:
        """
        self.rebulk = rebulk

    def guessit(self, string, options=None):
        """
        Retrieves all matches from string as a dict
        :param string: the filename or release name
        :type string: str
        :param options: the filename or release name
        :type options: str|dict
        :return:
        :rtype:
        """
        options = parse_options(options)
        result_decode = False
        result_encode = False
        if six.PY2 and isinstance(string, six.text_type):
            string = string.encode("latin-1")
            result_decode = True
        if six.PY3 and isinstance(string, six.binary_type):
            string = string.decode('ascii')
            result_encode = True
        matches = self.rebulk.matches(string, options)
        if result_decode:
            for match in matches:
                if isinstance(match.value, six.binary_type):
                    match.value = match.value.decode("latin-1")
        if result_encode:
            for match in matches:
                if isinstance(match.value, six.text_type):
                    match.value = match.value.encode("ascii")
        return matches.to_dict(options.get('advanced', False), options.get('implicit', False))

    def properties(self, options=None):
        """
        Grab properties and values that can be generated.
        :param options:
        :type options:
        :return:
        :rtype:
        """
        unordered = introspect(self.rebulk, options).properties
        ordered = OrderedDict()
        for k in sorted(unordered.keys(), key=six.text_type):
            ordered[k] = list(sorted(unordered[k], key=six.text_type))
        return ordered


default_api = GuessItApi(rebulk_builder())
