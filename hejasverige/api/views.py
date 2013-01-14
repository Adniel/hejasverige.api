
# Zope imports
# View is registered in portal root only
from Products.CMFCore.interfaces import ISiteRoot
from five import grok
#import csv
#from Acquisition import aq_inner
#from StringIO import StringIO
import json
#from plone.directives import form
#from hejasverige.api import HejaSverigeApiMessageFactory as _
from plone import api

# Add ListMerchants view
# 

class ListUsersView(grok.View):
    """ Lists all available users and corresponding
    """
    grok.context(ISiteRoot)
    grok.name('list-users')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def list_user_groups(self, user):
        groups = api.group.get_groups(user=user)
        group_list = []
        for group in groups:
            group_record = {'groupid': str(group),
                            'name': group.getProperty('title'),
                            }
            if group.getProperty('is_association'):
                group_list.append(group_record)
        return group_list

    def create_user_record(self, user, group_list):
        user_record = {'username': str(user),
                       'email': user.getProperty('email'),
                       'fullname': user.getProperty('fullname'),
                       'groups': group_list, }
        return user_record

    def render(self):
        # Prepare response
        userid = self.request.form.get('userid', '')
        data = []

        if userid != '':
            user = api.user.get(username=userid)
            if user is None:
                data.append({'Error': 'No user with id ' + userid + ' available', 'ErrorId': '4'})
            else:
                group_list = self.list_user_groups(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)
        else:
            users = api.user.get_users()
            for user in users:
                group_list = self.list_user_groups(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


class ListAssociasionsView(grok.View):
    """ Lists all available associasions
    """
    grok.context(ISiteRoot)
    grok.name('list-associasions')
    grok.require('hejasverige.ApiView')

    def render(self):
        data = []
        groups = api.group.get_groups()
        for group in groups:
            if group.getProperty('is_association'):
                group_record = {'groupId': str(group), 'name': group.getProperty('title')}
                data.append(group_record)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


class ListUsersByAssociasion(grok.View):
    """ Lists all users in a specific Assiciasion
        http://<host>:<port>/<site>/@@list-users-by-associasion?id=<id>

        The id should be provided, not the name
    """

    grok.context(ISiteRoot)
    grok.name('list-users-by-associasion')
    grok.require('hejasverige.ApiView')

    def render(self):
        data = []

        try:
            group_name = self.request.form.get('id', '')
            group = api.group.get(groupname=group_name)
            print str(group)
            if group is not None and group.getProperty('is_association'):
                users = api.user.get_users(groupname=group_name)
                for user in users:
                    user_record = {'username': str(user),
                                   'email': user.getProperty('email'),
                                   'fullname': user.getProperty('fullname'), }
                    data.append(user_record)
            else:
                data.append({'Error': 'No associasion with id ' + group_name + ' available', 'ErrorId': '1'})
        except KeyError:
            data.append({'Error': 'No associasion id provided. Syntax: http://'+ self.request["SERVER_URL"] + self.request["PATH_INFO"] + '?id=<id>', 'ErrorId': '2'})

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


class CheckUserAccountView(grok.View):
    """ Checks if an amount can be reserved from a specific user CheckUserAccount
    """
    grok.context(ISiteRoot)
    grok.name('check-user-account')
    grok.require('hejasverige.ApiView')

    def CheckUserAccount(self, user, amount):
        '''
        >>> from zope.component import getUtility
        >>> from plone.registry.interfaces import IRegistry

        >>> registry = getUtility(IRegistry)
        Now we fetch the HejaSverigeSetting registry

        >>> from hejasverige.settings.interfaces import IHejaSverigeSettings
        >>> settings = registry.forInterface(IHejaSverigeSettings)
        And now we can access the values

        >>> self.settings.megabank_url
        >>> ''
        >>> self.settings.megabank_user
        >>> ''        
        >>> self.settings.megabank_password
        >>> ''        
        '''

        import requests
        from requests.auth import HTTPBasicAuth
        from zope.component import getUtility
        from plone.registry.interfaces import IRegistry
        registry = getUtility(IRegistry)

        from hejasverige.settings.interfaces import IHejaSverigeSettings
        settings = registry.forInterface(IHejaSverigeSettings)
        mburl = settings.megabank_url
        mbuser = settings.megabank_user
        mbpassword = settings.megabank_password
        

        import logging
        logger = logging.getLogger("@@check-user-account")
        logger.info('Check user account (' + str(user) + ')')
        logger.info('Calling MegaBank')
        logger.info('User: ' + mbuser)
        logger.info('Password: ' + mbpassword)
        logger.info('Url: ' + mburl)

        #data = json.dumps({u'user': str(user), u'amount': amount})

        auth = HTTPBasicAuth(mbuser, mbpassword)

        # http://swedwise.no-ip.org/BankAPI/BankAPI.BankService.svc/accounts/check/7810095039/?amount=100.00       
        #r = requests.post(mburl + '/accounts/check/7810095039/?amount=' + amount, data=data, auth=auth)
        r = requests.get(mburl + '/accounts/check/' + str(user) + '/?amount=' + amount, auth=auth)

        logger.info('Response: ' + r.text)

        if r.text == 'true':
            return True
        else:
            return False

    def render(self):
        data = []
        import logging
        logger = logging.getLogger("@@check-user-account")
        logger.info("Rendering check-user-account")

        try:
            user_personal_code = self.request['pc']
            amount = self.request['amount']
            users = api.user.get_users()
            user_found = False
            logger.info("Found pc: " + user_personal_code)
            logger.info("Found amount: " + amount)

            for user in users:
                #if user.getProperty('personal_code') is user_personal_code:
                logger.info("Investigating user: " + str(user))
                if str(user) == user_personal_code:
                    logger.info("Found user: " + str(user))
                    data.append({'Result': self.CheckUserAccount(user, amount)})
                    user_found = True
            
            if not user_found:
                data.append({'Error': 'No user with personal code ' + user_personal_code + ' found', 'ErrorId': '3'})
        except KeyError:
            data.append({'Error': 'No personal code provided. Syntax: http://'+ self.request["SERVER_URL"] + self.request["PATH_INFO"] + '?pc=<personal code>', 'ErrorId': '3'})

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)

# list-merchants
#   filter by POS
#   list all pos possessed by the merchant
class ListMerchantsView(grok.View):
    grok.context(ISiteRoot)
    grok.name('list-merchants')
    grok.require('zope2.View')

    def render(self):
        data = []
        pos_serial = self.request.form.get('pos_serial', '')
        if pos_serial != '':
            pass
        else:
            pass

        pos_list = []

        pos_record = {'pos_serial': '1234'}
        pos_list.append(pos_record)

        pos_record = {'pos_serial': '1235'}
        pos_list.append(pos_record)


        merchant_record = {'corporate_id': '5555555555',
                       'name': 'TestMerchant',
                       'customer_id': '12345',
                       'poses': pos_list, }
        if pos_serial != '':
            if pos_serial in pos_list:
                data.append(merchant_record)
        else:
            data.append(merchant_record)

        return json.dumps(data)

    

class TestView(grok.View):
    grok.context(ISiteRoot)
    grok.name('test-view')
    grok.require('zope2.View')

    def render(self):
        hej = self.request.form.get('hej', '')
        if hej != '':
            return 'Is in and contains: ' + hej
        else:
            return self.request.items()
    #    if self.request['method'] == 'GET' and 'hej' in self.request['QUERY_STRING']:
    #        if self.request['hej'] is not None and self.request['hej'] != '':
    #            return self.request["hej"]
    #        else:
    #            return self.request.items()
