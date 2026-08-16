#!/usr/bin/env python3
"""Q3-H2-P3-A rollout seed derivation (SPEC section 6.2, frozen).

``rollout_seed(dp, m)`` derives the continuation substream seed for world
``m`` of decision point ``dp``:

    rollout_seed(dp, m) =
        uint64_be( SHA256( UTF8(
            "h2_rollout|" + str(master_seed_h2) + "|" + str(replicate_id)
            + "|" + str(dp) + "|" + str(m) + "|" + ROLLOUT_SALT
        ) )[0:8] )

ROLLOUT_SALT = "q3h2-bootstrap-v1"; ALT salt "q3h2-bootstrap-alt-v1" is
implemented as an interface/test-only variant (no stability tuning in this
package).  The seed does NOT contain action / policy / strategy / run_id /
worker / execution_no, so all candidate actions of the SAME decision point
share the SAME set of m worlds (CRN); different dp and different m separate
streams.

Pure stdlib (hashlib), no live-DES imports (C23 isolation).

Python 3.12, standard library only.
"""
from __future__ import annotations

import hashlib

ROLLOUT_SALT: str = "q3h2-bootstrap-v1"
ROLLOUT_ALT_SALT: str = "q3h2-bootstrap-alt-v1"


def rollout_seed(master_seed: int, replicate_id: int, dp: int, m: int,
                 salt: str = ROLLOUT_SALT) -> int:
    """Frozen rollout_seed(dp, m) -> uint64 big-endian from the first 8
    bytes of SHA256 over the canonical UTF-8 string."""
    text = "h2_rollout|{master}|{rep}|{dp}|{m}|{salt}".format(
        master=master_seed, rep=replicate_id, dp=dp, m=m, salt=salt)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[0:8], "big")


def rollout_seed_alt(master_seed: int, replicate_id: int, dp: int,
                     m: int) -> int:
    """ALT-salt variant (test/interface only in P3-A; no stability tuning)."""
    return rollout_seed(master_seed, replicate_id, dp, m,
                        salt=ROLLOUT_ALT_SALT)
