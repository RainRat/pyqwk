from pyqwk.core import _normalize_subject

def test_normalize_subject_lowercase_default():
    assert _normalize_subject("Re: Subject") == "subject"
    assert _normalize_subject("RE: Subject") == "subject"
    assert _normalize_subject("Fw: Subject") == "subject"
    assert _normalize_subject("  Re : Subject  ") == "subject"

def test_normalize_subject_no_lowercase():
    assert _normalize_subject("Re: Subject", lowercase=False) == "Subject"
    assert _normalize_subject("RE: Important Topic", lowercase=False) == "Important Topic"
    assert _normalize_subject("Fwd: [123] Next Topic", lowercase=False) == "[123] Next Topic"
    assert _normalize_subject("  Re : Mixed Case  ", lowercase=False) == "Mixed Case"

def test_normalize_subject_iterative_prefix_removal():
    assert _normalize_subject("Re: Fwd: Re: Multi Prefix") == "multi prefix"
    assert _normalize_subject("Re: Fwd: Re: Multi Prefix", lowercase=False) == "Multi Prefix"
