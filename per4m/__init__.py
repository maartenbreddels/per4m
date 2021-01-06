from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution("per4m").version
except DistributionNotFound:
     # package is not installed
    pass

def load_ipython_extension(ipython):
    from .cellmagic import load_ipython_extension
    load_ipython_extension(ipython)
