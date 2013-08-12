# -*- coding: utf-8 -*-

from Products.CMFCore.interfaces import ISiteRoot
from five import grok
import json
from hejasverige.content.merchant import IMerchant
from hejasverige.content.store import IStore
from hejasverige.content.pos import IPos
from Products.CMFCore.utils import getToolByName
from plone.memoize.instance import memoize
import re

# TODO: make sure we only list published merchants
@memoize
def get_merchants(context):
    catalog = getToolByName(context.context, 'portal_catalog')
    return catalog({'object_provides': IMerchant.__identifier__,
                    'sort_on': 'sortable_title'})


class ListMerchantsView(grok.View):

    """ Lists all available users and corresponding
    """

    grok.context(ISiteRoot)
    grok.name('list-merchants')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    # TODO: make sure we only list published merchants
    @memoize
    def get_merchants(self):
        catalog = getToolByName(self.context, 'portal_catalog')
        return catalog({'object_provides': IMerchant.__identifier__,
                        'sort_on': 'sortable_title'})

    @memoize
    def list_stores(self, merchant):
        catalog = getToolByName(self.context, 'portal_catalog')
        stores = catalog({'object_provides': IStore.__identifier__,
                         'path': dict(query=merchant.getPath(),
                                      depth=1),
                         'sort_on': 'sortable_title'})
        data = []
        for store in stores:
            pos = self.list_pos(store)
            store_record = self.create_store_record(store, pos)
            data.append(store_record)

        return data

    @memoize
    def list_pos(self, store):
        catalog = getToolByName(self.context, 'portal_catalog')
        return [dict(url=pos.getURL(), title=pos.Title,
                description=pos.Description,
                pos_id=pos.posId,) for pos in
                catalog({'object_provides': IPos.__identifier__,
                'path': dict(query=store.getPath(),
                depth=1),
                'sort_on': 'sortable_title'})]

    @memoize
    def merchant_has_pos(self, merchant, pos_id):
        catalog = getToolByName(self.context, 'portal_catalog')
        merchant_pos = [pos.posId for pos in
                             catalog({'object_provides': IPos.__identifier__,
                             'path': dict(query=merchant.getPath(),
                             depth=2),})]

        if pos_id in merchant_pos:
            return True

        return False


    def create_store_record(self, store, pos):
        store_record = {'name': store.Title,
                        'store_id': store.storeId,
                        'point_of_sales': pos,
                        }
        return store_record

    def create_merchant_record(self, merchant, stores):

        if not merchant.discount:
            discount = '0'
        else:
            discount = merchant.discount

        if not merchant.supplierId:
            supplierId = ''
        else:
            supplierId = merchant.supplierId

        if not merchant.customerId:
            customerId = ''
        else:
            customerId = merchant.customerId

        try:
            transaction_fee = merchant.transaction_fee
        except:
            transaction_fee = ''
        # Value is missing in the catalog. Type Missing.Value name == 'Value'
        if type(transaction_fee).__name__ == 'Value':
            transaction_fee = ''

        #import pdb; pdb.set_trace()

        if not merchant.transaction_description:
            transaction_description = []
        else:
            transaction_description = [x.encode('base64') for x in merchant.transaction_description]


        merchant_record = {'name': merchant.Title,
                           'corporate_id': merchant.corporateId,
                           'supplier_id': supplierId,
                           'customer_id': customerId,
                           'discount': discount,
                           'transaction_fee': transaction_fee,
                           'transaction_description': transaction_description,
                           'stores': stores,
                           }
        return merchant_record

    def render(self):
        # Prepare response
        corporate_id = self.request.form.get('corporate_id', '')
        pos_id = self.request.form.get('pos_id', '')
        data = []

        merchants = self.get_merchants()
        for merchant in merchants:
            if corporate_id:
                if merchant.corporateId == corporate_id:
                    stores = self.list_stores(merchant)
                    merchant_record = self.create_merchant_record(merchant,
                                                                  stores)
                    data.append(merchant_record)
            elif pos_id:
                if self.merchant_has_pos(merchant, pos_id):
                    stores = self.list_stores(merchant)
                    merchant_record = self.create_merchant_record(merchant,
                                                                  stores)
                    data.append(merchant_record)
            else:
                stores = self.list_stores(merchant)
                merchant_record = self.create_merchant_record(merchant, stores)
                data.append(merchant_record)

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)

# Skicka in transaktionstext - returnera handlare
class GetMerchantByDescription(grok.View):

    """ Returns the first matching merchant. Be aware that several expressions 
        could match, but only the firt found is returned. (That must change. 
        returning a list of merchants for future change.)
    """

    grok.context(ISiteRoot)
    grok.name('get-merchant-by-description')
    grok.require('hejasverige.ApiView')  # this is the security declaration

    def render(self):
        description = self.request.form.get('description', '')
        data = []
        if description:
            merchants = get_merchants(self)
            #import pdb; pdb.set_trace()
            for merchant in merchants:
                try:
                    transaction_descriptions = merchant.transaction_description
                except:
                    merchant.getObject().reindexObject()
                    try:
                        transaction_descriptions = merchant.transaction_description
                    except:
                        pass

                if transaction_descriptions:
                    for transaction_description in transaction_descriptions:
                        tdre = re.compile(transaction_description)
                        match = tdre.match(description)
                        if match:
                            merchant_obj = merchant.getObject()

                            try:
                                transaction_fee = merchant_obj.transaction_fee
                            except:
                                merchant.getObject().reindexObject()
                                try:
                                    transaction_fee = merchant_obj.transaction_fee
                                except:
                                    transaction_fee = ''
                                # Value is missing in the catalog. Type Missing.Value name == 'Value'
                                if type(transaction_fee).__name__ == 'Value':
                                    transaction_fee = ''



                            data.append({'name': merchant_obj.title,
                                         'corporate_id': merchant_obj.corporateId,
                                         'supplier_id': merchant_obj.supplierId,
                                         'customer_id': merchant_obj.customerId,
                                         'discount': merchant_obj.discount,
                                         'transaction_fee': transaction_fee,
                                         'description': description,
                                         'matching_description': transaction_description,
                                         })

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(data)
