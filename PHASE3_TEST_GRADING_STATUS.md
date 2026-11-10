# Phase 3 TEST postgame grading readiness

The scheduled postgame workflow is a **read-only readiness preview**. It does not create authentic pregame predictions, persist grades, or modify Supabase.

The offline grading gate now reports `ready: false` when any pick is `UNAVAILABLE`, including mixed batches where some picks can be graded. The preview still includes the individual outcomes for troubleshooting. This avoids treating partially completed or mismatched statistics as a complete graded card.

A `ready: true` result means only that the supplied, labeled snapshot data can be graded offline with the supplied statistics. It **does not** independently authenticate the original pregame capture, upstream data publication timing, immutable storage, or live game-final status. Those are separate release requirements.

Production remains out of scope. No cloud-write authorization is introduced by this change.
