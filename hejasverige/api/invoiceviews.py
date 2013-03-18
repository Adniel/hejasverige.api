# -*- coding: utf-8 -*-

import json
import StringIO

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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# TODO:
#   - set owner and permissions on created invoice to recipient
#   - validate the read json/return json schema when @@create-invoice?schema
#   - set grok.require to correct permission (some api permission)
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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

    def render(self):

        if self.request['QUERY_STRING'] == 'schema':
            data = self.get_schema()
            self.request.response.setStatus(200, "")
            return data
        else:
            payload = self.request.get('BODY')

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
                print 'No boundry found...'
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
                    data = 'No or empty invoice-data part received'
                    self.request.response.setStatus(422, "")
                    return data

            try:
                #import pdb
                #pdb.set_trace()
                objfields = json.loads(invoicedata)
            except Exception, ex:
                data = 'Error creating json object from invoice-data part', ex
                self.request.response.setStatus(400, "")
                return data
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
                    #import pdb
                    #pdb.set_trace()

                    print item.id
                except Exception, ex:
                    data = 'Could not create invoice object', ex
                    self.request.response.setStatus(500, "")
                    return data


            data = "ID=" + item.id
            self.request.response.setStatus(201, "")
            #import pdb; pdb.set_trace()
            return data
