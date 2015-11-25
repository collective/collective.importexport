from AccessControl.SecurityInfo import ModuleSecurityInfo
from Products.CMFCore.permissions import setDefaultRoles

security = ModuleSecurityInfo('Products.CMFCore.permissions')

security.declarePublic("DexterityImport")
DexterityImport = "collective.importexport: Import"
setDefaultRoles(DexterityImport, ("Member", "Manager"))

security.declarePublic("DexterityExport")
DexterityExport = "collective.importexport: Export"
setDefaultRoles(DexterityExport, ("Member", "Manager"))
