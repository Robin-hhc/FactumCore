"""Public maintenance adapter; source resolution uses shared functions."""


def execute(context):
    ctx = context.modules["runtime"].fork_context(context)
    return ctx.modules["maintenance"].execute(ctx)
