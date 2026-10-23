"""(3+1)D superspace groups: the operator half of modulated structures (N-W1,
N-W2's group half).

Operators and their algebra (:mod:`.operators`), the groups derived from a
basic space group and a modulation vector, with equivalence and
standardisation (:mod:`.generation`), one-line symbols (:mod:`.symbols`), the
3D space group of a commensurate section (:meth:`SuperspaceGroup.section`),
and the magnetic superspace groups — θ on the operators, {1′|000½}, and the
groups generated over a superspace group (:mod:`.magnetic`, WP-1992).  No
atoms, waves, structure factors or satellites: those are later work packages
of issue #258, and they consume the operator lists built here.  d = 1 only.
"""

from .generation import (
    N_BRAVAIS_CLASSES_D1,
    N_SUPERSPACE_GROUPS_D1,
    bravais_classes,
    canonical_key,
    catalogue,
    count_superspace_groups,
    equivalent,
    family_orbits,
    generate,
    standard_setting,
    standardised,
    superspace_groups,
)
from .magnetic import (
    N_MAGNETIC_SUPERSPACE_GROUPS_D1,
    N_MAGNETIC_SUPERSPACE_TYPES_D1,
    construct_type,
    count_magnetic_superspace_groups,
    family,
    magnetic_canonical_key,
    magnetic_superspace_groups,
    magnetic_symbol,
    maximal_subgroup,
    parse_magnetic_symbol,
)
from .operators import (
    IDENTITY,
    IDENTITY_PRIME,
    ModulationVector,
    Section,
    SuperspaceGroup,
    SuperspaceOperator,
    SuperspaceTransform,
    line_rule,
)
from .symbols import ITC_C_EXCEPTIONS, parse_symbol, symbol, symbol_candidates

__all__ = [
    "IDENTITY",
    "IDENTITY_PRIME",
    "ITC_C_EXCEPTIONS",
    "N_MAGNETIC_SUPERSPACE_GROUPS_D1",
    "N_MAGNETIC_SUPERSPACE_TYPES_D1",
    "N_BRAVAIS_CLASSES_D1",
    "N_SUPERSPACE_GROUPS_D1",
    "ModulationVector",
    "Section",
    "SuperspaceGroup",
    "SuperspaceOperator",
    "SuperspaceTransform",
    "bravais_classes",
    "canonical_key",
    "catalogue",
    "construct_type",
    "count_magnetic_superspace_groups",
    "count_superspace_groups",
    "equivalent",
    "family",
    "family_orbits",
    "generate",
    "line_rule",
    "magnetic_canonical_key",
    "magnetic_superspace_groups",
    "magnetic_symbol",
    "maximal_subgroup",
    "parse_magnetic_symbol",
    "parse_symbol",
    "standard_setting",
    "standardised",
    "superspace_groups",
    "symbol",
    "symbol_candidates",
]
