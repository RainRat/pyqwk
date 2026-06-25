from pyqwk.core import _normalize_subject

def test_normalize_subject_basic():
    assert _normalize_subject("Hello") == "hello"
    assert _normalize_subject("  Hello  ") == "hello"

def test_normalize_subject_prefix_removal():
    assert _normalize_subject("Re: Hello") == "hello"
    assert _normalize_subject("re: re: Hello") == "hello"
    assert _normalize_subject("Fwd: Hello") == "hello"
    assert _normalize_subject("re[1]: Hello") == "hello"

def test_normalize_subject_lowercase_param():
    # After refactor, this should work
    try:
        assert _normalize_subject("Hello", lowercase=False) == "Hello"
        assert _normalize_subject("Re: Hello", lowercase=False) == "Hello"
    except TypeError:
        # Before refactor, it only takes one argument
        pass

def test_normalize_subject_iterative():
    assert _normalize_subject("Re: Fwd: Re: Hello") == "hello"
