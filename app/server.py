"""Application entry point for the loopback SMTP server and optional relay."""
from dotenv import load_dotenv

load_dotenv()
import asyncio
import logging

from app.config import Settings
from app.relay import HostingerSMTPRelay
from app.session import SMTPSession
from app.storage import MessageStore


# Keep your existing imports below this point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ezio.smtp")


async def main() -> None:
    settings = Settings.from_env()
    if settings.host not in ("127.0.0.1", "::1", "localhost"):
        raise RuntimeError(
            "This development server must bind to loopback only. "
            "Do not expose it to a network."
        )

    store = MessageStore(settings.spool_dir)
    relay = None
    if settings.relay_enabled:
        relay = HostingerSMTPRelay(
            host=settings.relay_host,
            port=settings.relay_port,
            username=settings.relay_username,
            password=settings.relay_password,
            security=settings.relay_security,
            timeout_seconds=settings.relay_timeout_seconds,
        )
        logger.info(
            "Outbound relay enabled: host=%s port=%s security=%s username=%s",
            settings.relay_host,
            settings.relay_port,
            settings.relay_security,
            settings.relay_username,
        )
    else:
        logger.info("Outbound relay disabled; messages are stored locally only")

    async def client_connected(reader, writer):
        peer = writer.get_extra_info("peername")
        logger.info("Client connected: %s", peer)
        session = SMTPSession(
            reader=reader,
            writer=writer,
            store=store,
            max_command_line_bytes=settings.max_command_line_bytes,
            max_data_line_bytes=settings.max_data_line_bytes,
            max_message_bytes=settings.max_message_bytes,
            timeout_seconds=settings.client_timeout_seconds,
            relay=relay,
        )
        try:
            await session.handle()
        except Exception:
            logger.exception("Unexpected SMTP session failure for %s", peer)
        finally:
            logger.info("Client disconnected: %s", peer)

    server = await asyncio.start_server(
        client_connected,
        host=settings.host,
        port=settings.port,
        limit=max(settings.max_command_line_bytes, settings.max_data_line_bytes) + 2,
    )
    logger.info("SMTP development server listening on %s:%s", settings.host, settings.port)
    logger.info("Messages are stored under: %s", store.spool_dir.resolve())

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("SMTP server stopped")
