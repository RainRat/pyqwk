import pytest
from pyqwk.core import (
    _reconstruct_metadata, ParsedMessage, MessageHeader, _serialize_rfc822,
    _order_messages_by_thread
)

def test_reconstruct_metadata_with_bbs_id():
    # Covers line 912: if msg.bbs_id: bbs_info.bbs_id = msg.bbs_id
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='ToUser', msgfrom='FromUser', msgsubject='Subj', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(
        text="body", msgnum=1, refnum=None, confnum=1, header=header,
        bbs_name="TestBBS", bbs_id="BBS123"
    )
    board_dict = _reconstruct_metadata([msg])
    assert board_dict.bbs_info.bbs_id == "BBS123"
    assert board_dict.bbs_info.name == "TestBBS"

def test_serialize_rfc822_with_bbs_id():
    # Covers line 2577: if message.bbs_id: parts.append(f"X-QWK-BBS-ID: {message.bbs_id}")
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='ToUser', msgfrom='FromUser', msgsubject='Subj', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(
        text="body", msgnum=1, refnum=None, confnum=1, header=header,
        bbs_id="BBS123"
    )
    rfc822 = _serialize_rfc822(msg, include_mbox_header=False)
    assert "X-QWK-BBS-ID: BBS123" in rfc822

def test_order_messages_by_thread_convergent():
    # Covers lines 3458 and 3514 (visited checks in _order_messages_by_thread)
    # This happens when multiple roots or paths lead to the same already-visited message.
    # Structure:
    # 1. Msg 1 (Root)
    # 2. Msg 2 (Root, also references Msg 1 via subject)
    # 3. Msg 3 (Child of Msg 1)

    h1 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User1', msgsubject='Topic A', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    m1 = ParsedMessage(text="body 1", msgnum=1, refnum=None, confnum=1, header=h1)

    h2 = MessageHeader(
        status=' ', msgnum=2, msgdate='01-01-23', msgtime='12:01',
        msgto='All', msgfrom='User2', msgsubject='Topic A', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    # m2 will be identified as a child of m1 because of the same subject.
    # But it might also be in 'roots' initially.
    m2 = ParsedMessage(text="body 2", msgnum=2, refnum=None, confnum=1, header=h2)

    h3 = MessageHeader(
        status=' ', msgnum=3, msgdate='01-01-23', msgtime='12:02',
        msgto='User1', msgfrom='User3', msgsubject='Re: Topic A', msgpassword='',
        refnum=1, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    m3 = ParsedMessage(text="body 3", msgnum=3, refnum=1, confnum=1, header=h3)

    messages = [m1, m2, m3]
    ordered = _order_messages_by_thread(messages)

    # Check that we have 3 messages and no duplicates
    assert len(ordered) == 3
    msgnums = [m.msgnum for m in ordered]
    assert sorted(msgnums) == [1, 2, 3]

    # Verify threading
    # m1 should be root (depth 0)
    m1_ordered = next(m for m in ordered if m.msgnum == 1)
    assert m1_ordered.depth == 0

    # m2 and m3 should be children of m1
    m2_ordered = next(m for m in ordered if m.msgnum == 2)
    m3_ordered = next(m for m in ordered if m.msgnum == 3)
    assert m2_ordered.parent_msgnum == 1
    assert m3_ordered.parent_msgnum == 1
