# Writing guide

Report the actual CLI status, phase, diagnostics and returned business file references. Use the output of this invocation; do not invent a passing result. OpenFlow owns run/node/attempt tracking and transition checks.

When a source declares `code_ref`, show its actual code_navigation status and current resolved path/range separately from the retained snapshot/locator and current_source_matches. Navigation success does not prove the Claim's current semantics; missing, ambiguous and unavailable results retain their actual diagnostics. Use CodeGraph only as an additional source-location aid.
