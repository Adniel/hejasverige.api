from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from zope.configuration import xmlconfig
from plone.testing import z2


class HejaSverigeAPI(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # Load ZCML
        import hejasverige.api
        xmlconfig.file('configure.zcml',
                       hejasverige.api,
                       context=configurationContext
                       )
        z2.installProduct(app, 'plone.api')

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'plone.api')

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'hejasverige.api:default')

HEJASVERIGE_API_FIXTURE = HejaSverigeAPI()
HEJASVERIGE_API_INTEGRATION_TESTING = IntegrationTesting(
    bases=(HEJASVERIGE_API_FIXTURE,),
    name="HejaSverige:Integration")
