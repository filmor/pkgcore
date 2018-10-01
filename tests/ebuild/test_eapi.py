# Copyright: 2018 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD

from importlib import reload
from unittest import mock

from pkgcore.ebuild import eapi
from pkgcore.ebuild.eapi import (
    EAPI, get_eapi,
    eapi0, eapi1, eapi2, eapi3, eapi4, eapi5, eapi6, eapi7)

import pytest


def test_get_eapi():
    # unknown EAPI
    unknown_eapi = get_eapi("unknown")
    assert unknown_eapi in EAPI.unknown_eapis.values()
    # check that unknown EAPI is now registered as an unknown
    assert unknown_eapi == get_eapi("unknown")

    # known EAPI
    eapi = get_eapi("6")
    assert eapi6 == eapi


class TestEAPI(object):

    def setup_method(self, method):
        # keep registered EAPIs consistent between methods
        reload(eapi)

    def test_register(self):
        # re-register known EAPI
        with pytest.raises(ValueError):
            EAPI.register(magic="0")

        with mock.patch('pkgcore.ebuild.eapi.bash_version') as bash_version:
            # inadequate bash version
            bash_version.return_value = '3.1'
            with pytest.raises(SystemExit) as excinfo:
                new_eapi = EAPI.register(magic='new', optionals={'bash_compat': '3.2'})
            assert 'EAPI new requires >=bash-3.2, system version: 3.1' == excinfo.value.args[0]

            # adequate system bash versions
            bash_version.return_value = '3.2'
            test_eapi = EAPI.register(magic='test', optionals={'bash_compat': '3.2'})
            assert test_eapi._magic == 'test'
            bash_version.return_value = '4.2'
            test_eapi = EAPI.register(magic='test1', optionals={'bash_compat': '4.1'})
            assert test_eapi._magic == 'test1'

    def test_is_supported(self):
        assert eapi6.is_supported

        # partially supported EAPI is flagged as such
        test_eapi = EAPI.register("test", optionals={'is_supported': False})
        assert not test_eapi.is_supported

        # unsupported/unknown EAPI is flagged as such
        unknown_eapi = get_eapi("blah")
        assert not unknown_eapi.is_supported

    def test_inherits(self):
        assert list(eapi0.inherits) == [eapi0]
        assert list(eapi7.inherits) == [eapi7, eapi6, eapi5, eapi4, eapi3, eapi2, eapi1, eapi0]

    def test_get_ebd_env(self):
        assert eapi0.get_ebd_env()['EAPI'] == '0'