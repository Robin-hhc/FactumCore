# Mechanism acceptance

Red: transaction seam absent, six behavior tests failed before implementation. Green: eight tests cover multi-file create/update/delete and idempotence, all-file CAS before first write, interrupted resume, rollback, preserving external edits, resealed fake consent, journal path tampering and OS lock exclusion. Fixtures contain synthetic Ed25519 events generated ephemerally. The unit seam injects a Context; installed CLI/domain integration is separately required. No real-user, real-code, CI or access-control acceptance is claimed.

