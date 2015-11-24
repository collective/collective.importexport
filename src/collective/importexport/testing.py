# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import collective.importexport


class CollectiveImportexportLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=collective.importexport)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'collective.importexport:default')


COLLECTIVE_IMPORTEXPORT_FIXTURE = CollectiveImportexportLayer()


COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING = IntegrationTesting(
    bases=(COLLECTIVE_IMPORTEXPORT_FIXTURE,),
    name='CollectiveImportexportLayer:IntegrationTesting'
)


COLLECTIVE_IMPORTEXPORT_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_IMPORTEXPORT_FIXTURE,),
    name='CollectiveImportexportLayer:FunctionalTesting'
)


COLLECTIVE_IMPORTEXPORT_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        COLLECTIVE_IMPORTEXPORT_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE
    ),
    name='CollectiveImportexportLayer:AcceptanceTesting'
)
