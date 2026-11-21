- **`RigidBodyBlock(site_reach=None)` is the default, and means the body's atoms were not typed on a site** (WP-1807, #1551's review).
  The old default, `0.0`, refused a linear body typed exactly along or across its site's one turn axis, because the axis read back from its quaternion is off by rounding (a few times 1e-17 rad).
  With no reach, the axis test does not apply and the body takes the nearer case: one turn about the axis, or none.
  An explicit number keeps the test, and a structure's rigid bodies, which pass one whenever the site fixes a direction, build as before.
