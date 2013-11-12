# -*- coding: utf-8 -*-

from Products.CMFCore.interfaces import ISiteRoot
from five import grok
import json
import datetime
from plone import api
from Products.CMFCore.utils import getToolByName
from plone.app.uuid.utils import uuidToObject
from hejasverige.content.person import IRelation, IPerson
from hejasverige.content.sports import IClub
from hejasverige.content.eventsubscribers import _getFolder

import logging
logger = logging.getLogger(__name__)



class GetMembers(grok.View):
    """ Lists all available recipients and corresponding associasions
    """

    grok.context(ISiteRoot)
    grok.name('get-members')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def get_club(self, id):
        catalog = getToolByName(self.context, 'portal_catalog')
        return [dict(name=club.Title, vat_no=club.personal_id, uid=club.UID, club=club) for club in
                catalog({'object_provides': IClub.__identifier__,
                         'personal_id': id,
                         })]


    def get_property(self, obj, prop):
        value = obj.getProperty(prop)
        if type(value).__name__ == 'object':
             return None
        return value

    def get_person(self, relation):
        portal_type = relation.getObject().__parent__.portal_type
        
        record = {}
        #import pdb; pdb.set_trace()

        user = relation.getObject().getOwner()
        #user = api.user.get(relation.Creator)

        if portal_type == 'hejasverige.person':
            # get the person name
            # and the creator of the person
            record['fullname'] = relation.getObject().__parent__.first_name + ' ' + relation.getObject().__parent__.last_name
            record['personal_id'] = relation.getObject().__parent__.personal_id

        elif portal_type == 'hejasverige.relationfolder':
            # get user name
            record['fullname'] = self.get_property(user, 'fullname')
            record['personal_id'] = self.get_property(user, 'personal_id')


        record['address1'] = self.get_property(user, 'address1')
        record['address2'] = self.get_property(user, 'address2')
        record['postal_code'] = self.get_property(user, 'postal_code')
        record['city'] = self.get_property(user, 'city')
        record['kollkoll'] = self.get_property(user, 'kollkoll')
        record['username'] = str(user)  # relation.Creator
        record['status'] = relation.review_state
        record['email'] = str(user)  # relation.Creator
        

        return record

    def get_club_relations(self, id):
        #import pdb; pdb.set_trace()
        catalog = getToolByName(self.context, 'portal_catalog')
        '''
        relationw = [dict(creator=relation.Creator,
                          title=relation.Title,
                          vat_no=relation.personal_id,
                          uid=relation.UID,
                          person=self.get_person(relation))
                     for relation in
                     catalog({'object_provides': IRelation.__identifier__,
                     'personal_id': id, 
                     })
                     ]
        '''

        query = {'object_provides': IRelation.__identifier__,
                 'personal_id': id,
                 }

        status = self.request.form.get('status', None)
        if status:
            logger.debug('status: %s' % status)
            review_states = [x.strip() for x in status.split(',')]
            query['review_state'] = review_states

        relations = [self.get_person(relation)
                     for relation in
                     catalog(query)
                     ]

        return relations

    def get_invited(self, club):
        data = []
        catalog = getToolByName(self.context, 'portal_catalog')

        from hejasverige.invitation.interfaces import IInvitation

        query = {}
        query['object_provides'] = IInvitation.__identifier__
        query['path'] = dict(query=club.getPath())
        query['review_state'] = 'pending'

        invitations = catalog(query)

        for invitation in invitations:
            if invitation.ExpirationDate > datetime.datetime.now():
                o = invitation.getObject()
                rec = {}
                rec['type'] = 'invited'
                rec['personal_id'] = o.personal_id
                rec['fullname'] = o.first_name + ' ' + o.last_name
                rec['email'] = o.recipient_email
                rec['personal_id'] = o.personal_id
                rec['status'] = invitation.review_state
                data.append(rec)
        
        return data

    def render(self):
        data = []
        if self.request['QUERY_STRING']:
            vat_no = self.request.form.get('vat_no', None)
            invited = self.request.form.get('invited', None)
            club = self.get_club(vat_no)
            relations = self.get_club_relations(vat_no)
            data = relations

            if invited == 'true':
                personal_ids = [v['personal_id'] for v in data]
                invited = self.get_invited(club[0].get('club'))

                for i in invited:
                    if i.get('personal_id') not in personal_ids:
                        data.append(i)
                        personal_ids.append(i.get('personal_id'))
                    else:
                        logger.info('Did not include %s from invited. Already a present member.' % (i.get('personal_id'),))

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data, indent=4)


class GetMember(grok.View):

    """ Lists a specific member and their available relations.
        The relations can be either direct or in-direct through any of
        the member's associated person
    """

    grok.context(ISiteRoot)
    grok.name('get-member')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def get_clubs_from_relations(self, path):
        catalog = getToolByName(self.context, 'portal_catalog')

        query = {'object_provides': IRelation.__identifier__,
                 'path': dict(query=path,),
                 'sort_on': 'sortable_title'}

        status = self.request.form.get('status', None)
        if status:
            logger.debug('status: %s' % status)
            review_states = [x.strip() for x in status.split(',')]
            query['review_state'] = review_states

        clubs = [dict(clubobj=uuidToObject(relation.getObject().foreign_id),
                 relation=relation)
                 for relation in
                 catalog(query)]

        clubs = [x for x in clubs if x]

        return clubs

    def render(self):
        userid = self.request.form.get('userid', '')
        personalid = self.request.form.get('personalid', '')
        details = self.request.form.get('details', '')
        vat_no = self.request.form.get('vat_no', '')
        show_details = False
        if details == 'true':
            show_details = True

        data = {}
        user = None
        # find user object
        if userid != '':
            user = api.user.get(username=userid)
        elif personalid != '':
            users = api.user.get_users()
            for u in users:
                if personalid == u.getProperty('personal_id'):
                    # user found, store it
                    user = u
                    break

        if user is None:
            logger.info('No user with provided parameters found. Personal id %s, User id: %s' % (personalid, userid))
            # possibly a person
            # handle that
            # (there might appear cases where a user is also a person guarded by another user, we do not
            #  handle that yet, and possibly never)
            catalog = getToolByName(self.context, 'portal_catalog')

            persons = catalog({'object_provides': IPerson.__identifier__,
                      'personal_id': personalid,
                      'sort_on': 'sortable_title'})

            if persons:
                data['type'] = 'person'
                data['personal_id'] = persons[0].personal_id
                if show_details:
                    data['fullname'] = persons[0].Title

                guardians = []
                for person in persons:
                    user = person.getObject().getOwner()
                    # check that the user has an Id
                    # removed users with orphant persons will otherwise errounously show up here
                    if user.getId():                  
                        guardian = {}
                        guardian['personal_id'] = user.getProperty('personal_id')
                        if show_details:
                            guardian['username'] = str(user)
                            guardian['email'] = user.getProperty('email')
                            guardian['fullname'] = user.getProperty('fullname')
                            guardian['address1'] = user.getProperty('address1')
                            guardian['address2'] = user.getProperty('address2')
                            guardian['postal_code'] = user.getProperty('postal_code')
                            guardian['city'] = user.getProperty('city')          
                            guardian['kollkoll'] = user.getProperty('kollkoll')

                        # persons managed club relations
                        query = {'object_provides': IRelation.__identifier__,
                                 'path': dict(query=person.getPath(),)}

                        # TODO: What happens if en förening byter organisationsnummer
                        # Bad things will happen... alla relationer med koppling till föreningen måste indexeras om
                        if vat_no:
                           query['personal_id'] = vat_no 

                        status = self.request.form.get('status', None)
                        if status:
                            logger.debug('status: %s' % status)
                            review_states = [x.strip() for x in status.split(',')]
                            query['review_state'] = review_states

                        clubs = [dict(vat_no=club.personal_id, name=club.Title, uid=club.UID, status=club.review_state)
                                 for club in 
                                 catalog(query)]
                                 # had earlier a condition where ther had to be a vat_no present
                                 #  if club.personal_id
                        guardian['associated_clubs'] = clubs

                        # only include guardians where club is present
                        if clubs:
                            guardians.append(guardian)
                
                data['guardians'] = guardians

        else:
            mship = getToolByName(self, 'portal_membership')
            homefolder = mship.getHomeFolder(user.getProperty('id'))
            path = '/'.join(homefolder.getPhysicalPath())
            logger.info('Found home folder %s' % path)

            clubs = self.get_clubs_from_relations(path)

            associated_clubs = []
            for club in clubs:
                rec = {}
                if show_details:
                    if club.get('relation').getObject().__parent__.portal_type != 'hejasverige.relationfolder':
                        parent = club.get('relation').getObject().__parent__
                        rec['owner'] = parent.personal_id
                        rec['owner_name'] = parent.first_name + ' ' + parent.last_name
                    else:
                        rec['owner'] = user.getProperty('personal_id')
                        rec['owner_name'] = user.getProperty('fullname')

                    rec['name'] = club.get('clubobj').title

                rec['uid'] = club.get('clubobj').UID()
                rec['vat_no'] = club.get('clubobj').VatNo
                rec['status'] =  club.get('relation').review_state
                if rec['vat_no']:
                    rec['vat_no'] = rec['vat_no'].replace('-','')

                associated_clubs.append(rec)

            # make clubs list unique 
            if show_details:
                pass
            else:
                associated_clubs = {v['uid']:v for v in associated_clubs}.values()

            data = dict(personal_id=user.getProperty('personal_id'), associated_clubs=associated_clubs)
            if show_details:
                data['type'] = 'user'
                data['username'] = str(user)
                data['email'] = user.getProperty('email')
                data['fullname'] = user.getProperty('fullname')
                data['address1'] = user.getProperty('address1')
                data['address2'] = user.getProperty('address2')
                data['postal_code'] = user.getProperty('postal_code')
                data['city'] = user.getProperty('city')          
                data['kollkoll'] = user.getProperty('kollkoll')


        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data, indent=4)


class GetInvitedMembers(grok.View):
    """ Lists a specific member and their available relations.
        The relations can be either direct or in-direct through any of
        the member's associated person
    """

    grok.context(ISiteRoot)
    grok.name('get-invited-members')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def render(self):
        vat_no = self.request.form.get('vat_no', None)
        data = []

        if vat_no:
            vat_no = vat_no.replace('-','')

            catalog = getToolByName(self.context, 'portal_catalog')
            clubs = catalog({'object_provides': IClub.__identifier__,
                             'personal_id': vat_no,
                              }
                             )

            from hejasverige.invitation.interfaces import IInvitation

            for club in clubs:
                query = {}
                query['object_provides'] = IInvitation.__identifier__
                query['path'] = dict(query=club.getPath())
                invitations = catalog(query)

                for invitation in invitations:
                    o = invitation.getObject()
                    rec = {}
                    rec['type'] = 'invited'
                    rec['personal_id'] = o.personal_id
                    rec['fullname'] = o.first_name + ' ' + o.last_name
                    rec['email'] = o.recipient_email
                    rec['personal_id'] = o.personal_id
                    rec['status'] = invitation.review_state
                    data.append(rec)
        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data, indent=4)

