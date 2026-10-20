# Keep original grader mailbox identities; redirect only their local ports.
import imaplib
import os
import smtplib

_original_imap_init = imaplib.IMAP4.__init__
_original_imap_search = imaplib.IMAP4.search
_original_smtp_init = smtplib.SMTP.__init__


def _imap_init(self, host='', port=143, *args, **kwargs):
    if host in ('localhost', '127.0.0.1') and port == 1143:
        port = int(os.environ['BUSINESS_IMAP_PORT'])
    return _original_imap_init(self, host, port, *args, **kwargs)


def _smtp_init(self, host='', port=0, *args, **kwargs):
    if host in ('localhost', '127.0.0.1') and port in (1587, 2525):
        port = int(os.environ['BUSINESS_SMTP_PORT'])
    return _original_smtp_init(self, host, port, *args, **kwargs)


def _imap_search(self, charset, *criteria):
    # GreenMail rejects a quoted display name after the standard FROM key.
    # HEADER From has the same IMAP field-match semantics and accepts it.
    rewritten = []
    for criterion in criteria:
        if isinstance(criterion, str):
            parenthesized = criterion.startswith('(')
            offset = int(parenthesized)
            if criterion[offset:offset + 5].upper() == 'FROM ':
                criterion = criterion[:offset] + 'HEADER From ' + criterion[
                    offset + 5:]
        rewritten.append(criterion)
    return _original_imap_search(self, charset, *rewritten)


imaplib.IMAP4.__init__ = _imap_init
imaplib.IMAP4.search = _imap_search
smtplib.SMTP.__init__ = _smtp_init
