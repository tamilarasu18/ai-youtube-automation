"""
YouTube upload via Google API with OAuth2 authentication.

Supports:
- Resumable uploads with progress tracking
- Scheduled publishing via ISO-8601 timestamps
- Both full-length video and Shorts upload
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from video_engine.core.config import Settings
from video_engine.core.exceptions import UploadError
from video_engine.core.logger import logger


def _authenticate(settings: Settings) -> googleapiclient.discovery.Resource:
    """
    Authenticate with YouTube API using OAuth2.

    Handles token refresh and first-time authorisation flow.

    Returns:
        An authenticated YouTube API service resource.

    Raises:
        UploadError: If authentication fails.
    """
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    token_file = Path(settings.YOUTUBE_TOKEN_FILE)
    secrets_file = Path(settings.YOUTUBE_CLIENT_SECRETS)

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    credentials = None

    # Try loading existing token
    if token_file.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_file), scopes)
        except Exception as exc:
            logger.warning("Failed to load cached credentials: {}", exc)
            credentials = None

    # Refresh or re-auth
    if not credentials or not credentials.valid:
        try:
            if credentials and credentials.expired and credentials.refresh_token:
                logger.info("Refreshing expired credentials...")
                credentials.refresh(Request())
            else:
                if not secrets_file.exists():
                    raise UploadError(
                        f"Client secrets file not found: {secrets_file}. "
                        "Download it from Google Cloud Console."
                    )

                logger.info("Starting OAuth2 authorisation flow...")
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    str(secrets_file), scopes=scopes,
                )
                flow.redirect_uri = f"http://localhost:{settings.YOUTUBE_REDIRECT_PORT}/"
                credentials = flow.run_local_server(port=settings.YOUTUBE_REDIRECT_PORT)

            # Persist token
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(credentials.to_json())
            logger.info("Credentials saved → {}", token_file)

        except UploadError:
            raise
        except Exception as exc:
            raise UploadError(f"YouTube authentication failed: {exc}") from exc

    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)


def _upload_single(
    youtube: googleapiclient.discovery.Resource,
    video_path: Path,
    seo_data: dict,
    title_suffix: str | None,
    scheduled_time: str | None,
    settings: Settings,
) -> str | None:
    """
    Upload a single video file to YouTube.

    Returns:
        The YouTube video ID on success, None on failure.
    """
    title = seo_data["title"]
    if title_suffix:
        title = f"{title} - {title_suffix}"

    description = seo_data["description"]
    hashtags = seo_data.get("hashtags", [])
    if hashtags:
        description += "\n\n" + " ".join(hashtags)

    request_body = {
        "snippet": {
            "categoryId": settings.YOUTUBE_CATEGORY_ID,
            "title": title,
            "description": description,
            "tags": hashtags,
        },
        "status": {
            "privacyStatus": settings.YOUTUBE_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    if scheduled_time:
        request_body["status"]["publishAt"] = scheduled_time

    media_body = MediaFileUpload(str(video_path), chunksize=256 * 1024, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status,contentDetails",
        body=request_body,
        media_body=media_body,
    )

    logger.info("Uploading: {} ({})", video_path.name, title[:50])

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.debug("Upload progress: {}%", progress)

    video_id = response.get("id")
    if video_id:
        logger.success("Uploaded: {} → https://youtu.be/{}", video_path.name, video_id)
        if scheduled_time:
            logger.info("Scheduled for: {}", scheduled_time)
    else:
        logger.error("Upload failed for: {}", video_path.name)

    return video_id


def upload_all(settings: Settings, scheduled_time: str | None = None) -> dict[str, list[str]]:
    """
    Upload all generated videos (full-length + Shorts) to YouTube.

    Args:
        settings: Application settings.
        scheduled_time: Optional ISO-8601 publish time.

    Returns:
        Dict with ``videos`` and ``shorts`` keys containing lists of video IDs.

    Raises:
        UploadError: If authentication fails or SEO content is missing.
    """
    seo_file = settings.video_output_dir / "seo_content.json"
    if not seo_file.exists():
        raise UploadError(f"SEO content file not found: {seo_file}")

    try:
        seo_data = json.loads(seo_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise UploadError(f"Failed to read SEO content: {exc}") from exc

    youtube = _authenticate(settings)
    result: dict[str, list[str]] = {"videos": [], "shorts": []}

    # Upload full-length video
    full_video = settings.yt_video_dir / "final_video.mp4"
    if full_video.exists():
        vid = _upload_single(youtube, full_video, seo_data, None, scheduled_time, settings)
        if vid:
            result["videos"].append(vid)
    else:
        logger.warning("Full video not found, skipping: {}", full_video)

    # Upload Shorts
    shorts_dir = settings.shorts_output_dir
    if shorts_dir.exists():
        shorts_files = sorted(
            f for f in shorts_dir.iterdir()
            if f.name.startswith("youtube_shorts_part") and f.suffix == ".mp4"
        )
        for idx, shorts_file in enumerate(shorts_files, 1):
            suffix = f"Part {idx}" if len(shorts_files) > 1 else None
            vid = _upload_single(
                youtube, shorts_file, seo_data, suffix, scheduled_time, settings,
            )
            if vid:
                result["shorts"].append(vid)
    else:
        logger.warning("Shorts directory not found, skipping: {}", shorts_dir)

    logger.info(
        "Upload complete: {} videos, {} shorts",
        len(result["videos"]), len(result["shorts"]),
    )
    return result
