.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide_addons.html
   This text does not appear on pypi or github. It is a comment.

==============================================================================
Collective Import & Export
==============================================================================

Provides a user action to do bulk metadata import and export on Plone content via
CSV files. It doesn't support all field types (such as files) so its not suitable
for import and export of complete content trees, but rather bulk metadata updates
and reporting.

Features
--------

- Lets the user map their CSV columns to fields on content types
- Can use fields other than Path or id to locate exiting content to update
- Can select the content type to create new content (only one type of content can be created with one CSV)
- Allows you create CSV reports on all content in subfolder with user selected fields
- Currently supports Text, Number Bool and Date fields (Uses transmogrify.dexterity internally)
  It doesn't support Files but you just can just bulk upload fields first.

Comparison to Other Plugins
---------------------------

- https://github.com/collective/collective.excelimportexport

  - con: requires columns to match internal fields
  - con: requires both path and portal_type in the data
  - con: excel only
  - pro: works for AT and DX
  - pro: works on collections and search, not just folders

- https://pypi.python.org/pypi/collective.plone.gsxml

  - con: AT only
  - con: XML only format export and import

- https://github.com/collective/collective.contentexport

  - con: DX only
  - con: export only
  - pro: Can select types to export
  - pro: Support many export formats such as YAML, json, xlsx
  - pro: Plone 5 compatible
  - pro: export files

- https://plone.org/products/csvreplicata

  - pro: plone 3 only
  - pro: handles referencefields

- https://plone.org/products/smart-csv-exporter

  - con: doesn't support plone 5
  - con: export only
  - pro: works with collections so you can select content to export

- https://plone.org/products/archecsv

  - con: plone 2.5 only. AT only
  - pro: lets the user select fields
  - pro: can paste and edit csv file

- https://pypi.python.org/pypi/transmogrify.dexterity

  - con: No UI. Have to configure via files and run on commandline

Usage
-----

Import
======

1. Create your CSV file with your data.
2. Select Action > CSV Import/Export
3. Select your CSV on your local drive
4. A datagrid will be loaded with the headers found in your CSV
5. Select the Internal fields you want to contain the CSV data
6. Pick a column to use to find any existing content
7. Either skip non-existing content or select a content type to create
8. Import. It will provide totals on updated vs created content

Export
======

1. Select the headers and internal fields to export (will remember from an import)
2. Export


Installation
------------

Install collective.importexport by adding it to your buildout::

    [buildout]

    ...

    eggs =
        collective.importexport


and then running ``bin/buildout``


Contribute
----------

- Issue Tracker: https://github.com/collective/collective.importexport/issues
- Source Code: https://github.com/collective/collective.importexport


License
-------

The project is licensed under the GPLv2.
