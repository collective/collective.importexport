# -*- coding: utf-8 -*-
from Products.CMFPlone.interfaces import ISelectableConstrainTypes, IConstrainTypes
from plone.dexterity.utils import iterSchemataForType
from plone.formwidget.namedfile import NamedFileFieldWidget
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
from tempfile import NamedTemporaryFile
from z3c.form import button
from zope.interface import Interface, directlyProvides
from zope import schema
from zope.component import getUtility
from zope.event import notify
from zope.i18n import translate
from zope.lifecycleevent import ObjectModifiedEvent
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile as FiveViewPageTemplateFile

import csv
import logging
import StringIO
import time

log = logging.getLogger(__name__)
KEY_ID = u"_id"

# TODO(ivanteoh): user will pick a PRIMARY_KEY from column name.
PRIMARY_KEY = "Filename"

# TODO(ivanteoh): convert to import config option (csv_col, obj_field)
matching_fields = {
    "Filename": u"filename",
    "Title": u"title",
    "Summary": u"description",
    "IAID": u"iaid",
    "Citable Reference": u"citable_reference",
}


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


def process_file(data, mappings, primary_key):
    """Process the file and return all the values.

    :param data: File content
    :type obj: String
    :param mappings: Map field name with column name
    :type obj: Dictionary
    :returns: All items with matching field object name
    :rtype: List
    """
    io = StringIO.StringIO(data)
    reader = csv.DictReader(io, delimiter=",", dialect="excel", quotechar='"')
    rows = []
    # use IURLNormalizer instead of IIDNormalizer for url id
    normalizer = getUtility(IURLNormalizer)

    # return only fields are needed.
    for row in reader:
        fields = {}

        # set primary_key
        if primary_key not in row:
            continue

        key_value = row[primary_key].decode("utf-8")
        # http://docs.plone.org/develop/plone/misc/normalizing_ids.html
        # Normalizers to safe ids
        fields[KEY_ID] = normalizer.normalize(key_value)

        for key, value in row.items():
            if not key:
                continue
            if key in mappings:
                fields[mappings[key].decode("utf-8")] = \
                    value.decode("utf-8")
        rows.append(fields)
    return rows


def fields_list(context):
    terms = []

    # need to look up all the possible fields we can set on all the content
    # types we might update in the given folder
    found = {}
    if context is None:
        return SimpleVocabulary([])

    #TODO: won't work in the root
    for fti in IConstrainTypes(context).allowedContentTypes():
        portal_type = fti.getId()
        schemas = iterSchemataForType(portal_type)
        for schema in schemas:
            for field in schema:
                if field not in found:
                    found[field] = 1
                    terms.append(SimpleVocabulary.createTerm(field, field, field))


    #for term in ['Slovenia', 'Spain', 'Portugal', 'France']:
    #    terms.append(SimpleVocabulary.createTerm(term, term, term))
    return SimpleVocabulary(terms)
directlyProvides(fields_list, IContextSourceBinder)

def headers_list(context):
    """ use the last upload header info from the last uploaded file
    """


    terms = []
    #for term in ['Slovenia', 'Spain', 'Portugal', 'France']:
    #    terms.append(SimpleVocabulary.createTerm(term, term, term))
    return SimpleVocabulary(terms)
directlyProvides(headers_list, IContextSourceBinder)



def dexterity_import(container, resources, object_type, create_new=False):
    """Import to dexterity-types from file to container."""
    new_count = 0
    existing_count = 0
    ignore_count = 0
    report = []

    if not resources:
        return {"existing_count": existing_count,
                "new_count": new_count,
                "ignore_count": ignore_count,
                "report": report}

    # TODO(ivanteoh): Make sure the object have all the valid keys
    # keys = resources[0].keys()
    # hasProperty, getProperty not working

    catalog = api.portal.get_tool(name="portal_catalog")
    container_path = "/".join(container.getPhysicalPath())

    # TODO(ivanteoh): Make sure container is either folder or SiteRoot
    # import pdb; pdb.set_trace()

    for resource in resources:
        obj = None

        # should not have u"id" in the dictionary
        assert u"id" not in resource
        assert u"type" not in resource
        assert u"container" not in resource
        assert u"safe_id" not in resource

        # must have either u"id" or u"title"
        # primary_key value will be used as id
        id_key = resource[KEY_ID]

        key_arg = dict(resource)
        if KEY_ID in key_arg:
            del key_arg[KEY_ID]

        # find existing obj
        results = catalog(
            portal_type=object_type,
            path={"query": container_path, "depth": 1},
            id=id_key
        )

        if results:
            obj = results[0].getObject()
            for key, value in key_arg.items():
                # does not update metadata
                setattr(obj, key, value)
            # TODO(ivanteoh): any performance risk by calling this?
            notify(ObjectModifiedEvent(obj))
            existing_count += 1
        elif create_new:
            # Save the objects in this container
            obj = api.content.create(
                type=object_type,
                id=id_key,
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
        report.append(key_arg)

    # Later if want to rename
    # api.content.rename(obj=portal["blog"], new_id="old-blog")
    return {"existing_count": existing_count,
            "new_count": new_count,
            "ignore_count": ignore_count,
            "report": report}


def export_file(request, result):
    normalizer = getUtility(IIDNormalizer)
    random_id = normalizer.normalize(time.time())
    filename = "export_{0}.{1}".format(random_id, 'csv')
    with NamedTemporaryFile(mode='wb') as tmpfile:
        writer = csv.DictWriter(tmpfile, result.keys())
        # writer.writeheader()
        writer.writerow(result)
        tmpfile.seek(0)
        request.response.setHeader('Content-Type', 'text/csv')
        request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="%s"' % filename)
        return file(tmpfile.name).read()

terms = [
    schema.vocabulary.SimpleTerm(*value) for value in
    [("A", "A", "A"), ("B", "B", "B"),
     ("C", "C", "C"), ("D", "D", "D")]]
vocabularies = schema.vocabulary.SimpleVocabulary(terms)




class IImportSchema(form.Schema):
    """Define fields used on the form."""

    import_file = NamedFile(
        title=_(
            "import_field_import_file_title",  # nopep8
            default=u"Import File"),
        description=_(
            "import_field_import_file_description",  # nopep8
            default=u"In CSV format."),
        required=True
    )
#    form.widget('header_mapping', NamedFileFieldWidget)
    header_mapping = schema.Dict(
        title=_(u'Header Mapping'),
        description=_(u"Any matching headers in your CSV will be mapped to "
                      u"these fields"),
        key_type=schema.TextLine(title=u"header"),
        value_type=schema.Choice(source=fields_list, title=u"field"),
        #default={'table th td': 'width height'},
        missing_value={},
        required=False)
    import_columns = schema.List(
        title=_(
            "import_field_import_columns_title",  # nopep8
            default=u"Import Columns"),
        description=_(
            "import_field_import_columns_description",  # nopep8
            default=u"The order of these columns will match with "
                    u"the object fields below."),
        value_type=schema.Choice(
            values=("A", "B", "C", "D")),
        default=["D", "B"]
    )
    primary_key = schema.Choice(
        title=_(
            "import_field_primary_key_title",  # nopep8
            default=u"Primary Key"),
        description=_(
            "import_field_primary_key_description",
            default=u"Select one of the column name as primary key, "
                    u"which will used as ID when creation or "
                    u"finding existing objects."),
        vocabulary=vocabularies,
        required=True
    )
    object_type = schema.Choice(
        title=_(
            "import_field_object_type_title",  # nopep8
            default=u"Object Type"),
        description=_(
            "import_field_object_type_description",
            default=u"Content type of the import object, "
                    u"which is created or updated when "
                    u"importing from the file."),
        vocabulary='plone.app.vocabularies.ReallyUserFriendlyTypes',
        required=True
    )
    object_fields = schema.List(
        title=_(
            "import_field_object_fields_title",  # nopep8
            default=u"Object Fields"),
        description=_(
            "import_field_object_fields_description",  # nopep8
            default=u"The order of these fields will match with "
                    u"import columns above."),
        value_type=schema.Choice(
            values=(1, 2, 3, 4)),
        default=[1, 3]
    )
    create_new = schema.Bool(
        title=_(
            "import_field_create_new_title",  # nopep8
            default=u"Create New"),
        description=_(
            "import_field_create_new_description",  # nopep8
            default=u"It will create new object if doesn't exist "
                    u"based from the primary key. "
                    u"Or else it will be ignored."),
    )


class ImportForm(form.SchemaForm):
    """Import data to dexterity-types."""

    # Which plone.directives.form.Schema subclass is used to define
    # fields for this form
    schema = IImportSchema
    ignoreContext = True

    # Form label
    label = _("import_form_label",  # nopep8
              default=u"Import")
    description = _("import_form_description",  # nopep8
                    default=u"Import data to dexterity-types objects.")


    def save_data(self, data):
        # TODO(ivanteoh): save date using Annotation Adapter
        pass

    def updateWidgets(self):
        # TODO: Maybe here take the header from the request and use it to set
        # defaults on the header_mapping.

        super(ImportForm, self).updateWidgets()
        self.widgets['import_file'].onselect = u"alert('got this');"

    @button.buttonAndHandler(_("import_button_save", default=u"Save"))  # nopep8
    def handleSave(self, action):
        """Create and handle form button "Save"."""

        # Extract form field values and errors from HTTP request
        data, errors = self.extractData()
        if errors:
            return False

        self.save_data(data)

        api.portal.show_message(
            message=_("import_message_save",  # nopep8
                default=u"Import settings saved."),
            request=self.request,
            type="info")
        self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(_("import_button_save_import",  # nopep8
                               default=u"Save and Import"))
    def handleSaveImport(self, action):
        """Create and handle form button "Save and Import"."""

        # Extract form field values and errors from HTTP request
        data, errors = self.extractData()
        if errors:
            return False

        self.save_data(data)

        data, errors = self.extractData()
        if errors:
            return False

        import_file = data["import_file"]
        create_new = data["create_new"]
        object_type = data["object_type"]

        if import_file:

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

            # based from the matching fields, get all the values.
            rows = process_file(file_resource, matching_fields, PRIMARY_KEY)
            log.debug(rows)

            import_metadata = dexterity_import(
                self.context,
                rows,
                object_type,
                create_new
            )

            existing_count = import_metadata["existing_count"]
            new_count = import_metadata["new_count"]
            ignore_count = import_metadata["ignore_count"]

            api.portal.show_message(
                message=_("import_message_csv_info",  # nopep8
                    default=u"""${new_num} items added,
                        ${existing_num} items updated and
                        ${ignore_num} items not added
                        from ${filename}""",
                    mapping={"new_num": new_count,
                        "existing_num": existing_count,
                        "ignore_num": ignore_count,
                        "filename": file_name}),
                request=self.request,
                type="info")

        else:
            api.portal.show_message(
                message=_("import_message_csv_error",  # nopep8
                    default=u"Please provide a csv file."),
                request=self.request,
                type="error")

        # self.request.response.redirect(self.context.absolute_url())

        # export to csv file
        return export_file(self.request, import_metadata["report"])

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
