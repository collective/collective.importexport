# -*- coding: utf-8 -*-
from collective.importexport import _
from operator import itemgetter
from plone import api
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import iterSchemataForType
from plone.directives import form
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.namedfile.field import NamedFile
from plone.z3cform.layout import wrap_form
from Products.CMFPlone.utils import safe_unicode
from z3c.form import button
from zope.component import getUtility
from zope.i18n import translate

import csv
import logging
import StringIO
import time

log = logging.getLogger(__name__)

# TODO(ivanteoh): convert to import config option (csv_col, obj_field)
matching_fields = {
#    "Filename": u"filename",
    "Title": u"title",
    "Summary": u"description",
#    "IAID": u"iaid",
#    "Citable Reference": u"citable_reference",
}


def get_portal_types(request, all=True):
    """A list with info on all dexterity content types with existing items.

    """
    catalog = api.portal.get_tool('portal_catalog')
    portal_types = api.portal.get_tool('portal_types')
    results = []
    for fti in portal_types.listTypeInfo():
        if not IDexterityFTI.providedBy(fti):
            continue
        number = len(catalog(portal_type=fti.id))
        if number >= 1 or all:
            results.append({
                'number': number,
                'type': fti.id,
                'title': translate(
                    fti.title, domain='plone', context=request)
            })
    return sorted(results, key=itemgetter('title'))


def get_schema_info(portal_type):
    """Get a flat list of all fields in all schemas for a content-type."""
    fields = []
    for schema in iterSchemataForType(portal_type):
        for fieldname in schema:
            fields.append((fieldname, schema.get(fieldname)))
    return fields


def _get_prop(prop, item, default=None):
    """Get value from prop as key in dictionary item."""
    ret = default
    if prop in item:
        ret = safe_unicode(item[prop])
    return ret


def process_file(data, mappings):
    """Process the file and return all the values.

    @param data: file content.

    @param mappings: map field name with column name.
    """
    io = StringIO.StringIO(data)
    reader = csv.DictReader(io, delimiter=",", dialect="excel", quotechar='"')
    rows = []

    # return only fields are needed.
    for row in reader:
        fields = {}
        for key, value in row.items():
            if not key:
                continue
            if key in mappings:
                fields[mappings[key].decode("utf-8")] = \
                    value.decode("utf-8")
        rows.append(fields)

    return rows


def dexterity_import(container, resources, creation_type, primary_key=None):
    """Import to dexterity-types from file to container."""
    count = 0

    if not resources:
        return {"count": count}

    # TODO(ivanteoh): Make sure the object have all the keys
    # keys = resources[0].keys()
    # hasProperty, getProperty not working

    # cat = api.portal.get_tool(name="portal_catalog")
    # container_path = '/'.join(container.getPhysicalPath())

    # TODO(ivanteoh): Make sure container is either folder or SiteRoot
    normalizer = getUtility(IIDNormalizer)

    for resource in resources:
        obj = None

        # primary_key must be either u"id" or u"title"
        if primary_key:
            # Normalizers to safe ids

            # Save the objects in this container
            obj = api.content.create(
                type=creation_type,
                id=normalizer.normalize(resource[primary_key]),
                container=container)

        if not obj and u"title" in resource:
            # Save the objects in this container
            obj = api.content.create(
                type=creation_type,
                title=resource[u"title"],
                container=container)

        # http://docs.plone.org/develop/plone/misc/normalizing_ids.html
        if not obj:
            obj = api.content.create(
                type=creation_type,
                id=time.time(),
                container=container)

        assert obj.id

        for key, value in resource.items():
            if key != u"id" or key != u"title":
                setattr(obj, key, value)

        count += 1

    # Later if want to rename
    # api.content.rename(obj=portal['blog'], new_id='old-blog')
    return {"count": count}


class IImportSchema(form.Schema):
    """Define fields used on the form."""

    import_file = NamedFile(
        title=_("import_field_file_title",  # nopep8
                default=u"Import File"),
        description=_("import_field_file_description",  # nopep8
                      default=u"In CSV format."),
        required=True)


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

    def updateWidgets(self):
        super(ImportForm, self).updateWidgets()

    def save_data(self, data):
        # TODO(ivanteoh): save date using Annotation Adapter
        pass

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

        if import_file:

            # File upload is not saved in settings
            file_resource = import_file.data
            file_name = import_file.filename
            #import pdb; pdb.set_trace()

            # TODO(ivanteoh): use import_file.contentType to check csv file ext

            # list all the dexterity types
            dx_types = get_portal_types(self.request)
            log.debug(dx_types)
            # TODO(ivanteoh): user will pick a types.

            creation_type = "Document"
            # creation_type = "WildcardVideo"

            # based from the types, display all the fields
            fields = get_schema_info(creation_type)
            log.debug(fields)

            # based from the matching fields, get all the values.
            rows = process_file(file_resource, matching_fields)
            log.debug(rows)

            import_metadata = dexterity_import(
                self.context,
                rows,
                creation_type
            )

            count = import_metadata["count"]

            api.portal.show_message(
                message=_("import_message_csv_info",  # nopep8
                    default=u"${num} items imported from ${filename}",
                    mapping={'num': count, 'filename': file_name}),
                request=self.request,
                type="info")

        else:
            api.portal.show_message(
                message=_("import_message_csv_error",  # nopep8
                    default=u"Please provide a csv file."),
                request=self.request,
                type="error")

        self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(u'Cancel')
    def handleCancel(self, action):
        api.portal.show_message(
            message=_("import_message_cancel",  # nopep8
                default="Import canceled."),
            request=self.request,
            type="info")
        self.request.response.redirect(self.context.absolute_url())

ImportView = wrap_form(ImportForm)
