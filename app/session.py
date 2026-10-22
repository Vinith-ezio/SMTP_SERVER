"""SMTP session state machine for local development and protocol learning."""
import asyncio
from email import policy
from email.parser import BytesParser
from typing import List, Optional

from app.protocol import parse_command, parse_mail_from, parse_rcpt_to
from app.storage import MessageStore
from app.relay import HostingerSMTPRelay, RelayError


class SMTPProtocolError(Exception):
    """Raised when client input violates SMTP framing rules."""


class SMTPLineTooLongError(SMTPProtocolError):
    """Raised when a command or DATA line exceeds its configured limit."""


class SMTPSession:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: MessageStore,
        max_command_line_bytes: int = 8192,
        max_data_line_bytes: int = 998,
        max_message_bytes: int = 1_000_000,
        timeout_seconds: float = 60.0,
        relay: Optional[HostingerSMTPRelay] = None,
    ):
        if max_command_line_bytes < 1:
            raise ValueError("max_command_line_bytes must be positive")
        if max_data_line_bytes < 1:
            raise ValueError("max_data_line_bytes must be positive")
        if max_message_bytes < 1:
            raise ValueError("max_message_bytes must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.reader = reader
        self.writer = writer
        self.store = store
        self.max_command_line_bytes = max_command_line_bytes
        self.max_data_line_bytes = max_data_line_bytes
        self.max_message_bytes = max_message_bytes
        self.timeout_seconds = timeout_seconds
        self.relay = relay

        self.greeted = False
        self.helo_name = ""
        self.mail_from: Optional[str] = None
        self.recipients: List[str] = []

    async def reply(self, text: str) -> None:
        self.writer.write((text + "\r\n").encode("ascii"))
        await self.writer.drain()

    def reset_transaction(self) -> None:
        self.mail_from = None
        self.recipients = []

    async def read_line(self) -> Optional[bytes]:
        """Read one complete CRLF-terminated line with a client-input timeout.

        None means the peer disconnected cleanly or the timeout response was sent.
        Invalid or overlong framing raises SMTPProtocolError and closes the session.
        """
        try:
            raw_line = await asyncio.wait_for(
                self.reader.readline(),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self.reply("421 Timeout waiting for client input")
            return None
        except ValueError as exc:
            # StreamReader may discard an over-limit line while raising ValueError.
            # Close rather than continuing with potentially desynchronized framing.
            raise SMTPLineTooLongError("Input line exceeds StreamReader limit") from exc

        if raw_line == b"":
            return None
        if not raw_line.endswith(b"\r\n"):
            raise SMTPProtocolError("Input line is not terminated by CRLF")
        return raw_line[:-2]

    async def read_message_data(self) -> Optional[bytes]:
        """Read DATA while bounding memory and enforcing SMTP line framing.

        Oversized messages are drained through the DATA terminator without being
        buffered, allowing the client to safely issue a new transaction afterward.
        """
        data = bytearray()
        too_large = False

        while True:
            line = await self.read_line()
            if line is None:
                raise ConnectionError("Client disconnected or timed out during DATA")

            if len(line) > self.max_data_line_bytes:
                raise SMTPLineTooLongError("DATA line exceeds configured limit")

            if line == b".":
                break

            # SMTP transparency: remove exactly one dot from dot-stuffed lines.
            if line.startswith(b".."):
                line = line[1:]

            line_size = len(line) + 2  # Restore CRLF in the stored message.
            if not too_large:
                if len(data) + line_size > self.max_message_bytes:
                    too_large = True
                    data.clear()
                else:
                    data.extend(line)
                    data.extend(b"\r\n")

        if too_large:
            return None
        return bytes(data)

    async def _handle_command(self, line: str) -> bool:
        """Handle one decoded SMTP command. Return False to close the session."""
        parsed = parse_command(line)
        command = parsed.name
        argument = parsed.argument

        if not command:
            await self.reply("500 Empty command")
            return True

        if command in ("EHLO", "HELO"):
            if not argument:
                await self.reply("501 Hostname required")
                return True
            self.greeted = True
            self.helo_name = argument
            self.reset_transaction()
            await self.reply("250-ezio-smtp.local")
            await self.reply("250 HELP")
            return True

        if command == "QUIT":
            await self.reply("221 Closing connection")
            return False

        if command == "NOOP":
            await self.reply("250 OK")
            return True

        if command == "HELP":
            await self.reply(
                "214 Supported: EHLO HELO MAIL RCPT DATA RSET NOOP HELP QUIT"
            )
            return True

        if command == "RSET":
            self.reset_transaction()
            await self.reply("250 Reset")
            return True

        if not self.greeted:
            await self.reply("503 Send EHLO or HELO first")
            return True

        if command == "MAIL":
            sender = parse_mail_from(argument)
            if sender is None:
                await self.reply("501 Invalid MAIL FROM syntax or address")
                return True
            # A new MAIL command starts a new transaction and clears recipients.
            self.mail_from = sender
            self.recipients = []
            await self.reply("250 Sender accepted")
            return True

        if command == "RCPT":
            if self.mail_from is None:
                await self.reply("503 Send MAIL FROM first")
                return True
            recipient = parse_rcpt_to(argument)
            if recipient is None:
                await self.reply("501 Invalid RCPT TO syntax or address")
                return True
            self.recipients.append(recipient)
            await self.reply("250 Recipient accepted")
            return True

        if command == "DATA":
            if self.mail_from is None or not self.recipients:
                await self.reply("503 MAIL FROM and RCPT TO required")
                return True

            await self.reply("354 End data with <CRLF>.<CRLF>")
            message = await self.read_message_data()

            if message is None:
                await self.reply("552 Message size exceeds fixed limit")
                self.reset_transaction()
                return True

            parsed_message = BytesParser(policy=policy.default).parsebytes(message)
            if parsed_message.defects:
                await self.reply("554 Malformed message")
                self.reset_transaction()
                return True

            # Persist before relaying so a local storage failure cannot result in
            # an upstream message being delivered without a local audit copy.
            message_id = None
            try:
                message_id = self.store.save(
                    sender=self.mail_from,
                    recipients=list(self.recipients),
                    message=message,
                )
            except OSError:
                await self.reply("451 Unable to store message")
                self.reset_transaction()
                return True

            if self.relay is not None:
                try:
                    await self.relay.send(
                        sender=self.mail_from,
                        recipients=list(self.recipients),
                        message=message,
                    )
                except RelayError:
                    # This prototype has no durable retry queue. Remove the local
                    # copy after a reported relay failure so it is not mistaken for
                    # a successfully delivered message. A network failure after the
                    # provider accepts DATA can still be ambiguous, as with SMTP generally.
                    try:
                        self.store.delete(message_id)
                    except OSError:
                        pass
                    await self.reply("451 Upstream email submission failed")
                    self.reset_transaction()
                    return True

            await self.reply(f"250 Message accepted; id={message_id}")
            self.reset_transaction()
            return True

        await self.reply("502 Command not implemented")
        return True

    async def handle(self) -> None:
        try:
            await self.reply("220 ezio-smtp.local SMTP ready")

            while True:
                line_bytes = await self.read_line()
                if line_bytes is None:
                    break

                if len(line_bytes) > self.max_command_line_bytes:
                    raise SMTPLineTooLongError("Command line exceeds configured limit")

                try:
                    line = line_bytes.decode("ascii")
                except UnicodeDecodeError:
                    await self.reply("500 Commands must use ASCII")
                    continue

                try:
                    keep_open = await self._handle_command(line)
                except SMTPLineTooLongError:
                    # Input framing may no longer be synchronized; do not continue.
                    try:
                        await self.reply("500 Input line too long")
                    except (ConnectionError, OSError):
                        pass
                    break
                except SMTPProtocolError:
                    try:
                        await self.reply("500 Invalid line framing")
                    except (ConnectionError, OSError):
                        pass
                    break

                if not keep_open:
                    break

        except (ConnectionError, OSError):
            # A disconnected client should not crash the server process.
            pass
        except SMTPLineTooLongError:
            # read_line can raise before command/DATA dispatch, including at EOF.
            try:
                await self.reply("500 Input line too long")
            except (ConnectionError, OSError):
                pass
        except SMTPProtocolError:
            try:
                await self.reply("500 Invalid line framing")
            except (ConnectionError, OSError):
                pass
        finally:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass
