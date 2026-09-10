"""Magnetic symmetry: operator lists, magnetic space groups, moment subspaces.

The nuclear side of the package resolves a space-group *symbol* into operators
(``crystallography.symmetry``).  Magnetic structures cannot work that way: the
1651 magnetic space groups have no symbol grammar any of this package's
dependencies can parse, so the **operator list is the stored form** and every
other description — a UNI/BNS/OG number, an irrep plus an order-parameter
direction — is converted into it.  ``operators`` is that conversion, in both
directions.
"""

from .operators import (
    DatabaseSetting,
    MagneticGroup,
    MagneticOperator,
    MagneticSpaceGroupId,
    allowed_moment_basis,
    database_settings,
    format_transform,
    identify,
    in_span,
    magnetic_group,
    moment_from_cartesian,
    moment_magnitude,
    moment_to_cartesian,
    parse_transform,
)

__all__ = [
    "DatabaseSetting",
    "MagneticGroup",
    "MagneticOperator",
    "MagneticSpaceGroupId",
    "allowed_moment_basis",
    "database_settings",
    "format_transform",
    "identify",
    "in_span",
    "magnetic_group",
    "moment_from_cartesian",
    "moment_magnitude",
    "moment_to_cartesian",
    "parse_transform",
]
