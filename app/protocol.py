"""Small, explicit helpers for the SMTP protocol."""
from dataclasses import dataclass
import re
from typing import Optional, Tuple


@dataclass(frozen=True)
class SMTPCommand:
    name: str
    argument: str


def parse_command(line: str) -> SMTPCommand:
    """Split a decoded SMTP command into its verb and argument."""
    command, separator, argument = line.partition(" ")
    return SMTPCommand(
        name=command.upper(),
        argument=argument.strip() if separator else "",
    )


_MAIL_FROM_RE = re.compile(r"^FROM:\s*<([^<>]*)>\s*$", re.IGNORECASE)
_RCPT_TO_RE = re.compile(r"^TO:\s*<([^<>]+)>\s*$", re.IGNORECASE)


def parse_mail_from(argument: str) -> Optional[str]:
    """Parse MAIL FROM:<address>. Empty path is allowed for bounce messages."""
    match = _MAIL_FROM_RE.fullmatch(argument)
    if not match:
        return None
    address = match.group(1)
    if address and not is_plausible_address(address):
        return None
    return address


def parse_rcpt_to(argument: str) -> Optional[str]:
    """Parse RCPT TO:<address> using conservative basic validation."""
    match = _RCPT_TO_RE.fullmatch(argument)
    if not match:
        return None
    address = match.group(1)
    return address if is_plausible_address(address) else None


def is_plausible_address(address: str) -> bool:
    """Reject obvious invalid input; this is not a full RFC mailbox parser."""
    if not address or len(address) > 254:
        return False
    if any(ch.isspace() for ch in address):
        return False
    if address.count("@") != 1:
        return False
    local, domain = address.rsplit("@", 1)
    if not local or not domain or local.startswith(".") or local.endswith("."):
        return False
    if ".." in local or ".." in domain:
        return False
    return "." in domain and not domain.startswith(".") and not domain.endswith(".")
