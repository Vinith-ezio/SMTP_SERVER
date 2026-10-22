
import smtplib
from email.message import EmailMessage

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
SENDER_EMAIL = "info@eziosolutions.ai"


def main():
    recipient = input("Enter a real recipient email address: ").strip()

    if not recipient or "\r" in recipient or "\n" in recipient:
        raise ValueError("A valid recipient address is required.")

    message = EmailMessage()
    message["From"] = SENDER_EMAIL
    message["To"] = recipient
    message["Subject"] = "EZIO Hostinger Relay Test"
    message.set_content(
        "This message tests the EZIO SMTP server and Hostinger relay - 2 ."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as client:
        client.set_debuglevel(1)
        client.send_message(
            message,
            from_addr=SENDER_EMAIL,
            to_addrs=[recipient],
        )

    print("Local SMTP submission completed successfully.")


if __name__ == "__main__":
    main()
