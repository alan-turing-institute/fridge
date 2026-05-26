from enum import Enum, unique


@unique
class FridgeStack(Enum):
    INFRASTRUCTURE = "infrastructure"
    ACCESS = "access"
    ISOLATED = "isolated"


@unique
class AksCoreOutboundFqdn(str, Enum):
    AZURE_MGMT = "management.azure.com"
    MCR = "mcr.microsoft.com"
    PACKAGES_AKS_AZURE_COM = "packages.aks.azure.com"
    MS_LOGIN = "mslogin.microsoft.com"
