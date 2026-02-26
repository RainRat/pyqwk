from pyqwk import __version__, __all__

def test_version_exported():
    assert "__version__" in __all__
    assert isinstance(__version__, str)
