# -*- coding: utf-8 -*-

from Products.CMFCore.interfaces import ISiteRoot
from five import grok
import json
from plone import api
from Products.CMFCore.utils import getToolByName
from plone.app.uuid.utils import uuidToObject
from hejasverige.content.person import IRelation, IPerson


class ListUsersView2(grok.View):

    """ Lists all available users and corresponding
    """

    grok.context(ISiteRoot)
    grok.name('list-users-2')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def get_clubs_from_relations(self, path):
        catalog = getToolByName(self.context, 'portal_catalog')

        clubs = [dict(clubobj=uuidToObject(relation.getObject().foreign_id),
                 relation=relation)
                 for relation in
                 catalog({'object_provides': IRelation.__identifier__,
                 'path': dict(query=path,),
                 'sort_on': 'sortable_title'})]

        clubs = [x for x in clubs if x]

        return clubs

    def list_user_clubs(self, user):
        club_list = []
        # find all clubs for specified user
        # should use field data from brain instead of from the object
        #import pdb; pdb.set_trace()

        #mship = getToolByName(self.context, 'portal_membership')
        portal_url_tool = getToolByName(self, "portal_url")
        portal = portal_url_tool.getPortalObject()
        #portal_url = portal.portal_url()
        portal_path = '/'.join(portal.getPhysicalPath())
        club_path = '/'.join((portal_path, 'Members', str(user), 'my-clubs'))
        clubs = self.get_clubs_from_relations(club_path)

        #catalog = getToolByName(self.context, 'portal_catalog')

        #clubs = [dict(clubobj=uuidToObject(relation.getObject().foreign_id),
        #        relation=relation)
        #        for relation in
        #        catalog({'object_provides': IRelation.__identifier__,
        #        'path': dict(query=club_path,),
        #        'sort_on': 'sortable_title'})]

        #clubs = [x for x in clubs if x]
        for club in clubs:
            club_list.append(dict(groupid=club.get('clubobj').clubId, name=club.get('clubobj').title, orgnr=club.get('clubobj').VatNo))

        return club_list

    def create_user_record(self, user, group_list):
        user_record = {
                       'username': str(user),
                       'email': user.getProperty('email'),
                       'fullname': user.getProperty('fullname'),
                       'personal_id': user.getProperty('personal_id'),
                       'kollkoll': user.getProperty('kollkoll'),
                       'groups': group_list, }
        return user_record

    def merge_lists(l1, l2, key):
        merged = {}
        for item in l1 + l2:
            if item[key] in merged:
                merged[item[key]].update(item)
            else:
                merged[item[key]] = item
        return [val for (_, val) in merged.items()]

    #@memoize
    def persons(self):
        """Get all persons (not users, but persons connected with users).
        """

        catalog = getToolByName(self.context, 'portal_catalog')

        retu = [dict(name=person.Title,
               personal_id=person.personal_id) for person in 
               catalog({'object_provides': IPerson.__identifier__,
               'sort_on': 'sortable_title'})]

        # remove persons without personal id
        retu = [x for x in retu if x['personal_id']]

        # merge persons with same personal id
        # TODO: merge clubs in each merged person
        merged = {}
        for person in retu:
            if person.get('personal_id') in merged:
                merged[person.get('personal_id')].update(person)
            else:
                merged[person.get('personal_id')] = person
        return [val for (_, val) in merged.items()]

    def render(self):
        # Prepare response
        userid = self.request.form.get('userid', '')
        personalid = self.request.form.get('personalid', '')

        data = []

        # get users
        if userid != '':
            user = api.user.get(username=userid)
            if user is None:
                data.append({'Error': 'No user with id ' + userid
                            + ' available', 'ErrorId': '4'})
            else:
                group_list = self.list_user_clubs(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)

        elif personalid != '':

            # # might be unefficient. Possibly filter better.
            users = api.user.get_users()
            for user in users:
                if personalid == user.getProperty('personal_id'):
                    group_list = self.list_user_clubs(user)
                    user_record = self.create_user_record(user, group_list)
                    data.append(user_record)

            if not data:
                data.append({'Error': 'No user with personal_id ' + personalid
                            + ' available', 'ErrorId': '5'})
        else:
            #import pdb; pdb.set_trace()
            users = api.user.get_users()
            for user in users:
                group_list = self.list_user_clubs(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)

        # get persons
        persons = self.persons()
        for person in persons:
                person['groups'] = [x for x in self.get_clubs_from_relations()]
                data.append(person)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


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
                            'orgnr': group.getProperty('orgnr'),
                            }
            if group.getProperty('is_association'):
                group_list.append(group_record)
        return group_list

    def create_user_record(self, user, group_list):
        user_record = {
                        'username': str(user),
                        'email': user.getProperty('email'),
                        'fullname': user.getProperty('fullname'),
                        'personal_id': user.getProperty('personal_id'),
                        'kollkoll': user.getProperty('kollkoll'),
                        'groups': group_list,
                        }
        return user_record

    def render(self):
        # Prepare response
        userid = self.request.form.get('userid', '')
        personalid = self.request.form.get('personalid', '')

        data = []

        if userid != '':
            user = api.user.get(username=userid)
            if user is None:
                data.append({'Error': 'No user with id ' + userid
                            + ' available', 'ErrorId': '4'})
            else:
                group_list = self.list_user_groups(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)

        elif personalid != '':

            # # might be unefficient. Possibly filter better.
            users = api.user.get_users()
            for user in users:
                if personalid == user.getProperty('personal_id'):
                    group_list = self.list_user_groups(user)
                    user_record = self.create_user_record(user, group_list)
                    data.append(user_record)

            if not data:
                data.append({'Error': 'No user with personal_id ' + personalid
                            + ' available', 'ErrorId': '5'})
        else:
            users = api.user.get_users()
            for user in users:
                group_list = self.list_user_groups(user)
                user_record = self.create_user_record(user, group_list)
                data.append(user_record)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


class ListAssociasionsView(grok.View):

    """ Lists all available associations
    """

    grok.context(ISiteRoot)
    grok.name('list-associations')
    grok.require('hejasverige.ApiView')

    def render(self):
        data = []
        groups = api.group.get_groups()
        #import pdb
        #pdb.set_trace()
        for group in groups:
            if group.getProperty('is_association'):
                group_record = {'groupId': str(group),
                                'name': group.getProperty('title'),
                                'orgnr': group.getProperty('orgnr'),
                                #'is_association': group.getProperty('is_association'),
                                }
                data.append(group_record)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)


class ListUsersByAssociation(grok.View):

    """ Lists all users in a specific Assiciasion
        http://<host>:<port>/<site>/@@list-users-by-associasion?id=<id>

        The id should be provided, not the name
    """

    grok.context(ISiteRoot)
    grok.name('list-users-by-association')
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
                    user_record = {
                        'username': str(user),
                        'email': user.getProperty('email'),
                        'fullname': user.getProperty('fullname'),
                        'personal_id': user.getProperty('personal_id'),
                        }
                    data.append(user_record)
            else:
                data.append({'Error': 'No association with id ' + group_name
                            + ' available', 'ErrorId': '1'})
        except KeyError:
            data.append({'Error': 'No association id provided. Syntax: http://'
                         + self.request['SERVER_URL']
                        + self.request['PATH_INFO'] + '?id=<id>',
                        'ErrorId': '2'})

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
        logger = logging.getLogger('@@check-user-account')
        logger.info('Check user account (' + str(user) + ')')
        logger.info('Calling MegaBank')
        logger.info('User: ' + mbuser)
        logger.info('Password: ' + mbpassword)
        logger.info('Url: ' + mburl)

        # data = json.dumps({u'user': str(user), u'amount': amount})

        auth = HTTPBasicAuth(mbuser, mbpassword)

        # http://swedwise.no-ip.org/BankAPI/BankAPI.BankService.svc/accounts/check/7810095039/?amount=100.00
        # r = requests.post(mburl + '/accounts/check/7810095039/?amount=' + amount, data=data, auth=auth)
        r = requests.get(mburl + '/accounts/check/' + str(user) + '/?amount='
                         + amount, auth=auth)

        logger.info('Response: ' + r.text)

        if r.text == 'true':
            return True
        else:
            return False

    def render(self):
        data = []
        import logging
        logger = logging.getLogger('@@check-user-account')
        logger.info('Rendering check-user-account')

        try:
            user_personal_code = self.request['pc']
            amount = self.request['amount']
            users = api.user.get_users()
            user_found = False
            logger.info('Found pc: ' + user_personal_code)
            logger.info('Found amount: ' + amount)

            for user in users:
                # if user.getProperty('personal_code') is user_personal_code:
                logger.info('Investigating user: ' + str(user))
                if str(user) == user_personal_code:
                    logger.info('Found user: ' + str(user))
                    data.append({'Result': self.CheckUserAccount(user,
                                amount)})
                    user_found = True

            if not user_found:
                data.append({'Error': 'No user with personal code '
                            + user_personal_code + ' found', 'ErrorId': '3'})
        except KeyError:
            data.append({'Error': 'No personal code provided. Syntax: http://'
                        + self.request['SERVER_URL'] + self.request['PATH_INFO'
                        ] + '?pc=<personal code>', 'ErrorId': '3'})

        self.request.response.setHeader('Content-Type', 'application/json')
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
