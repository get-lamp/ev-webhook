import logging

from google.auth import default
from googleapiclient.discovery import build


logger = logging.getLogger(__name__)


DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
]


def connect():
    credentials, project = default(scopes=DRIVE_SCOPES)
    email = getattr(credentials, "service_account_email", "unknown")
    logger.info("RealDriveClient: ADC project=%s service_account=%s", project, email)
    return build("drive", "v3", credentials=credentials)


async def list_changes(drive, page_token: str | None = None) -> dict:
    """Call ``changes.list`` and return the raw response dict."""
    if page_token is None:
        start = drive.changes().getStartPageToken().execute()
        page_token = start["startPageToken"]
        logger.info("Fetched start page token: %s", page_token)

    logger.info("changes.list(pageToken=%s)", page_token)
    result = (
        drive.changes()
        .list(
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    logger.info("changes.list raw response: %s", result)
    return result


async def list_folder_files(drive, folder_id: str) -> list[dict]:
    """List all non-trashed files directly inside *folder_id*.

    Returns a list of dicts with ``id`` and ``name`` keys.
    """
    logger.info("files.list(folder=%s)", folder_id)
    result = (
        drive.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name)",
            pageSize=1000,
        )
        .execute()
    )
    logger.info("files.list raw response: %s", result)
    files = result.get("files", [])
    logger.info("files.list returned %d files", len(files))
    return files


async def find_folder(drive, name: str) -> str:
    """Return the file ID of the first folder matching *name*."""
    logger.info("Searching for folder: %s", name)
    result = (
        drive.files()
        .list(
            q=f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false",
            fields="files(id,name)",
            pageSize=10,
        )
        .execute()
    )
    folders = result.get("files", [])
    if not folders:
        raise SystemExit(f"Folder not found: {name}")
    folder_id = folders[0]["id"]
    logger.info("Found folder '%s' → %s", folders[0]["name"], folder_id)
    return folder_id


async def get_file_metadata(drive, file_id: str) -> dict:
    """Return metadata for a single file (id, name, owners, shared, timestamps)."""
    logger.info("files.get(fileId=%s)", file_id)
    result = (
        drive.files()
        .get(fileId=file_id, fields="id,name,owners,shared,createdTime,modifiedTime")
        .execute()
    )
    logger.info("files.get returned: %s", result)
    return result
