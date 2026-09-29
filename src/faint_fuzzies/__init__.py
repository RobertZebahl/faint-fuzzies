from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("faint-fuzzies")
except PackageNotFoundError:
    __version__ = "0+unknown"
