
"""Test email submission through the local EZIO SMTP server."""

import argparse
import logging
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger("smtp-client-test")


def valid_email(address: str) -> bool:
    """Perform basic email address validation."""
    if not address or any(char.isspace() for char in address):
        return False

    if "\r" in address or "\n" in address:
        return False

    _, parsed = parseaddr(address)
    return parsed == address and "@" in address and "." in address.rsplit("@", 1)[-1]


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a test email through the local EZIO SMTP server."
    )
    parser.add_argument(
        "--recipient",
        help="Recipient email address. Defaults to the first configured "
             "EZIO_ALERT_RECIPIENTS address, or prompts if none is configured.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("EZIO_SMTP_HOST", "127.0.0.1"),
        help="SMTP server host (default: EZIO_SMTP_HOST or 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("EZIO_SMTP_PORT", "1025")),
        help="SMTP server port (default: EZIO_SMTP_PORT or 1025).",
    )
    parser.add_argument(
        "--sender",
        default=os.getenv("EZIO_ALERT_SENDER", "info@eziosolutions.ai"),
        help="Sender email address.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="SMTP connection timeout in seconds.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose SMTP protocol debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = get_arguments()

    if not args.host.strip():
        logger.error("SMTP host cannot be empty.")
        return 2

    if not 1 <= args.port <= 65535:
        logger.error("SMTP port must be between 1 and 65535.")
        return 2

    if args.timeout <= 0:
        logger.error("Timeout must be greater than zero.")
        return 2

    if not valid_email(args.sender):
        logger.error("Invalid sender address: %s", args.sender)
        return 2

    recipient = args.recipient
    if not recipient:
        configured = os.getenv("EZIO_ALERT_RECIPIENTS", "")
        recipients = [item.strip() for item in configured.split(",") if item.strip()]
        recipient = recipients[0] if recipients else input(
            "Enter a recipient email address: "
        ).strip()

    if not valid_email(recipient):
        logger.error("Invalid recipient email address.")
        return 2

    message = EmailMessage()
    message["From"] = args.sender
    message["To"] = recipient
    message["Subject"] = "EZIO SMTP Relay Test"
    message.set_content(
        "This is a test email submitted through the EZIO local SMTP server. "
        "It verifies SMTP submission and, if configured, outbound relay delivery."
    )

    try:
        with smtplib.SMTP(
            args.host,
            args.port,
            timeout=args.timeout,
        ) as client:
            if args.debug:
                client.set_debuglevel(1)

            client.send_message(
                message,
                from_addr=args.sender,
                to_addrs=[recipient],
            )

        logger.info("SMTP submission accepted for recipient: %s", recipient)
        logger.info("Server: %s:%s", args.host, args.port)
        logger.info(
            "Check the recipient mailbox to confirm final delivery."
        )
        return 0

    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP test failed: %s", exc)
        logger.error(
            "Check that the SMTP server is running and the relay is configured."
        )
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
