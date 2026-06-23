import pytest
from pyqwk.core import _normalize_subject

def test_normalize_subject_lowercase_default():
    assert _normalize_subject("Re: Hello World") == "hello world"
    assert _normalize_subject("  fwd: test  ") == "test"
    assert _normalize_subject("RE: re: Multi Prefix") == "multi prefix"
    assert _normalize_subject("Re[2]: Subject") == "subject"

def test_normalize_subject_no_lowercase():
    assert _normalize_subject("Re: Hello World", lowercase=False) == "Hello World"
    assert _normalize_subject("  fwd: test  ", lowercase=False) == "test"
    assert _normalize_subject("RE: re: Multi Prefix", lowercase=False) == "Multi Prefix"
    assert _normalize_subject("Re[2]: Subject", lowercase=False) == "Subject"

def test_normalize_subject_no_prefix():
    assert _normalize_subject("Just a Subject") == "just a subject"
    assert _normalize_subject("Just a Subject", lowercase=False) == "Just a Subject"
