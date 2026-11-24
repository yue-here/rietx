- A magCIF whose stated `_space_group_magn.number_BNS` or `number_OG` is not
  the group its operator and centring loops generate is now refused with a
  `MagCifError` (#193). It used to load under the operators' number with a
  `CIF_MAGNETIC_NUMBER_MISMATCH` warning. The reader cannot tell which side is
  wrong, and a forgotten anti-centring line makes the operators the wrong,
  smaller group. The message names the file, the stated number and its tag,
  the group the loops generate, and each side's operation count per cell, so
  one corrected line makes the file readable. A file in a non-standard setting
  of its stated group still loads.
