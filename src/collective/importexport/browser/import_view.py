# -*- coding: utf-8 -*-
from collective.importexport import _
from plone.namedfile.field import NamedFile
from plone.z3cform.layout import wrap_form
from Products.statusmessages.interfaces import IStatusMessage
from z3c.form import button
from z3c.form import field
from z3c.form import form
from zope.interface import Interface
# from zope import schema


def dexterity_import(container, file_resource):
    """Import to dexterity-types from file to container."""
    count = 0

    return {'count': count}


class IImportSchema(Interface):
    """Import settings."""

    import_file = NamedFile(
        title=_("import_field_file_title",  # nopep8
                default=u"Import File"),
        description=_("import_field_file_description",  # nopep8
                      default=u"In CSV format."),
        required=True)


class ImportForm(form.Form):
    """Import data to dexterity-types."""

    fields = field.Fields(IImportSchema)
    ignoreContext = True

    label = _("import_form_label",  # nopep8
              default=u"Import")
    description = _("import_form_description",  # nopep8
                    default=u"Import data to dexterity-types objects.")

    def save_data(self, data):
        # TODO(ivanteoh): save date using Annotation Adapter
        pass

    def updateWidgets(self):
        super(ImportForm, self).updateWidgets()

    @button.buttonAndHandler(_("import_button_save", default=u"Save"))  # nopep8
    def handleSave(self, action):
        data, errors = self.extractData()
        if errors:
            return False

        self.save_data(data)

        IStatusMessage(self.request).addStatusMessage(
            _("import_message_save",  # nopep8
              default=u"Import settings saved."),
            'info')
        self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(_("import_button_save_import",  # nopep8
                               default=u"Save and Import"))
    def handleSaveImport(self, action):
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

            import_metadata = dexterity_import(
                self.context,
                file_resource=file_resource
            )

            count = import_metadata['count']

            IStatusMessage(self.request).addStatusMessage(
                _("import_message_csv_info",  # nopep8
                  default=u"${num} items imported from ${filename}",
                  mapping={'num': count, 'filename': file_name}),
                'info')

        else:
            IStatusMessage(self.request).addStatusMessage(
                _("import_message_csv_error",  # nopep8
                  default=u"Please provide a csv file."), 'error')

        self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(u'Cancel')
    def handleCancel(self, action):
        IStatusMessage(self.request).addStatusMessage(
            _("import_message_cancel",  # nopep8
              default="Import canceled."),
            "info")
        self.request.response.redirect(self.context.absolute_url())

ImportView = wrap_form(ImportForm)
