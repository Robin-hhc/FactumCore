"""Compatibility adapter for the locked shared raw inventory algorithm."""


def scan(context):
    return context.modules["source_inventory"].scan(context)
