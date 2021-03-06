# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for qutebrowser.commands.argparser."""

import inspect

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.commands import argparser, cmdexc
from qutebrowser.utils import usertypes, objreg


Enum = usertypes.enum('Enum', ['foo', 'foo_bar'])


class FakeTabbedBrowser:

    def __init__(self):
        self.opened_url = None

    def tabopen(self, url):
        self.opened_url = url


class TestArgumentParser:

    @pytest.fixture
    def parser(self):
        return argparser.ArgumentParser('foo')

    @pytest.yield_fixture
    def tabbed_browser(self, win_registry):
        tb = FakeTabbedBrowser()
        objreg.register('tabbed-browser', tb, scope='window', window=0)
        yield tb
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_name(self, parser):
        assert parser.name == 'foo'

    def test_exit(self, parser):
        parser.add_argument('--help', action='help')

        with pytest.raises(argparser.ArgumentParserExit) as excinfo:
            parser.parse_args(['--help'])

        assert excinfo.value.status == 0

    def test_error(self, parser):
        with pytest.raises(argparser.ArgumentParserError) as excinfo:
            parser.parse_args(['--foo'])
        assert str(excinfo.value) == "Unrecognized arguments: --foo"

    def test_help(self, parser, tabbed_browser):
        parser.add_argument('--help', action=argparser.HelpAction, nargs=0)

        with pytest.raises(argparser.ArgumentParserExit):
            parser.parse_args(['--help'])

        expected_url = QUrl('qute://help/commands.html#foo')
        assert tabbed_browser.opened_url == expected_url


@pytest.mark.parametrize('types, value, expected', [
    ([Enum], 'foo', Enum.foo),
    ([Enum], 'foo-bar', Enum.foo_bar),

    ([int], '2', 2),
    ([int, str], 'foo', 'foo'),
])
@pytest.mark.parametrize('multi', [True, False])
def test_type_conv_valid(types, value, expected, multi):
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)

    if multi:
        assert argparser.multitype_conv(param, types, value) == expected
    elif len(types) == 1:
        assert argparser.type_conv(param, types[0], value) == expected


@pytest.mark.parametrize('typ, value', [
    (Enum, 'blubb'),
    (Enum, 'foo_bar'),
    (int, '2.5'),
    (int, 'foo'),
])
@pytest.mark.parametrize('multi', [True, False])
def test_type_conv_invalid(typ, value, multi):
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)

    with pytest.raises(cmdexc.ArgumentTypeError) as excinfo:
        if multi:
            argparser.multitype_conv(param, [typ], value)
        else:
            argparser.type_conv(param, typ, value)

    if multi:
        msg = 'foo: Invalid value {}'.format(value)
    elif typ is Enum:
        msg = ('foo: Invalid value {} - expected one of: foo, '
               'foo-bar'.format(value))
    else:
        msg = 'foo: Invalid {} value {}'.format(typ.__name__, value)
    assert str(excinfo.value) == msg


def test_multitype_conv_invalid_type():
    """Test using an invalid type with a multitype converter."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(ValueError) as excinfo:
        argparser.multitype_conv(param, [None], '')
    assert str(excinfo.value) == "foo: Unknown type None!"


@pytest.mark.parametrize('value, typ', [(None, None), (42, int)])
def test_conv_default_param(value, typ):
    """The default value should always be a valid choice."""
    def func(foo=value):
        pass
    param = inspect.signature(func).parameters['foo']
    assert argparser.type_conv(param, typ, value, str_choices=['val']) == value


def test_conv_str_type():
    """Using a str literal as type used to mean exactly that's a valid value.

    This got replaced by @cmdutils.argument(..., choices=...), so we make sure
    no string annotations are there anymore.
    """
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(TypeError) as excinfo:
        argparser.type_conv(param, 'val', None)
    assert str(excinfo.value) == 'foo: Legacy string type!'


def test_conv_str_choices_valid():
    """Calling str type with str_choices and valid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    converted = argparser.type_conv(param, str, 'val1',
                                    str_choices=['val1', 'val2'])
    assert converted == 'val1'


def test_conv_str_choices_invalid():
    """Calling str type with str_choices and invalid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(cmdexc.ArgumentTypeError) as excinfo:
        argparser.type_conv(param, str, 'val3', str_choices=['val1', 'val2'])
    msg = 'foo: Invalid value val3 - expected one of: val1, val2'
    assert str(excinfo.value) == msg
