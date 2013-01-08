import unittest2 as unittest
from hejasverige.api.testing import HEJASVERIGE_API_INTEGRATION_TESTING


class TestSetup(unittest.TestCase):
    layer = HEJASVERIGE_API_INTEGRATION_TESTING

    def test_role_added(self):
        portal = self.layer['portal']
        self.assertTrue("HejaSverigeAPIMember" in portal.validRoles())

    def test_view_permission_for_hejasverigeapimember(self):
        portal = self.layer['portal']
        self.assertTrue('View' in [r['name']
            for r in portal.permissionsOfRole('Reader')
            if r['selected']])
        self.assertTrue('View' in [r['name']
            for r in portal.permissionsOfRole('HejaSverigeAPIMember')
            if r['selected']])

    def test_hejasverigeapi_group_added(self):
        portal = self.layer['portal']
        acl_users = portal['acl_users']
        self.assertEqual(1,
            len(acl_users.searchGroups(name='HejaSverigeAPI')))

    def test_api_view_permission_for_hejasverigeapimember(self):
        portal = self.layer['portal']
        self.assertTrue('HejaSverige: API View' in [r['name'] 
            for r in portal.permissionsOfRole('HejaSverigeAPIMember') 
            if r['selected']])
