# -*- coding: utf-8 -*-

import json
import StringIO
import logging
import email.Parser

from datetime import datetime
from five import grok
from hejasverige.api.dotdictify import dotdictify
from hejasverige.content.invoice import IInvoice
from plone.dexterity.utils import createContent
from plone.dexterity.utils import addContentToContainer
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.interfaces import INamedFileField
from plone.namedfile.interfaces import INamedImageField
from plone.rfc822.interfaces import IPrimaryField
from Products.CMFCore.interfaces import ISiteRoot
from zope.schema import getFieldsInOrder
from Products.CMFCore.utils import getToolByName

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# TODO:
#   - set owner and permissions on created invoice to recipient. DONE!
#   - validate the read json/return json schema when @@create-invoice?schema
#   - set grok.require to correct permission (some api permission)
#   - use python email module to handle multi-part/form
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
logger = logging.getLogger(__name__)

class CreateInvoiceView(grok.View):

    """ Creates an invoice
    """

    grok.context(ISiteRoot)
    grok.name('create-invoice')
    grok.require('hejasverige.ApiView')

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def get_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "invoiceNo": {
                    "type": "string",
                    "required": True
                },

                "invoiceDescription": {
                    "type": "string",
                    "description": ""
                },
                "invoiceReference": {
                    "type": "object",
                    "properties": {
                        "userName": {
                            "type": "string",
                            "required": True
                        },
                        "displayName": {
                            "type": "string"
                        },
                    }
                },
                "invoiceDetails": {
                    "type": "array",
                    "properties": {
                        "amount": {
                            "type": "string"
                        },
                        "unitprice": {
                            "type": "string"
                        },
                        "total": {
                            "type": "string"
                        },
                        "taxRate": {
                            "type": "string"
                        },
                        "description": {
                            "type": "string"
                        },
                    }
                },
                "senderId": {
                    "type": "string",
                    "required": True
                },
                "senderName": {
                    "type": "string"
                },
                "invoiceDate": {
                    "type": "string"
                },
                "invoicePayCondition": {
                    "type": "string"
                },
                "invoiceExpireDate": {
                    "type": "string",
                    "required": True
                },
                "invoiceTotalCost": {
                    "type": "string",
                    "required": True
                },
                "invoiceCurrency": {
                    "type": "string"
                },
                "invoiceTotalVat": {
                    "type": "string"
                }
            },
        }

        return schema

    def validate(self, data):
        '''
        Maybe use this...

        http://www.alexconrad.org/2011/10/json-validation.html

        import validictory
        data = json.loads(request.body)
        schema = {"type": "string"}
        try:
            validictory.validate(data, schema)
        except ValueError, ex:
            print ex

        '''
        import validictory
        schema = self.get_schema()
        try:
            validictory.validate(data, schema)
            return 0
        except ValueError, ex:
            return ex

    def set_owner(self, obj):
        membership_tool = getToolByName(self, 'portal_membership')
        members = [member for member in membership_tool.listMembers()
                   if member.getProperty('personal_id') == obj.invoiceRecipient
                   ]

        # import pdb; pdb.set_trace()

        if members:
            obj.changeOwnership(members[0].getUser(), recursive=False)
            obj.manage_setLocalRoles(str(members[0].getUser()), ["Owner", ])
            obj.reindexObjectSecurity()
        else:
            # no user with provided personal id found property not changed
            pass

        return

    def render(self):

        if self.request['QUERY_STRING'] == 'schema':
            data = self.get_schema()
            self.request.response.setStatus(200, "")
            self.request.response.setHeader('Content-Type', 'application/json')
            return data
        else:
            # init response
            data = []

            # Payload should not really be in body, but we'll accept that also
            payload = self.request.get('BODY')
            if payload:
                logger.info('Payload in BODY: %s' % str(payload));


                # split up payload
                '''
                Content-Type: multipart/form-data; boundary=AaB03x

                --AaB03x
                Content-Disposition: form-data; name="submit-name"

                Larry
                --AaB03x
                Content-Disposition: form-data; name="files"; filename="file1.txt"
                Content-Type: text/plain

                ... contents of file1.txt ...
                --AaB03x--
                '''

                filename = None
                invoicedata = None
                invoicefile = None
                contenttype = None
                transfer_encoding = None

                buf = StringIO.StringIO(payload)

                p=email.Parser.Parser()
                try:
                    msg=p.parse(buf)
                    partCounter=1
                    for part in msg.walk():
                        import pdb; pdb.set_trace()
                        if part.get_content_maintype()=="multipart":
                            continue
                        name=part.get_param("name")
                        if not name:
                            name=part.get_param("name", header='Content-Disposition')
                        
                        if name==None:
                            name="part-%i" % partCounter
                        partCounter+=1

                        if name=='invoice-data':
                            invoicedata = part.get_payload(decode=1)

                        if name=='invoice-file':
                            contenttype = part.get_content_type()
                            invoicefile = part.get_payload(decode=1)
                            filename = part.get_filename()
                            transfer_encoding = part.get_all('Content-Transfer-Encoding')

                except Exception, ex:
                    error = 'Unable to parse payload: %s' % str(ex)
                    data.append({'error': error})
                    self.request.response.setHeader('Content-Type', 'application/json')
                    self.request.response.setStatus(404, "")
                    return data
            else:
                # request was sent as a real multipart
                logger.info('Payload not received in request BODY. Good...')
                # import pdb;pdb.set_trace()
                invoicedata = self.request.get('invoice-data')
                invoicefile = self.request.get('invoice-file').readlines()[0]
                filename = self.request.get('invoice-file').filename
                contenttype = self.request['invoice-file'].headers['content-type']
                transfer_encoding = None

            if invoicefile:
                if transfer_encoding == 'base64':
                    import base64
                    try:
                        invoicefile = base64.b64decode(invoicefile)
                        #import pdb; pdb.set_trace()
                    except:
                        # just try to decode if possible
                        pass
            else:
                if not invoicedata:
                    #if there is no invoice data
                    #return
                    data.append({'error': 'No or empty invoice-data part received'})
                    self.request.response.setHeader('Content-Type', 'application/json')
                    self.request.response.setStatus(422, "")
                    return data

            try:
                #import pdb
                #pdb.set_trace()
                objfields = json.loads(invoicedata)
            except Exception, ex:
                data.append({'error': 'Error creating json object from invoice-data part: ' + str(ex)})
                self.request.response.setStatus(400, "")
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(data)
            else:
                try:
                    #invoiceNo
                    #invoiceSender
                    #invoiceSenderName = schema.ASCIILine(title=_(u'Avsändare namn'),
                    #invoiceRecipient = schema.ASCIILine(title=_(u'Mottagare'),
                    #invoiceRecipientName = schema.ASCIILine(title=_(u'Mottagare namn'),
                    #externalId = schema.ASCIILine(title=_(u'Externt Id'),
                    #invoiceDate = schema.Date(title=_(u'Fakturadatum'),
                    #invoicePayCondition = schema.ASCIILine(title=_(u'Betalningsvillkor'),
                    #invoiceExpireDate = schema.Date(title=_(u'Förfallodatum'),
                    #invoiceCurrency = schema.ASCIILine(title=_(u'Valuta'),
                    #invoiceTotalVat = schema.ASCIILine(title=_(u'Total moms'),
                    #invoiceTotalAmount = schema.ASCIILine(title=_(u'Totalt belopp'),
                    #InvoiceImage = NamedBlobFile(title=_(u'Faktura'),

                    invoice = dotdictify(objfields)
                    invoice.title = invoice.invoiceNo

                    #invoiceReferences = invoice.invoiceReferences
                    #use the first reference as recipient
                    #objfields = invoiceReferences[0]

                    #invoiceReference = dotdictify(invoice.invoiceReference)
                    invoice.invoiceRecipient = invoice.invoiceReference.userName
                    invoice.invoiceRecipientName = invoice.invoiceReference.displayName

                    invoice.invoiceExpireDate = datetime.strptime(invoice.invoiceExpireDate, '%Y-%m-%d')
                    invoice.invoiceDate = datetime.strptime(invoice.invoiceDate, '%Y-%m-%d')
                    #import pdb; pdb.set_trace()

                    content = createContent(portal_type="hejasverige.Invoice",
                                            title=invoice.title,
                                            description=invoice.invoiceDescription,
                                            invoiceNo=invoice.invoiceNo,
                                            invoiceSender=invoice.senderId,
                                            invoiceSenderName=invoice.senderName,
                                            invoiceRecipient=invoice.invoiceRecipient,
                                            invoiceRecipientName=invoice.invoiceRecipientName,
                                            invoiceDate=invoice.invoiceDate,
                                            invoicePayCondition=invoice.invoicePayCondition,
                                            invoiceExpireDate=invoice.invoiceExpireDate,
                                            invoiceCurrency=invoice.invoiceCurrency,
                                            invoiceTotalVat=invoice.invoiceTotalVat,
                                            invoiceTotalAmount=invoice.invoiceTotalCost
                                            )

                    # Get the field containing data
                    fields = getFieldsInOrder(IInvoice)
                    file_fields = [field for name, field in fields
                                   if INamedFileField.providedBy(field)
                                   or INamedImageField.providedBy(field)
                                   ]
                    for file_field in file_fields:
                        if IPrimaryField.providedBy(file_field):
                            break
                        else:
                            # Primary field can't be set ttw,
                            # then, we take the first one
                            file_field = file_fields[0]

                    #import pdb
                    #pdb.set_trace()

                    value = NamedBlobFile(data=invoicefile,
                                          contentType=contenttype,
                                          filename=unicode(filename, 'utf-8'))

                    file_field.set(content, value)

                    folder = self.context['invoices']

                    item = addContentToContainer(container=folder, object=content, checkConstraints=False)

                    # set the recipient to owner of the invoice. Otherwise it will not show up for the recipient in MyAccount View.
                    self.set_owner(item)

                    #content.reindexObject()

                    print item.id
                except Exception, ex:
                    data.append({'error': 'Could not create invoice object. Reason: ' + str(ex)})
                    self.request.response.setStatus(500, "")
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(data)
                #import pdb; pdb.set_trace()
                data.append({'storageid': item.id, 'UID': item.UID()})
                self.request.response.setStatus(201, "")
                #import pdb; pdb.set_trace()

            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(data)


class CreateInvoiceView2(grok.View):

    """ Creates an invoice
        OLD VERSION
    """

    grok.context(ISiteRoot)
    grok.name('create-invoice2')
    grok.require('hejasverige.ApiView')

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def get_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "invoiceNo": {
                    "type": "string",
                    "required": True
                },

                "invoiceDescription": {
                    "type": "string",
                    "description": ""
                },
                "invoiceReference": {
                    "type": "object",
                    "properties": {
                        "userName": {
                            "type": "string",
                            "required": True
                        },
                        "displayName": {
                            "type": "string"
                        },
                    }
                },
                "invoiceDetails": {
                    "type": "array",
                    "properties": {
                        "amount": {
                            "type": "string"
                        },
                        "unitprice": {
                            "type": "string"
                        },
                        "total": {
                            "type": "string"
                        },
                        "taxRate": {
                            "type": "string"
                        },
                        "description": {
                            "type": "string"
                        },
                    }
                },
                "senderId": {
                    "type": "string",
                    "required": True
                },
                "senderName": {
                    "type": "string"
                },
                "invoiceDate": {
                    "type": "string"
                },
                "invoicePayCondition": {
                    "type": "string"
                },
                "invoiceExpireDate": {
                    "type": "string",
                    "required": True
                },
                "invoiceTotalCost": {
                    "type": "string",
                    "required": True
                },
                "invoiceCurrency": {
                    "type": "string"
                },
                "invoiceTotalVat": {
                    "type": "string"
                }
            },
        }

        return schema

    def validate(self, data):
        '''
        Maybe use this...

        http://www.alexconrad.org/2011/10/json-validation.html

        import validictory
        data = json.loads(request.body)
        schema = {"type": "string"}
        try:
            validictory.validate(data, schema)
        except ValueError, ex:
            print ex

        '''
        import validictory
        schema = self.get_schema()
        try:
            validictory.validate(data, schema)
            return 0
        except ValueError, ex:
            return ex

    def set_owner(self, obj):
        membership_tool = getToolByName(self, 'portal_membership')
        members = [member for member in membership_tool.listMembers()
                   if member.getProperty('personal_id') == obj.invoiceRecipient
                   ]

        # import pdb; pdb.set_trace()

        if members:
            obj.changeOwnership(members[0].getUser(), recursive=False)
            obj.manage_setLocalRoles(str(members[0].getUser()), ["Owner", ])
            obj.reindexObjectSecurity()
        else:
            # no user with provided personal id found property not changed
            pass

        return

    def render(self):

        if self.request['QUERY_STRING'] == 'schema':
            data = self.get_schema()
            self.request.response.setStatus(200, "")
            self.request.response.setHeader('Content-Type', 'application/json')
            return data
        else:
            payload = self.request.get('BODY')
            if payload:
                logger.info('Payload: %s' % str(payload));
            else:
                logger.warning('Empty payload received')

            # init response
            data = []

            # split up payload
            '''
            Content-Type: multipart/form-data; boundary=AaB03x

            --AaB03x
            Content-Disposition: form-data; name="submit-name"

            Larry
            --AaB03x
            Content-Disposition: form-data; name="files"; filename="file1.txt"
            Content-Type: text/plain

            ... contents of file1.txt ...
            --AaB03x--
            '''
            buf = StringIO.StringIO(payload)
            boundry = None

            line = buf.readline()
            line = line.rstrip()

            ctline = line.split(';')

            if len(ctline) > 0:
                for l in ctline:
                    if 'boundary=' in l.replace(' ', ''):
                        key, boundry = l.split('=', 1)

            parts = []
            if not boundry:
                logger.error('No boundry found in payload: %s' % str(payload));
            else:
                parts = payload.split('--' + boundry)

            objects = []
            name = ''
            filename = ''
            contenttype = ''
            invoicedata = None
            invoicefile = ''

            for part in parts:
                objects.append(part.strip().split('\n\n'))

                try:
                    contentdescription, contentdata = part.strip().split('\n\n')

                    contentdescriptionlines = contentdescription.split('\n')
                    if contentdescriptionlines:
                        contentdescriptionlist = contentdescriptionlines[0].split(';')
                        for cd in contentdescriptionlist:
                            if 'filename=' in cd.replace(' ', ''):
                                key, filename = cd.split('=', 1)
                                filename = filename.strip('"')
                            elif 'name=' in cd.replace(' ', ''):
                                key, name = cd.split('=', 1)
                                name = name.strip('"')

                    if len(contentdescriptionlines) > 1:
                        try:
                            key, value = contentdescriptionlines[1].split(':')
                            if key.lower() == 'content-type':
                                contenttype = value.strip()
                        except:
                            print 'Not a content type line, strange'
                    if name == 'invoice-data':
                        invoicedata = contentdata
                    elif name == 'invoice-file':
                        invoicefile = contentdata

                except:
                    # Not a valid part (probably head or tail)
                    pass

            if invoicefile:
                import base64
                try:
                    invoicefile = base64.b64decode(invoicefile)
                except:
                    # just try to decode if possible
                    pass
            else:
                if not invoicedata:
                    #if there is no invoice data
                    #return
                    data.append({'error': 'No or empty invoice-data part received'})
                    self.request.response.setHeader('Content-Type', 'application/json')
                    self.request.response.setStatus(422, "")
                    return data

            try:
                #import pdb
                #pdb.set_trace()
                objfields = json.loads(invoicedata)
            except Exception, ex:
                data.append({'error': 'Error creating json object from invoice-data part: ' + str(ex)})
                self.request.response.setStatus(400, "")
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(data)
            else:
                try:
                    #invoiceNo
                    #invoiceSender
                    #invoiceSenderName = schema.ASCIILine(title=_(u'Avsändare namn'),
                    #invoiceRecipient = schema.ASCIILine(title=_(u'Mottagare'),
                    #invoiceRecipientName = schema.ASCIILine(title=_(u'Mottagare namn'),
                    #externalId = schema.ASCIILine(title=_(u'Externt Id'),
                    #invoiceDate = schema.Date(title=_(u'Fakturadatum'),
                    #invoicePayCondition = schema.ASCIILine(title=_(u'Betalningsvillkor'),
                    #invoiceExpireDate = schema.Date(title=_(u'Förfallodatum'),
                    #invoiceCurrency = schema.ASCIILine(title=_(u'Valuta'),
                    #invoiceTotalVat = schema.ASCIILine(title=_(u'Total moms'),
                    #invoiceTotalAmount = schema.ASCIILine(title=_(u'Totalt belopp'),
                    #InvoiceImage = NamedBlobFile(title=_(u'Faktura'),

                    invoice = dotdictify(objfields)
                    invoice.title = invoice.invoiceNo

                    #invoiceReferences = invoice.invoiceReferences
                    #use the first reference as recipient
                    #objfields = invoiceReferences[0]

                    #invoiceReference = dotdictify(invoice.invoiceReference)
                    invoice.invoiceRecipient = invoice.invoiceReference.userName
                    invoice.invoiceRecipientName = invoice.invoiceReference.displayName

                    invoice.invoiceExpireDate = datetime.strptime(invoice.invoiceExpireDate, '%Y-%m-%d')
                    invoice.invoiceDate = datetime.strptime(invoice.invoiceDate, '%Y-%m-%d')
                    #import pdb; pdb.set_trace()

                    content = createContent(portal_type="hejasverige.Invoice",
                                            title=invoice.title,
                                            description=invoice.invoiceDescription,
                                            invoiceNo=invoice.invoiceNo,
                                            invoiceSender=invoice.senderId,
                                            invoiceSenderName=invoice.senderName,
                                            invoiceRecipient=invoice.invoiceRecipient,
                                            invoiceRecipientName=invoice.invoiceRecipientName,
                                            invoiceDate=invoice.invoiceDate,
                                            invoicePayCondition=invoice.invoicePayCondition,
                                            invoiceExpireDate=invoice.invoiceExpireDate,
                                            invoiceCurrency=invoice.invoiceCurrency,
                                            invoiceTotalVat=invoice.invoiceTotalVat,
                                            invoiceTotalAmount=invoice.invoiceTotalCost
                                            )

                    # Get the field containing data
                    fields = getFieldsInOrder(IInvoice)
                    file_fields = [field for name, field in fields
                                   if INamedFileField.providedBy(field)
                                   or INamedImageField.providedBy(field)
                                   ]
                    for file_field in file_fields:
                        if IPrimaryField.providedBy(file_field):
                            break
                        else:
                            # Primary field can't be set ttw,
                            # then, we take the first one
                            file_field = file_fields[0]

                    value = NamedBlobFile(data=invoicefile,
                                          contentType=contenttype,
                                          filename=unicode(filename, 'utf-8'))

                    file_field.set(content, value)

                    folder = self.context['invoices']

                    item = addContentToContainer(container=folder, object=content, checkConstraints=False)

                    # set the recipient to owner of the invoice. Otherwise it will not show up for the recipient in MyAccount View.
                    self.set_owner(item)

                    #content.reindexObject()
                    #import pdb
                    #pdb.set_trace()

                    print item.id
                except Exception, ex:
                    data.append({'error': 'Could not create invoice object ' + str(ex)})
                    self.request.response.setStatus(500, "")
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(data)

            data.append({'storageid': item.id})
            self.request.response.setStatus(201, "")
            #import pdb; pdb.set_trace()
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(data)


class GetInvoicesView(grok.View):
    """ gets invoices for an organisation
    """

    grok.context(ISiteRoot)
    grok.name('get-invoices')
    grok.require('hejasverige.ApiView')

    def megabankisinstalled(self):
        try:
            from hejasverige.megabank.bank import Bank 
            logger.info('Megabank is installed');
            return True
        except:
            logger.info('Megabank is NOT installed');
            return False

    def render(self):
        # init response
        data = []

        # verify that Megabank is present, otherwise inform so
        if not self.megabankisinstalled:
            data.append({'error': 'There is no bank available'})
            self.request.response.setStatus(500, "")
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(data)
        else:
            # def getInvoices(self, personalid, invoiceid=None, startdate=None, enddate=None, status=None):
            orgnr = self.request.form.get('orgnr', '')
            invoiceid = self.request.form.get('invoiceid', '')
            startdate = self.request.form.get('startdate', '')
            enddate = self.request.form.get('enddate', '')
            status = self.request.form.get('status', 0)

            print self.request.form.get('outgoing', 0)

            if self.request.form.get('outgoing', '0') == '0':
                outgoing = 'false'
            else:
                outgoing = 'true'

            # Status
            # 0 = pending
            # 1 = payed
            # 2 = rejected

            
            # Exceptions are thouwn from the bank, that uses requests api
            # Bank should implement its own exception handling and throw them instead.
            # for now, we just read the exceptions from requests.
            from requests.exceptions import ConnectionError
            from requests.exceptions import Timeout

            # Get Invoices
            from hejasverige.megabank.bank import Bank
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
                    data = bank.getInvoices(personalid=orgnr,
                                           invoiceid=invoiceid,
                                           startdate=startdate,
                                           enddate=enddate,
                                           status=status,
                                           outgoing=outgoing)

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
                    data = []

                #import pdb; pdb.set_trace()

                self.request.response.setHeader('Content-Type', 'application/json')
                return data

#class GetInvoiceDetailsView(grok.View):
#    """ Shows details for a specific invoice
#    """
