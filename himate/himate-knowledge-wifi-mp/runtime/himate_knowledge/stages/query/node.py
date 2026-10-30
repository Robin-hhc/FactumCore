"""Public query adapter; algorithms are shared with P6 regression."""


def execute(context):
    ctx = context.modules["runtime"].fork_context(context)
    return ctx.modules["query_runtime"].execute(ctx)
