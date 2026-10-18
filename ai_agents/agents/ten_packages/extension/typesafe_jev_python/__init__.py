"""TypeSafe Jev decision extension."""

# The TEN loader imports this package to register its addon. Pure decision
# tests may import the provider layer without the native TEN runtime present.
try:
    from . import addon
except ModuleNotFoundError as error:
    if error.name != "ten_runtime":
        raise
