"""Memory overlay ledgers — poison-safe sidecars over the ICM durable store.

ICM IS the cross-host memory store (recall/store/decay/graph). These modules
own NO lesson store; they are small local JSONL overlays that add the one
thing ICM lacks — effectiveness governance — plus two dedup ledgers:

  - ``store``       the minimal I/O backbone the ledgers share
  - ``distrust``    miss-count overlay: a recalled memory whose error keeps
                    recurring gets suppressed from recall/router
  - ``sessionlog``  per-session inject dedup: a lesson injects ONCE per
                    session so multiple surfaces don't spam the same context
  - ``outcomes``    router feedback loop: a capability set suggested many
                    times with zero uses gets demoted from suggestion

Every public call is fail-safe (broken ledger → empty/tolerant no-op, never a
crash) so a corrupted sidecar can never break a recall, a hook, or routing.
"""
