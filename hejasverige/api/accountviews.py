# -*- coding: utf-8 -*-

import json
from five import grok
from Products.CMFCore.interfaces import ISiteRoot
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout
from hejasverige.megabank.bank import Bank

import logging
logger = logging.getLogger(__name__)


class GetAccountView(grok.View):
    """ gets account for an organisation
    """
    grok.context(ISiteRoot)
    grok.name('get-account')
    grok.require('hejasverige.ApiView')

    def render(self):
        data = {}
        personalid = self.request.form.get('personalid')

        self.request.response.setHeader('Content-Type', 'application/json')

        if not personalid:
            return json.dumps(data)

        # get the fuckin' account from Mega Bank
        # http://<bank>:<port>/BankService.svc/accounts/7804246697/


        # Get Account
        try:
            bank = Bank()
        except Exception, ex:
            logger.info("Connection Error while creating bank")
            data.append({'error': 'Connection Error. Could not connect to the bank: ' + str(ex)})
            self.request.response.setStatus(504, "")
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(data)
        else:
            try:
                data = bank.getAccountFromMegabank(personalid=personalid)

            except ConnectionError, ex:
                logger.info("Connection Error")
                data.append({'error': 'Connection Error. Could not connect to the bank: ' + str(ex)})
                self.request.response.setStatus(504, "")
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(data)
            except Timeout, ex:
                logger.info("Timeout")
                data.append({'error': 'Timeout. Could not connect to the bank: ' + str(ex)})
                self.request.response.setStatus(504, "")
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(data)

            if not data:
                data = {}

        return json.dumps(data)
