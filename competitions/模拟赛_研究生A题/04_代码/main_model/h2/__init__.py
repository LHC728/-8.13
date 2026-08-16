"""Q3-H2 P1 H2-facing safe-state package.

Contains ONLY the information-firewall boundary types:
  * observable_state_v1  -- ObservableState immutable safe projection
  * posterior_state_v1   -- PosteriorState P1 interface seam (P2 deferred)

Nothing in this package imports the live DES engine (``g3`` / ``des``);
H2 consumers receive only safe projections (C23 section 7).
"""
