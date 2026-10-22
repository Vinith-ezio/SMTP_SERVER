"""Authenticated outbound SMTP relay client for Hostinger Email."""
from __future__ import annotations

import asyncio
import smtplib
import ssl
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from typing import Sequence


class RelayError(Exception):
    """A safe-to-report outbound relay failure (contains no credentials)."""


class HostingerSMTPRelay:
    """Send messages through Hostinger using authenticated TLS submission.

    Network I/O runs in a worker thread so the asyncio SMTP server stays responsive.
    The configured mailbox is the only permitted envelope sender and From header.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        security: str = "ssl",
        timeout_seconds: float = 20.0,
    ) -> None:
        if not host.strip():
            raise ValueError("Relay host must not be empty")
        if not 1 <= port <= 65535:
            raise ValueError("Relay port must be between 1 and 65535")
        if not username.strip() or not password:
            raise ValueError("Relay username and password are required")
        if security not in {"ssl", "starttls"}:
            raise ValueError("Relay security must be 'ssl' or 'starttls'")
        if timeout_seconds <= 0:
            raise ValueError("Relay timeout must be positive")

        self.host = host
        self.port = port
        self.username = username.strip()
        self.password = password
        self.security = security
        self.timeout_seconds = timeout_seconds

    async def send(self, sender: str, recipients: Sequence[str], message: bytes) -> None:
        """Relay one message or raise RelayError on an unsuccessful submission."""
        if sender.casefold() != self.username.casefold():
            raise RelayError("Envelope sender must match the authenticated mailbox")
        if not recipients:
            raise RelayError("At least one recipient is required")

        parsed = BytesParser(policy=policy.default).parsebytes(message)
        from_header = parsed.get("From")
        header_address = parseaddr(str(from_header))[1] if from_header else ""
        if header_address.casefold() != self.username.casefold():
            raise RelayError("From header must match the authenticated mailbox")

        await asyncio.to_thread(self._send_blocking, sender, list(recipients), message)

    def _send_blocking(self, sender: str, recipients: list[str], message: bytes) -> None:
        context = ssl.create_default_context()
        client = None
        try:
            if self.security == "ssl":
                client = smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout_seconds,
                    context=context,
                )
            else:
                client = smtplib.SMTP(
                    self.host,
                    self.port,
                    timeout=self.timeout_seconds,
                )
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()

            with client:
                client.login(self.username, self.password)
                refused = client.sendmail(sender, recipients, message)
                if refused:
                    # A partial refusal can mean some recipients were already accepted.
                    raise RelayError(
                        "Relay provider refused one or more recipients; inspect provider logs"
                    )
        except RelayError:
            raise
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            # Do not expose host responses, message contents, or credentials to SMTP clients.
            raise RelayError("Hostinger SMTP submission failed") from exc
