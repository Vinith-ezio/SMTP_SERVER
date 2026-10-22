"""Atomic local spool storage for accepted SMTP messages."""
import json
import os
import shutil
from pathlib import Path
import tempfile
from typing import List
from uuid import uuid4


class MessageStore:
    """Stores each accepted message in its own atomically published directory."""

    def __init__(self, spool_dir: str):
        self.spool_dir = Path(spool_dir)

    def save(self, sender: str, recipients: List[str], message: bytes) -> str:
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        message_id = uuid4().hex
        final_dir = self.spool_dir / message_id

        # Build a complete message directory first, then publish it with rename.
        temporary_dir = Path(
            tempfile.mkdtemp(prefix=".tmp-", dir=str(self.spool_dir))
        )
        try:
            (temporary_dir / "message.eml").write_bytes(message)
            metadata = {
                "message_id": message_id,
                "envelope_from": sender,
                "envelope_to": recipients,
            }
            (temporary_dir / "envelope.json").write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )
            os.replace(str(temporary_dir), str(final_dir))
        except Exception:
            # Remove partially written temporary files/directories on failure.
            for child in temporary_dir.iterdir():
                try:
                    child.unlink()
                except OSError:
                    pass
            try:
                temporary_dir.rmdir()
            except OSError:
                pass
            raise

        return message_id

    def delete(self, message_id: str) -> None:
        """Delete a stored message directory by its generated ID."""
        if not message_id or any(ch not in "0123456789abcdef" for ch in message_id):
            raise ValueError("Invalid message ID")
        target = self.spool_dir / message_id
        # Resolve containment so this method cannot delete outside the spool.
        if target.parent.resolve() != self.spool_dir.resolve():
            raise ValueError("Message path is outside the spool")
        shutil.rmtree(target)
