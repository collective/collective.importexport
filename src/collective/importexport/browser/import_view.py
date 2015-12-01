# -*- coding: utf-8 -*-
from Products.CMFCore.interfaces import IFolderish
from Products.CMFPlone.interfaces import ISelectableConstrainTypes, IConstrainTypes
from plone.dexterity.utils import iterSchemataForType
from plone.formwidget.namedfile import NamedFileFieldWidget
from z3c.form.interfaces import NO_VALUE
from zope.schema import getFieldsInOrder
from zope.schema._bootstrapinterfaces import IContextAwareDefaultFactory
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
from collective.importexport import _
from operator import itemgetter
from plone import api
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import iterSchemataForType
from plone.directives import form
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.i18n.normalizer.interfaces import IURLNormalizer
from plone.namedfile.field import NamedFile
from plone.z3cform.layout import wrap_form
from Products.CMFPlone.utils import safe_unicode
from z3c.form import button
from zope.interface import Interface, directlyProvides, provider
from zope import schema
from zope.component import getUtility
from zope.event import notify
from zope.i18n import translate
from zope.lifecycleevent import ObjectModifiedEvent
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile as FiveViewPageTemplateFile
from collective.z3cform.datagridfield import DataGridFieldFactory, DictRow

import csv
import logging
import StringIO
import time

log = logging.getLogger(__name__)
KEY_ID = u"_id"

# TODO(ivanteoh): user will pick a PRIMARY_KEY from column name.
PRIMARY_KEY = "Filename"

# TODO(ivanteoh): convert to import config option (csv_col, obj_field)
#matching_fields = {
#    u"Filename": u"filename",
#    u"Title": u"title",
#    u"Summary": u"description",
#    u"IAID": u"iaid",
#    u"Citable Reference": u"citable_reference",
#}
#
## TODO(ivanteoh): convert to export config option
#output_orders = [
#    (u"id", u"ID"),
#    (u"title", u"Title"),
#    (u"description", u"Description"),
#    (u"filename", u"Filename"),
#    (u"iaid", u"IAID"),
#    (u"citable_reference", u"Citable Reference"),
#]


def get_portal_types(request, all=True):
    """A list with info on all dexterity content types with existing items.

    :param request: Request for translation
    :type obj: Request object
    :param all: True for including all Dexterity content types
    :type obj: Boolean
    :returns: Dexterity content types
    :rtype: List
    """
    catalog = api.portal.get_tool("portal_catalog")
    portal_types = api.portal.get_tool("portal_types")
    results = []
    for fti in portal_types.listTypeInfo():
        if not IDexterityFTI.providedBy(fti):
            continue
        number = len(catalog(portal_type=fti.id))
        if number >= 1 or all:
            results.append({
                "number": number,
                "type": fti.id,
                "title": translate(
                    fti.title, domain="plone", context=request)
            })
    return sorted(results, key=itemgetter("title"))


# TODO(ivanteoh): Not used, remove later
def get_schema_info(portal_type):
    """Get a flat list of all fields in all schemas for a content-type.

    :param data: Dexterity content type
    :type obj: String
    :returns: All fields on this object
    :rtype: List
    """
    fields = []
    for schema_items in iterSchemataForType(portal_type):
        for fieldname in schema_items:
            fields.append((fieldname, schema_items.get(fieldname)))
    return fields


# TODO(ivanteoh): Not used, remove later
def _get_prop(prop, item, default=None):
    """Get value from prop as key in dictionary item."""
    ret = default
    if prop in item:
        ret = safe_unicode(item[prop])
    return ret



def dexterity_import(container, data, mappings, object_type, create_new=False,
                     primary_key='id'):
    """Import to dexterity-types from file to container."""
    new_count = 0
    existing_count = 0
    ignore_count = 0
    report = []


    # TODO(ivanteoh): Make sure the object have all the valid keys
    # keys = resources[0].keys()
    # hasProperty, getProperty not working

    catalog = api.portal.get_tool(name="portal_catalog")
    container_path = "/".join(container.getPhysicalPath())

    # TODO(ivanteoh): Make sure container is either folder or SiteRoot
    # import pdb; pdb.set_trace()

    io = StringIO.StringIO(data)
    reader = csv.DictReader(io, delimiter=",", dialect="excel", quotechar='"')
    rows = []
    if not reader:
        return {"existing_count": existing_count,
                "new_count": new_count,
                "ignore_count": ignore_count,
                "report": report}

    # use IURLNormalizer instead of IIDNormalizer for url id
    normalizer = getUtility(IURLNormalizer)

    # return only fields are needed.
    for row in reader:

        ## set primary_key
        #if primary_key not in row:
        #    continue

        #key_value = row[primary_key].decode("utf-8")
        ## http://docs.plone.org/develop/plone/misc/normalizing_ids.html
        ## Normalizers to safe ids
        #fields[KEY_ID] = normalizer.normalize(key_value)

        key_arg = {}
        for key, value in row.items():
            if not key:
                continue
            if key in mappings:
                key_arg[mappings[key].decode("utf-8")] = \
                    value.decode("utf-8")


        obj = None

        # should not have u"id" in the dictionary
        #assert u"id" not in resource
        assert u"type" not in key_arg
        assert u"container" not in key_arg
        assert u"safe_id" not in key_arg


        # find existing obj
        # TODO: this is wrong since indexs aren't always the same as fields
        if primary_key in key_arg:
            query = dict(path={"query": container_path, "depth": 1},
    #                    portal_type=object_type,
                         )
            query[primary_key]=key_arg[primary_key]
            results = catalog(**query)
            # special case because id gets normalised.
            # try and guess the normalised id
            if len(results) == 0 and primary_key == 'id':
                query[primary_key] = normalizer.normalize(key_arg[primary_key])
                results = catalog(**query)
        else:
            results = []

        if len(results) > 1:
            assert "Primary key must be unique"
        elif len(results) == 1:
            obj = results[0].getObject()
            for key, value in key_arg.items():
                # does not update metadata
                if key == 'id':
                    #TODO: handle renaming later
                    continue
                setattr(obj, key, value)
            # TODO(ivanteoh): any performance risk by calling this?
            notify(ObjectModifiedEvent(obj))
            existing_count += 1
        elif create_new:
            # Save the objects in this container
            obj = api.content.create(
                type=object_type,
                container=container,
                safe_id=True,
                **key_arg
            )
            new_count += 1
        else:
            ignore_count += 1
            continue

        assert obj.id

        # generate report for csv export
        key_arg[u"id"] = obj.id
        key_arg[u'url'] = obj.absolute_url()
        report.append(key_arg)

    # Later if want to rename
    # api.content.rename(obj=portal["blog"], new_id="old-blog")
    return {"existing_count": existing_count,
            "new_count": new_count,
            "ignore_count": ignore_count,
            "report": report}


def export_file(result, header_mapping):
    if not result:
        return None,None

    normalizer = getUtility(IIDNormalizer)
    random_id = normalizer.normalize(time.time())
    file_name = "export_{0}.{1}".format(random_id, 'csv')
    csv_file = StringIO.StringIO()
    writer = csv.writer(csv_file, delimiter=",", dialect="excel", quotechar='"')
    columns = [d['header'] for d in header_mapping]
    writer.writerow(columns)
    for row in result:
        items = []
        if getattr(row, 'getObject', None):
            obj = row.getObject()
        else:
            obj = None
        for d in header_mapping:
            #TODO: need to get from the objects themselves in case the data
            # has been transformed
            if obj is None:
                items.append(row[d['field']])
            else:
                items.append(getattr(obj,d['field']))
        log.debug(items)
        writer.writerow(items)
    csv_attachment = csv_file.getvalue()
    csv_file.close()
    return (file_name, csv_attachment)

terms = [
    schema.vocabulary.SimpleTerm(*value) for value in
    [("A", "A", "A"), ("B", "B", "B"),
     ("C", "C", "C"), ("D", "D", "D")]]
vocabularies = schema.vocabulary.SimpleVocabulary(terms)


def get_allowed_types(context):
    if context is NO_VALUE or not context or not IFolderish.providedBy(context):
        #return SimpleVocabulary(terms)
        from zope.globalrequest import getRequest
        req = getRequest()
        for parent in req.PARENTS:
            if IFolderish.providedBy(parent):
                context = parent
                break

    #TODO: won't work in the root
    if IConstrainTypes.providedBy(context):
        types = IConstrainTypes(context).getImmediatelyAddableTypes()
    else:
        types = context.allowedContentTypes()
    return types

@provider(IContextSourceBinder)
def fields_list(context):
    terms = []

    # need to look up all the possible fields we can set on all the content
    # types we might update in the given folder
    found = {}
    terms = [SimpleVocabulary.createTerm('', '', '')]

    for fti in get_allowed_types(context):
        portal_type = fti.getId()
        schemas = iterSchemataForType(portal_type)
        for schema in schemas:
            for fieldid, field in getFieldsInOrder(schema):
                if fieldid not in found:
                    found[fieldid] = 1
                    #title = "%s (%s)" % (_(field.title), fieldid)
                    title = _(field.title)
                    terms.append(SimpleVocabulary.createTerm(fieldid, fieldid,
                                                             title))


    #for term in ['Slovenia', 'Spain', 'Portugal', 'France']:
    #    terms.append(SimpleVocabulary.createTerm(term, term, term))
    return SimpleVocabulary(terms)

@provider(IContextSourceBinder)
def if_not_found_list(context):
    terms = [SimpleVocabulary.createTerm('__ignore__', '__ignore__', 'Skip'),
             SimpleVocabulary.createTerm('__stop__', '__stop__', 'Stop')]


    for fti in get_allowed_types(context):
        portal_type = fti.getId()
        terms.append(SimpleVocabulary.createTerm(portal_type, portal_type,
                                                 "Create %s" % fti.title))
    return SimpleVocabulary(terms)



@provider(IContextAwareDefaultFactory)
def headersFromRequest(context):
    from zope.globalrequest import getRequest
    request = getRequest()
    fields = fields_list(None)
    rows = []
    if request.get('csv_header'):
        #TODO: use csv reader here
        for col in request.get('csv_header').split(','):
            matched_field = ''
            if not col.strip():
                continue
            #TODO: try to guess field from header
            for field in fields:
                if col.lower() == field.title.lower() or \
                   col.lower() == field.value.lower():
                    matched_field = field.value
                    break
            rows.append(dict(header=col, field=matched_field))
    return rows

class IMappingRow(form.Schema):
    header = schema.TextLine(title=u"CSV Header")
    field = schema.Choice(source=fields_list, title=u"Internal Field")


class IImportSchema(form.Schema):
    """Define fields used on the form."""

    import_file = NamedFile(
        title=_(
            "import_field_import_file_title",  # nopep8
            default=u"CSV metadata to import"),
        description=_(
            "import_field_import_file_description",  # nopep8
            default=u"CSV file containing rows for each content to create or update"),
        required=False
    )
#    form.widget('header_mapping', NamedFileFieldWidget)
    header_mapping = schema.List(
        title=_(u'Header Mapping'),
        description=_(u"Any matching headers in your CSV will be mapped to "
                      u"these fields"),
        value_type=DictRow(title=u"tablerow", schema=IMappingRow),
        defaultFactory=headersFromRequest,
        missing_value={},
        required=False)

    primary_key = schema.Choice(
        title=_(
            "import_field_primary_key_title",  # nopep8
            default=u"Test if content exists using"),
        description=_(
            "import_field_primary_key_description",
            default=u"Field to use to check if content already exists"
            ),
        source=fields_list, #TODO: should be index not fieldname
        required=True
    )
    object_type = schema.Choice(
        title=_(
            "import_field_object_type_title",  # nopep8
            default=u"If not found"),
        description=_(
            "import_field_object_type_description",
            default=u"Content type of the import object, "
                    u"which is created or updated when "
                    u"importing from the file."),
        #vocabulary='plone.app.vocabularies.ReallyUserFriendlyTypes',
        source = if_not_found_list,
        #TODO: should be only locally addable types
        required=True
    )
    #result_as_csv = schema.Bool(
    #    title=_(
    #        "csv_report",  # nopep8
    #        default=u"Report as CSV"),
    #    description=_(
    #        "csv_report_description",  # nopep8
    #        default=u"return a CSV with urls of imported content"),
    #)



class ImportForm(form.SchemaForm):
    """Import data to dexterity-types."""

    # Which plone.directives.form.Schema subclass is used to define
    # fields for this form
    schema = IImportSchema
    ignoreContext = True

    # Form label
    label = _("import_form_label",  # nopep8
              default=u"CSV Import/Export")
    description = _("import_form_description",  # nopep8
                    default=u"Create or Update content from a CSV")


    def save_data(self, data):
        # TODO(ivanteoh): save date using Annotation Adapter
        pass

    def updateWidgets(self):
        self.fields['header_mapping'].widgetFactory = DataGridFieldFactory
        # get around a bug. not sure whose fault it is.
        # seems likely is the datagrid field
        self.fields['header_mapping'].field.bind(self.context)
        super(ImportForm, self).updateWidgets()


    #@button.buttonAndHandler(_("import_button_save", default=u"Import CSV"))  # nopep8
    #def handleSave(self, action):
    #    """Create and handle form button "Save"."""
    #
    #    # Extract form field values and errors from HTTP request
    #    data, errors = self.extractData()
    #    if errors:
    #        return False
    #
    #    self.save_data(data)
    #
    #    api.portal.show_message(
    #        message=_("import_message_save",  # nopep8
    #            default=u"Import settings saved."),
    #        request=self.request,
    #        type="info")
    #    self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(_("import_button_save_import",  # nopep8
                               default=u"CSV Import"))
    def handleSaveImport(self, action):
        """Create and handle form button "Save and Import"."""

        # Extract form field values and errors from HTTP request
        data, errors = self.extractData()
        if errors:
            return False

        self.save_data(data)

        import_file = data["import_file"]
        if data["object_type"] in ['__ignore__', '__stop__']:
            create_new = False
            object_type = None
        else:
            create_new = True
            object_type = data["object_type"]

        if not import_file:
            api.portal.show_message(
                message=_("import_message_csv_error",  # nopep8
                    default=u"Please provide a csv file."),
                request=self.request,
                type="error")
            return

        # File upload is not saved in settings
        file_resource = import_file.data
        file_name = import_file.filename

        # TODO(ivanteoh): use import_file.contentType to check csv file ext

        # list all the dexterity types
        dx_types = get_portal_types(self.request)
        log.debug(dx_types)

        # based from the types, display all the fields
        # fields = get_schema_info(CREATION_TYPE)
        # log.debug(fields)

        # blank header or field means we don't want it
        header_mapping = [d for d in data['header_mapping'] if d['field'] and d['header']]

        matching_fields = dict([(d['header'],d['field']) for d in header_mapping])

        # based from the matching fields, get all the values.
        import_metadata = dexterity_import(
            self.context,
            file_resource,
            matching_fields,
            object_type,
            create_new,
            data["primary_key"]
        )

        existing_count = import_metadata["existing_count"]
        new_count = import_metadata["new_count"]
        ignore_count = import_metadata["ignore_count"]

        api.portal.show_message(
            message=_("import_message_csv_info",  # nopep8
                default=u"""${new_num} items added,
                    ${existing_num} items updated and
                    ${ignore_num} items skipped
                    from ${filename}""",
                mapping={"new_num": new_count,
                    "existing_num": existing_count,
                    "ignore_num": ignore_count,
                    "filename": file_name}),
            request=self.request,
            type="info")


        self.import_metadata = import_metadata
        return True


    @button.buttonAndHandler(_("import___button_import_export",  # nopep8
                               default=u"Import and Export Changes"))
    def handleImportExport(self, action):

        if not self.handleSaveImport(self, action):
            return False

        data, errors = self.extractData()
        if errors:
            return False

        # blank header or field means we don't want it
        header_mapping = [d for d in data['header_mapping'] if d['field'] and d['header']]


        # export to csv file
        # import pdb; pdb.set_trace()
        if self.import_metadata["report"]:
            filename, attachment = export_file(self.import_metadata["report"],
                                               header_mapping)
            self.request.response.setHeader('content-type', 'text/csv')
            self.request.response.setHeader(
                'Content-Disposition',
                'attachment; filename="%s"' % filename)
            self.request.response.setBody(attachment, lock=True)

        #self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(_("import___button_export",  # nopep8
                               default=u"CSV Export"))
    def handleExport(self, action):
        # Extract form field values and errors from HTTP request
        data, errors = self.extractData()
        if errors:
            return False
        container = self.context
        container_path = "/".join(container.getPhysicalPath())
        #TODO: should we allow more criteria? or at least filter by type?
        query = dict(path={"query": container_path, "depth": 1},
#                    portal_type=object_type,
                     )
#        query[primary_key]=key_arg[primary_key]

        # blank header or field means we don't want it
        header_mapping = [d for d in data['header_mapping'] if d['field'] and d['header']]


        catalog = api.portal.get_tool("portal_catalog")
        results = catalog(**query)
        filename, attachment = export_file(results, header_mapping)
        #log.debug(filename)
        #log.debug(attachment)
        self.request.response.setHeader('content-type', 'text/csv')
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="%s"' % filename)
        self.request.response.setBody(attachment, lock=True)
        return True


    @button.buttonAndHandler(u"Cancel")
    def handleCancel(self, action):
        api.portal.show_message(
            message=_("import_message_cancel",  # nopep8
                default="Import canceled."),
            request=self.request,
            type="info")
        self.request.response.redirect(self.context.absolute_url())




# IF you want to customize form frame you need to make a custom FormWrapper view around it
# (default plone.z3cform.layout.FormWrapper is supplied automatically with form.py templates)
#report_form_frame = plone.z3cform.layout.wrap_form(ReportForm, index=FiveViewPageTemplateFile("templates/reporter.pt"))
ImportView = wrap_form(ImportForm, index=FiveViewPageTemplateFile("import_view.pt"))
