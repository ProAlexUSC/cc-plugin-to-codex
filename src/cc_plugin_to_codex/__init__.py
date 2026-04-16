from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cc-plugin-to-codex")
except PackageNotFoundError:
    # Package not installed (e.g. running from source without `pip install -e .`).
    __version__ = "0.0.0+unknown"
