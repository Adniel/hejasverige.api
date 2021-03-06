import logging
from Products.CMFCore.utils import getToolByName


def setupGroups(portal, logger=None):
    if logger:
        logger.info("Setting up group HejaSverigeAPI as HejaSverigeAPIMember")
    acl_users = getToolByName(portal, 'acl_users')
    if not acl_users.searchGroups(name='HejaSverigeAPI'):
        gtool = getToolByName(portal, 'portal_groups')
        gtool.addGroup('HejaSverigeAPI', roles=['HejaSverigeAPIMember'])


#   Move to hejasverige.content
def addProperty(tool, id, value, type, logger=None):
    if not tool.hasProperty(id):
        if logger:
            logger.info("Property " + id + " not found. Creating property...")
        tool.manage_addProperty(id, value, type)


#   Move to hejasverige.content
def addGroupProperties(portal, logger=None):
    """ Adds a group property
        Group properties can be found ad
        http://localhost:8080/plone/portal_groupdata/manage_addProperty
    """
    if logger:
        logger.info("Adding HejaSverige Group Properties")
    portal_groupdata = getToolByName(portal, 'portal_groupdata')
    addProperty(portal_groupdata, 'orgnr', '', 'string', logger)
    addProperty(portal_groupdata, 'is_association', '', 'boolean', logger)


def importVarious(context):
    """Miscellanous steps import handle
    """
    #print "Importing group info for HejaSverige API"
    if context.readDataFile('hejasverige.api-various.txt') is None:
        #print "No file called hejasverige.api-various.txt available"
        return
    logger = logging.getLogger('hejasverige.api')
    portal = context.getSite()
    setupGroups(portal, logger)

#   Move to hejasverige.content
    addGroupProperties(portal, logger)
