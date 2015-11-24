# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from collective.importexport.testing import COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING  # noqa
from plone import api

import unittest


class TestSetup(unittest.TestCase):
    """Test that collective.importexport is properly installed."""

    layer = COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if collective.importexport is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'collective.importexport'))

    def test_browserlayer(self):
        """Test that ICollectiveImportexportLayer is registered."""
        from collective.importexport.interfaces import (
            ICollectiveImportexportLayer)
        from plone.browserlayer import utils
        self.assertIn(ICollectiveImportexportLayer, utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')
        self.installer.uninstallProducts(['collective.importexport'])

    def test_product_uninstalled(self):
        """Test if collective.importexport is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'collective.importexport'))

    def test_browserlayer_removed(self):
        """Test that ICollectiveImportexportLayer is removed."""
        from collective.importexport.interfaces import ICollectiveImportexportLayer  # noqa
        from plone.browserlayer import utils
        self.assertNotIn(ICollectiveImportexportLayer, utils.registered_layers())  # noqa
