"""R2 client for accessing Cloudflare logpush data via S3-compatible API."""

import os
from typing import Optional

import boto3
from botocore.config import Config

from .types import DateFolder, LogFile


class R2Client:
    """Client for accessing R2 buckets via S3-compatible API."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.account_id = account_id or os.getenv("R2_ACCOUNT_ID", "")
        self.access_key_id = access_key_id or os.getenv("R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.bucket_name = bucket_name or os.getenv("R2_BUCKET_NAME", "")

        # Auto-generate endpoint URL if not provided
        self.endpoint_url = endpoint_url or os.getenv(
            "R2_ENDPOINT_URL",
            f"https://{self.account_id}.r2.cloudflarestorage.com",
        )

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(
                signature_version="s3v4",
                region_name="auto",
            ),
        )

    def list_environments(self) -> list[str]:
        """List top-level environment folders (production, staging, etc.)."""
        response = self._client.list_objects_v2(
            Bucket=self.bucket_name,
            Delimiter="/",
        )

        environments = []
        for prefix in response.get("CommonPrefixes", []):
            env = prefix["Prefix"].rstrip("/")
            environments.append(env)

        return environments

    def list_dates(
        self,
        environment: Optional[str] = None,
        limit: int = 30,
    ) -> list[DateFolder]:
        """List available date folders.

        Args:
            environment: Filter by environment (production, staging). If None, list all.
            limit: Maximum number of dates to return.

        Returns:
            List of DateFolder objects sorted by date descending.
        """
        dates: list[DateFolder] = []

        if environment:
            environments = [environment]
        else:
            environments = self.list_environments()

        for env in environments:
            prefix = f"{env}/" if env else ""
            response = self._client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter="/",
            )

            for p in response.get("CommonPrefixes", []):
                folder = p["Prefix"].rstrip("/")
                parts = folder.split("/")
                date_str = parts[-1]

                # Validate date format (YYYYMMDD)
                if len(date_str) == 8 and date_str.isdigit():
                    dates.append(
                        DateFolder(
                            date=date_str,
                            environment=env or "root",
                            prefix=folder + "/",
                        )
                    )

        # Sort by date descending
        dates.sort(key=lambda d: d.date, reverse=True)
        return dates[:limit]

    def list_files(
        self,
        date: str,
        environment: str = "production",
        limit: int = 100,
        continuation_token: Optional[str] = None,
    ) -> tuple[list[LogFile], Optional[str]]:
        """List log files for a specific date.

        Args:
            date: Date in YYYYMMDD format.
            environment: Environment (production, staging).
            limit: Maximum number of files to return.
            continuation_token: Token for pagination.

        Returns:
            Tuple of (list of LogFile, next continuation token or None).
        """
        prefix = f"{environment}/{date}/"

        params = {
            "Bucket": self.bucket_name,
            "Prefix": prefix,
            "MaxKeys": limit,
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = self._client.list_objects_v2(**params)

        files = []
        for obj in response.get("Contents", []):
            files.append(
                LogFile.from_key(
                    key=obj["Key"],
                    size=obj["Size"],
                    last_modified=obj["LastModified"],
                )
            )

        # Sort by last_modified descending (most recent first)
        files.sort(key=lambda f: f.last_modified, reverse=True)

        next_token = response.get("NextContinuationToken")
        return files, next_token

    def get_file_content(self, key: str) -> str:
        """Get the content of a log file.

        Args:
            key: Full object key/path.

        Returns:
            File content as string.
        """
        response = self._client.get_object(
            Bucket=self.bucket_name,
            Key=key,
        )
        return response["Body"].read().decode("utf-8")

    def get_latest_files(
        self,
        environment: str = "production",
        count: int = 5,
    ) -> list[LogFile]:
        """Get the most recent log files.

        Args:
            environment: Environment to search.
            count: Number of files to return.

        Returns:
            List of most recent LogFile objects.
        """
        # Get the most recent date
        dates = self.list_dates(environment=environment, limit=1)
        if not dates:
            return []

        latest_date = dates[0]
        files, _ = self.list_files(
            date=latest_date.date,
            environment=environment,
            limit=count,
        )
        return files


# Global client instance (lazy initialization)
_client: Optional[R2Client] = None


def get_client() -> R2Client:
    """Get or create the global R2 client instance."""
    global _client
    if _client is None:
        _client = R2Client()
    return _client
