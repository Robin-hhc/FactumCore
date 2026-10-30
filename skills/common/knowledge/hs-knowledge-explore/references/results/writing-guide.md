# Writing guide

Report the actual CLI status, phase, diagnostics and returned business file references. Use the output of this invocation; do not invent a passing result. OpenFlow owns run/node/attempt tracking and transition checks.

Distinguish runtime-dependency readiness, actual symbol-navigation results and optional CodeGraph preparation. Routing to a code_ref does not prove it resolves or justify building a graph; report only the preparation or business action actually performed.

Report current context discovery only; do not turn an old private operation into a resumed Workflow.
