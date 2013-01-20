# -*- coding: utf-8 -*-

from Products.CMFCore.interfaces import ISiteRoot
from five import grok
import json
from hejasverige.content.merchant import IMerchant
from hejasverige.content.store import IStore
from hejasverige.content.pos import IPos
from Products.CMFCore.utils import getToolByName
from plone.memoize.instance import memoize


class ListMerchantsView(grok.View):

    """ Lists all available users and corresponding
    """

    grok.context(ISiteRoot)
    grok.name('list-merchants')
    grok.require('hejasverige.ApiView')  # this is the security declaration

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

    def create_store_record(self, store, pos):
        store_record = {'name': store.Title,
                        'store_id': store.storeId,
                        'point_of_sales': pos,
                        }
        return store_record

    def create_merchant_record(self, merchant, stores):
        merchant_record = {'name': merchant.Title,
                           'corporate_id': merchant.corporateId,
                           'supplier_id': merchant.supplierId,
                           'customer_id': merchant.customerId,
                           'stores': stores,
                           }
        return merchant_record

    def render(self):
        # Prepare response
        corporate_id = self.request.form.get('corporate_id', '')
        data = []

        merchants = self.get_merchants()
        for merchant in merchants:
            if corporate_id:
                if merchant.corporateId == corporate_id:
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
