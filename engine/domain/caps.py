from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Caps:
    """Cap negatif et cap positif du socle de risque, en prix absolus."""

    stop: Decimal
    target: Decimal
