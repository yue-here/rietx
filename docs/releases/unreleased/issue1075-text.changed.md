- Two help texts on the magnetic path now say what the code does (#1075). The
  `phases.*.magnetic_lor_size` entry no longer says to hold the moment while the
  width settles: the `magnetic_width` preset keeps the moment refining beside it
  (#609). `MagneticOnset` no longer calls its bracket a located T_N: the bracket
  is where the moment stops being supported, which for a continuous transition is
  a lower bound on the ordering temperature.
