import subprocess

from django.core.mail.backends.base import BaseEmailBackend


class MsmtpEmailBackend(BaseEmailBackend):
    '''Email backend that pipes each message to the local msmtp binary.'''

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            recipients = message.recipients()
            if not recipients:
                continue
            try:
                subprocess.run(
                    ['msmtp', '-f', message.from_email, '--', *recipients],
                    input=message.message().as_bytes(),
                    check=True,
                )
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent
