import unittest
from zope.interface import implements
from zope.component import getUtility, getMultiAdapter
from collective.importexport.browser.import_view import dexterity_import
from collective.importexport.testing import COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING

from plone.app.testing import TEST_USER_ID

from zope.component.interfaces import IObjectEvent


TEST1 = """Filename,Series,Description
test1.mp4,1,summary1 blah
test2.mp4,2,"summary2, blah"
test3.mp4,3,"summary3   blah"
"""

class TestImport(unittest.TestCase):
    layer = COLLECTIVE_IMPORTEXPORT_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.portal.invokeFactory('Folder', 'target')
        self.target = self.portal.target



    def testImportAndSkip(self):

        self.assertNotIn('test1.mp4', self.target.objectIds())
        dexterity_import(self.target,
                         TEST1,
                         dict(Filename='id', Description="description"),
                         object_type="__skip__",
                         create_new=False,
                         primary_key='id')
        self.assertNotIn('test1.mp4', self.target.objectIds())

    def testImportAndCreate(self):
        self.assertNotIn('test1.mp4', self.target.objectIds())
        dexterity_import(self.target,
                         TEST1,
                         dict(Filename='id', Description="description"),
                         object_type="Document",
                         create_new=True,
                         primary_key='id')
        self.assertIn('test1.mp4', self.target.objectIds())
        self.assertEqual(len(self.target.objectIds()), 3)
        self.assertEqual(self.target['test1.mp4'].description, "summary1 blah")
        self.assertEqual(self.target['test2.mp4'].description, "summary2, blah")

    def testUpdate(self):
        self.assertNotIn('test1.mp4', self.target.objectIds())
        dexterity_import(self.target,
                         TEST1,
                         dict(Filename='id', Description="description"),
                         object_type="Document",
                         create_new=True,
                         primary_key='id')
        self.assertIn('test1.mp4', self.target.objectIds())
        self.assertEqual(len(self.target.objectIds()), 3)

        dexterity_import(self.target,
                         """Filename,Series,Description
test1.mp4,1,new summary
""",
                         dict(Filename='id', Description="description"),
                         object_type="Document",
                         create_new=True,
                         primary_key='id')
        self.assertEqual(self.target['test1.mp4'].description, "new summary")

    def testUnsafeIds(self):
        self.assertNotIn('test1.mp4', self.target.objectIds())
        dexterity_import(self.target,
                         """Filename,Series,Description
test1/mp4,1,old summary
""",
                         dict(Filename='id', Description="description"),
                         object_type="Document",
                         create_new=True,
                         primary_key='id')
        self.assertIn('test1-mp4', self.target.objectIds())

        dexterity_import(self.target,
                         """Filename,Series,Description
test1/mp4,1,new summary
""",
                         dict(Filename='id', Description="description"),
                         object_type="Document",
                         create_new=True,
                         primary_key='id')
        self.assertEqual(self.target['test1-mp4'].description, "new summary")


    def testImportView(self):
#        view = getMultiAdapter((self.target, self.portal.REQUEST), name='dexterity_import_view')
#        view.form_instance.update()
        pass

        #self.assertTrue(False)
