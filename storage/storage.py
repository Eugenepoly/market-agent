"""Storage abstraction layer for local and cloud storage."""

import os
import datetime
from typing import Optional

from config import get_config


class Storage:
    """Unified storage interface for local and cloud storage."""

    def __init__(self):
        """Initialize storage with configuration."""
        self.config = get_config()
        self._gcs_client = None

    @property
    def gcs_client(self):
        """Lazy-load GCS client only when needed."""
        if self._gcs_client is None and not self.config.is_local_mode:
            from google.cloud import storage
            self._gcs_client = storage.Client()
        return self._gcs_client

    def save_report(self, content: str, filename: Optional[str] = None) -> str:
        """Save a market report.

        Args:
            content: The report content.
            filename: Optional custom filename. Defaults to date-based name.

        Returns:
            The path or URL where the report was saved.
        """
        if filename is None:
            filename = f"Market_Update_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            return self._save_local(content, filename, self.config.local_output_dir)
        else:
            return self._save_gcs(content, filename)

    def save_analysis(self, content: str, filename: Optional[str] = None) -> str:
        """Save a deep analysis report.

        Args:
            content: The analysis content.
            filename: Optional custom filename.

        Returns:
            The path or URL where the analysis was saved.
        """
        if filename is None:
            filename = f"Deep_Analysis_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            analysis_dir = os.path.join(self.config.local_output_dir, "analysis")
            return self._save_local(content, filename, analysis_dir)
        else:
            return self._save_gcs(content, f"analysis/{filename}")

    def save_pending_draft(self, content: str, workflow_id: str) -> str:
        """Save a draft pending approval.

        Args:
            content: The draft content.
            workflow_id: The workflow ID for tracking.

        Returns:
            The path where the draft was saved.
        """
        filename = f"draft_{workflow_id}_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            return self._save_local(content, filename, self.config.pending_approval_dir)
        else:
            return self._save_gcs(content, f"pending/{filename}")

    def save_approved_draft(self, content: str, workflow_id: str) -> str:
        """Save an approved draft for user to copy.

        Args:
            content: The approved draft content.
            workflow_id: The workflow ID for tracking.

        Returns:
            The path where the draft was saved.
        """
        filename = f"approved_{workflow_id}_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            return self._save_local(content, filename, self.config.approved_drafts_dir)
        else:
            return self._save_gcs(content, f"approved/{filename}")

    def load_pending_draft(self, workflow_id: str) -> Optional[str]:
        """Load a pending draft by workflow ID.

        Args:
            workflow_id: The workflow ID.

        Returns:
            The draft content or None if not found.
        """
        filename = f"draft_{workflow_id}_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            filepath = os.path.join(self.config.pending_approval_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        else:
            try:
                bucket = self.gcs_client.bucket(self.config.gcs_bucket)
                blob = bucket.blob(f"pending/{filename}")
                return blob.download_as_text()
            except Exception:
                return None

    def delete_pending_draft(self, workflow_id: str) -> bool:
        """Delete a pending draft after approval/rejection.

        Args:
            workflow_id: The workflow ID.

        Returns:
            True if deleted successfully.
        """
        filename = f"draft_{workflow_id}_{datetime.date.today()}.txt"

        if self.config.is_local_mode:
            filepath = os.path.join(self.config.pending_approval_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        else:
            try:
                bucket = self.gcs_client.bucket(self.config.gcs_bucket)
                blob = bucket.blob(f"pending/{filename}")
                blob.delete()
                return True
            except Exception:
                return False

    def _save_local(self, content: str, filename: str, directory: str) -> str:
        """Save content to local filesystem.

        Args:
            content: The content to save.
            filename: The filename.
            directory: The target directory.

        Returns:
            The full path where the file was saved.
        """
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def _save_gcs(self, content: str, blob_name: str) -> str:
        """Save content to Google Cloud Storage.

        Args:
            content: The content to save.
            blob_name: The blob name (path within bucket).

        Returns:
            The public URL of the saved file.
        """
        bucket = self.gcs_client.bucket(self.config.gcs_bucket)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="text/plain; charset=utf-8")
        return f"https://storage.googleapis.com/{self.config.gcs_bucket}/{blob_name}"
