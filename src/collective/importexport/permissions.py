from AccessControl.SecurityInfo import ModuleSecurityInfo
from Products.CMFCore.permissions import setDefaultRoles

security = ModuleSecurityInfo('Products.CMFCore.permissions')

security.declarePublic('ImportSection')
ImportSection = 'collective.importexport: Import'
setDefaultRoles(ImportSection, ('Member', 'Manager'))

security.declarePublic('ExportSection')
ExportSection = 'collective.importexport: Export'
setDefaultRoles(ExportSection, ('Member', 'Manager'))
