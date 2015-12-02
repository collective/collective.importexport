from AccessControl.SecurityInfo import ModuleSecurityInfo
from Products.CMFCore.permissions import setDefaultRoles

security = ModuleSecurityInfo('Products.CMFCore.permissions')

security.declarePublic("DexterityImport")
DexterityImport = "collective.importexport: Import"
#TODO: should allow readers to seee this too since they can do an export?
setDefaultRoles(DexterityImport, ("Owner", "Contributor" "Site Administrator", "Manager"))
