# -*- coding: utf-8 -*-
from AccessControl.security import checkPermission
from Products.CMFCore.interfaces import IFolderish
from Products.CMFPlone.interfaces import ISelectableConstrainTypes, IConstrainTypes
from plone.dexterity.utils import iterSchemataForType
from plone.formwidget.namedfile import NamedFileFieldWidget
from z3c.form.interfaces import NO_VALUE, WidgetActionExecutionError
from zope.annotation import IAnnotations
from zope.globalrequest import getRequest
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import IContextSourceBinder, IText, IBytes, IInt, IFloat, IDecimal, IChoice
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
from zope.interface import Interface, directlyProvides, provider, Invalid, implements
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

KEY = "collective.importoutput.settings"


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

    reader = csv.DictReader(data.splitlines(),
                            delimiter=",",
                            dialect="excel",
                            quotechar='"')
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

        #TODO: need to implement stop feature

        if len(results) > 1:
            assert "Primary key must be unique"
            continue
        elif len(results) == 1:
            obj = results[0].getObject()
            # TODO: get checkPermission working right
            #if not checkPermission("Modify portal content", obj):
            #    #TODO: We should have a different catagory of skipped
            #    ignore_count += 1
            #    continue
            for key, value in key_arg.items():
                # does not update metadata
                if key == 'id' or key == 'path':
                    #TODO: handle renaming later
                    continue
                #TODO: we should be validating against schemas here
                #TODO: validate against individual field permissions
                elif hasattr(obj,key):
                    setattr(obj, key, value)
            # TODO(ivanteoh): any performance risk by calling this?
            #TODO: only do this is we changed somthing
            notify(ObjectModifiedEvent(obj))
            existing_count += 1
        elif create_new:
            #TODO: handle creating using passed in path. ie find/create folders
            # Save the objects in this container

            #TODO: validate we either have a id or title (or make random ids)

            #TODO: currently lets you create files without a require file field
            #which breaks on view
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
        key_arg[u'path'] = obj.absolute_url()
        report.append(obj)

    # Later if want to rename
    # api.content.rename(obj=portal["blog"], new_id="old-blog")
    return {"existing_count": existing_count,
            "new_count": new_count,
            "ignore_count": ignore_count,
            "report": report}


def export_file(result, header_mapping, request):
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
            obj = row
        for d in header_mapping:
            #TODO: need to get from the objects themselves in case the data
            # has been transformed
            if obj is None:
                items.append(row[d['field']])
            else:
                if d['field'] == 'path':
                    path = obj.getPhysicalPath()
                    virtual_path = request.physicalPathToVirtualPath(path)
                    items.append('/'.join(virtual_path))
                else:
                    items.append(getattr(obj,d['field']))
        log.debug(items)
        writer.writerow(items)
    csv_attachment = csv_file.getvalue()
    csv_file.close()
    return (file_name, csv_attachment)

def getContext(context=None):
    if context is NO_VALUE or context is None or not IFolderish.providedBy(context):
        #return SimpleVocabulary(terms)
        req = getRequest()
        for parent in req.PARENTS:
            if IFolderish.providedBy(parent):
                context = parent
                break
    return context


def get_allowed_types(context):
    context = getContext(context)

    if IConstrainTypes.providedBy(context):
        types = IConstrainTypes(context).getImmediatelyAddableTypes()
    else:
        types = context.allowedContentTypes()
    return types


FIELD_LIST_CACHE = "collective.importexport.field_list"
@provider(IContextSourceBinder)
def fields_list(context):
    portal = api.portal.get()
    ttool = api.portal.getToolByName(portal, 'translation_service')

    #annotations = IAnnotations(portal.request)
    #value = annotations.get(FIELD_LIST_CACHE, None)
    #if value is not None:
    #    return value

    terms = []

    # need to look up all the possible fields we can set on all the content
    # types we might update in the given folder
    found = {}
    terms = [SimpleVocabulary.createTerm('', '', ''),
             SimpleVocabulary.createTerm('path', 'path', 'Path')]
    # path is special and allows us to import to dirs and export resulting path

    allowed_types = [IText, IBytes, IInt, IFloat, IDecimal, IChoice]

    for fti in get_allowed_types(context):
        portal_type = fti.getId()
        schemas = iterSchemataForType(portal_type)
        for _schema in schemas:
            for fieldid, field in getFieldsInOrder(_schema):

                if not any([ftype.providedBy(field) for ftype in allowed_types]):
                    continue

                if fieldid not in found:
                    found[fieldid] = 1
                    title = ttool.translate(field.title)
                    if not title:
                        continue
                    terms.append(SimpleVocabulary.createTerm(fieldid, fieldid,
                                                             title))

    value = SimpleVocabulary(terms)
    #annotations[FIELD_LIST_CACHE] = value
    return value


@provider(IContextSourceBinder)
def if_not_found_list(context):
    terms = [SimpleVocabulary.createTerm('__ignore__', '__ignore__', 'Skip'),
             SimpleVocabulary.createTerm('__stop__', '__stop__', 'Stop')]


    for fti in get_allowed_types(context):
        portal_type = fti.getId()
        terms.append(SimpleVocabulary.createTerm(portal_type, portal_type,
                                                 "Create %s" % fti.title))
    return SimpleVocabulary(terms)



class IMappingRow(form.Schema):
    header = schema.TextLine(title=u"CSV Header", required=False)
    field = schema.Choice(source=fields_list,
                          title=u"Internal Field",
                          required=False)


class IImportSchema(form.Schema):
    """Define fields used on the form."""

    #TODO: need to get rid of "Keep existing file" etc. It's confusing
    # suspect this is the wrong field type
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
        missing_value={},
        required=False)

    primary_key = schema.Choice(
        title=_(
            "import_field_primary_key_title",  # nopep8
            default=u"Test if content exists using"),
        description=_(
            "import_field_primary_key_description",
            default=u"Field with unique id to use to check if content already exists. "
            "Normally 'Short Name' or 'Path'."
            ),
        source=fields_list, #TODO: should be index not fieldname
        required=True,
        default=u"id"
    )
    object_type = schema.Choice(
        title=_(
            "import_field_object_type_title",  # nopep8
            default=u"If not found"),
        description=_(
            "import_field_object_type_description",
            default=u"If content can't be found then Create, Skip or Stop at that row. "
                    u"For rich media such as Videos, upload first."),
        source = if_not_found_list,
        required=True
    )


class ImportForm(form.SchemaForm):
    """Import data to dexterity-types."""

    # Which plone.directives.form.Schema subclass is used to define
    # fields for this form
    schema = IImportSchema
    ignoreContext = False

    # Form label
    label = _("import_form_label",  # nopep8
              default=u"CSV Import/Export")
    description = _("import_form_description",  # nopep8
                    default=u"Create or Update content from a CSV. "
    u"For images, files, videos or html documents, use Upload first and use "
    u"CSV import to set the metadata of the uploaded files.")

    def getContent(self):
        """ """

        # Create a temporary object holding the settings values out of the patient

        class TemporarySettingsContext(object):
            implements(IImportSchema)

        obj = TemporarySettingsContext()

        annotations = IAnnotations(self.context)
        settings = annotations.get(KEY)
        if settings:
            obj.primary_key = settings['primary_key']
            obj.object_type = settings['object_type']

        obj.header_mapping = self.headersFromRequest()
        return obj


    def headersFromRequest(self):
        rows = []
        request = self.request
        context = self.context

        # try and load it from settings
        settings = IAnnotations(getContext(context)).get(KEY, {})
        if not settings:
            #TODO: should look in the parent?
            pass
        header_list = settings.get('header_list',[])
        matching_fields = settings.get('matching_fields',{})
        if request.get('csv_header'):
            reader = csv.DictReader(request.get('csv_header').splitlines(),
                                    delimiter=",",
                                    dialect="excel",
                                    quotechar='"')
            header_list = reader.fieldnames

        fields = fields_list(None)
        field_names = {}
        for field in fields:
            field_names[field.title.lower()] = field.value
            field_names[field.value.lower()] = field.value

        for col in header_list:
            col = unicode(col.strip())
            if not col:
                continue
            if col in matching_fields:
                matched_field = matching_fields[col]
            elif col.lower() in field_names:
                matched_field = field_names[col.lower()]
            else:
                matched_field = ""
            rows.append(dict(header=col, field=matched_field))
        return rows


    def updateWidgets(self):
        self.fields['header_mapping'].widgetFactory = DataGridFieldFactory
        # get around a bug. not sure whose fault it is.
        # seems likely is the datagrid field
        self.fields['header_mapping'].field.bind(self.context)
        super(ImportForm, self).updateWidgets()


    @button.buttonAndHandler(_("import_button_save_import",  # nopep8
                               default=u"CSV Import"))
    def handleSaveImport(self, action):
        """Create and handle form button "Save and Import"."""

        # Extract form field values and errors from HTTP request
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return False

        import_file = data["import_file"]


        if not import_file:
            raise WidgetActionExecutionError('import_file',
                Invalid(_(u"Please provide a csv file to import")))
            return


        # File upload is not saved in settings
        file_resource = import_file.data
        file_name = import_file.filename

        if not (import_file.contentType.startswith("text/") or \
            import_file.contentType.startswith("application/csv")):
            raise WidgetActionExecutionError('import_file',
                Invalid(_(u"Please provide a file of type CSV")))
            return
        if import_file.contentType.startswith("application/vnd.ms-excel"):
            raise WidgetActionExecutionError('import_file',
                Invalid(_(u"Please convert your Excel file to CSV first")))
            return



        if data["object_type"] in ['__ignore__', '__stop__']:
            create_new = False
            object_type = None
        else:
            create_new = True
            object_type = data["object_type"]

        # list all the dexterity types
        #dx_types = get_portal_types(self.request)
        #log.debug(dx_types)

        # based from the types, display all the fields
        # fields = get_schema_info(CREATION_TYPE)
        # log.debug(fields)

        # blank header or field means we don't want it
        header_mapping = [d for d in data['header_mapping'] if d['field'] and d['header']]

        matching_headers = dict([(d['field'],d['header']) for d in header_mapping])


        if create_new and not(matching_headers.get('id') or matching_headers.get('title')):
            raise WidgetActionExecutionError('header_mapping',
                Invalid(_(u"If creating new content you need either 'Short Name"
                u" or 'Title' in your data.")))
            return

        if not matching_headers:
            raise WidgetActionExecutionError('header_mapping',
                Invalid(_(u"You must pick which fields should contain your data")))
            return

        primary_key = data["primary_key"]
        if primary_key and not matching_headers.get(primary_key):
            raise WidgetActionExecutionError('primary_key',
                Invalid(_(u"Must be a field selected in Header Mapping")))
            return

        # based from the matching fields, get all the values.
        matching_fields = dict([(d['header'],d['field']) for d in header_mapping])
        import_metadata = dexterity_import(
            self.context,
            file_resource,
            matching_fields,
            object_type,
            create_new,
            primary_key
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

        # Save our sucessful settings to save time next import
        annotations = IAnnotations(self.context)
        settings = annotations.setdefault(KEY, {})
        settings['header_list'] = [d['header'] for d in header_mapping]
        # we will keep making this bigger in case they switch between several CSVs
        settings.setdefault("matching_fields",{}).update(matching_fields)
        settings['primary_key'] = primary_key
        settings['object_type'] = object_type

        return True



    #TODO: replace with a report element on import that gives an extra button
    # to "Download CSV of changes". Requires we have hidden field of all changed
    # UIDs and then relookup all of those.
    # Report element can also display list of top 20 creations, top 20 updates etc
    # replaces info window
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
                                               header_mapping,
                                               self.request)
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
        filename, attachment = export_file(results, header_mapping, self.request)
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
