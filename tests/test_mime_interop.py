import email
import email.message
import email.policy
from pyqwk.core import _message_from_email, _serialize_rfc822, ParsedMessage, MessageHeader

def test_eml_import_with_mime_attachments():
    msg = email.message.EmailMessage()
    msg['Subject'] = 'Test with attachment'
    msg['From'] = 'sender@example.com'
    msg['To'] = 'receiver@example.com'
    msg.set_content('This is the body.')

    attachment_data = b'binary data'
    msg.add_attachment(attachment_data, maintype='application', subtype='octet-stream', filename='test.bin')

    parsed = _message_from_email(msg)

    # We expect the attachment to be converted to UUE and appended to the text
    assert 'begin 644 test.bin' in parsed.text
    assert 'test.bin' in (parsed.discover_attachments() or [])

def test_eml_export_with_mime_attachments():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    # Body with UUE attachment for "Cat"
    uue_body = "This is the body.\r\nbegin 644 cat.txt\n#0V%T\n`\nend\r\n"
    message = ParsedMessage(
        text=uue_body,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header
    )

    eml_str = _serialize_rfc822(message, include_mbox_header=False)

    # Use policy.default to ensure EmailMessage objects and proper multipart parsing
    eml = email.message_from_string(eml_str, policy=email.policy.default)

    # Check that it is a multipart message with a proper attachment
    assert eml.is_multipart()
    attachments = list(eml.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == 'cat.txt'
    assert attachments[0].get_content().strip() == b'Cat'

    # The UUE block should be removed from the main text part in the exported EML
    body_part = eml.get_body(preferencelist=('plain',))
    body = body_part.get_content()
    assert 'begin 644 cat.txt' not in body
    assert 'This is the body.' in body
