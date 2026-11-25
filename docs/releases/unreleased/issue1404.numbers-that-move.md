- A magnetic fit that frees a moment's angles builds their Jacobian columns exactly (#1404), as it already did for the moduli.
  Where the site symmetry fixes the direction and an angle's exact column is zero, that column alone takes the forward difference for that step, so a start on such a direction still moves off it.
  A converged fit's χ², values and esds move inside the solver's tolerance: on a two-site test fit, χ² by under 1e-9 relative, values by under 1e-8 of their esds, esds by about 2e-6 relative.
  A fit that stopped short of its minimum can now reach it with the closing stage declared: on a monoclinic fit freeing the cell and the moment together in one stage, reduced χ² 2.53 and 4.45 became 0.978 and 1.013 (#1730's table).
  Under the default since #1708, which has no closing stage, the same fits stop at 14.7 and 14.1 instead of 476 and 487, still short of the minimum (#1730).
