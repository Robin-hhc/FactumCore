Before writing, validate the complete final card map, reviewed bytes, proof and all expected-old digests. Persist fsynced content-addressed old bytes and a prepared journal. Atomic per-file replacements are reconciled from old/final digests after interruptions. Seal all journal states; verify against authenticated exact view before recovery so resealing cannot authorize new writes.

