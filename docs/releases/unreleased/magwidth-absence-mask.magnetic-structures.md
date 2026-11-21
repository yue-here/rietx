- **A fit with a separate magnetic width is faster where the magnetic group forbids rows.** The second family of
  windows (`magnetic_lor_size`, `magnetic_lor_strain`) is now built only on reflections whose Laue orbit has a member the
  magnetic space group lets scatter. A k ≠ 0 structure such as NiO at k = (½ ½ ½) no longer evaluates a magnetic window on
  every nuclear reflection. A dropped row's magnetic intensity is zero by symmetry, so no refined value moves beyond
  floating-point summation order.
  `rietx.crystallography.magnetic.isotropy.group_absences` now decides exactly, by a cyclotomic character sum in integer
  arithmetic (`rietx.crystallography.magnetic.operators.magnetically_allowed`), instead of a 1e-9 cut on singular values.
  Its answers are unchanged on every group tested.
