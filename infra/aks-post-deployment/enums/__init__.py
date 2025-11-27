from enum import Enum, unique


@unique
class FridgeStack(Enum):
    INFRASTRUCTURE = "infrastructure"
    ACCESS = "access"
    ISOLATED = "isolated"
