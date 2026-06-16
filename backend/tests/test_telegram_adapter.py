"""
Telegram adapter tests — Telethon mocked with unittest.mock, no real network calls.

StringSession is patched alongside TelegramClient because StringSession validates
the session string on construction (before TelegramClient is called).

Publish flow under test:
  1. TelegramClient.__aenter__ → mock client
  2. client(CanSendStoryRequest) → mock with count_remains=N
  3. httpx.get(media_url) → bytes  [mocked with respx]
  4. client.upload_file() → fake InputFile
  5. client(SendStoryRequest) → mock Updates with UpdateStoryID(id=42)

Insights flow:
  client(GetStoriesViewsRequest) → mock StoryViews result
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from app.adapters.telegram import TelegramPublisher
from telethon.tl.types import UpdateStoryID

FAKE_API_ID = 12345
FAKE_API_HASH = "abc123fakehash"
FAKE_SESSION = "fake_session_string"

MEDIA_URL = "https://test.supabase.co/storage/v1/object/public/media/story.jpg"
VIDEO_URL = "https://test.supabase.co/storage/v1/object/public/media/story.mp4"


class FakeAccount:
    credentials_enc = None


class FakePhotoMedia:
    url = MEDIA_URL
    media_type = "photo"


class FakeVideoMedia:
    url = VIDEO_URL
    media_type = "video"


@pytest.fixture
def publisher():
    return TelegramPublisher(
        api_id=FAKE_API_ID,
        api_hash=FAKE_API_HASH,
        session_str=FAKE_SESSION,
    )


def _make_publish_client(can_send_remains: int = 3, story_id: int = 42) -> AsyncMock:
    """Mock TelegramClient for publish_story: CanSend + Send calls."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.upload_file = AsyncMock(return_value=MagicMock(name="InputFile"))

    can_send = MagicMock()
    can_send.count_remains = can_send_remains

    updates = MagicMock()
    updates.updates = [UpdateStoryID(id=story_id)]

    client.side_effect = [can_send, updates]
    return client


def _make_insights_client(views_count: int, reactions_count: int = 0,
                          forwards_count: int = 0) -> AsyncMock:
    """Mock TelegramClient for fetch_insights."""
    from telethon.tl.types import StoryViews
    sv = StoryViews(
        views_count=views_count,
        reactions_count=reactions_count,
        forwards_count=forwards_count,
    )
    result = MagicMock()
    result.views = [sv]

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.return_value = result
    return client


# ──────────────────────────────────────────────
# publish_story — happy paths
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_publish_photo_ok(mock_ss, mock_tg_class, publisher):
    mock_tg_class.return_value = _make_publish_client(can_send_remains=3, story_id=42)

    respx.get(MEDIA_URL).mock(
        return_value=httpx.Response(
            200,
            content=b"\xff\xd8\xff\xe0fake_jpeg",
            headers={"content-type": "image/jpeg"},
        )
    )

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption="Тест")

    assert result.ok is True
    assert result.external_id == "42"
    assert result.retry_later is False
    assert result.error is None


@pytest.mark.asyncio
@respx.mock
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_publish_video_ok(mock_ss, mock_tg_class, publisher):
    mock_tg_class.return_value = _make_publish_client(can_send_remains=2, story_id=99)

    respx.get(VIDEO_URL).mock(
        return_value=httpx.Response(
            200,
            content=b"\x00\x00\x00\x1cftypisom_fake_mp4",
            headers={"content-type": "video/mp4"},
        )
    )

    result = await publisher.publish_story(FakeAccount(), [FakeVideoMedia()], caption=None)

    assert result.ok is True
    assert result.external_id == "99"


@pytest.mark.asyncio
@respx.mock
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_caption_truncated_to_200(mock_ss, mock_tg_class, publisher):
    client = _make_publish_client(story_id=7)
    mock_tg_class.return_value = client

    respx.get(MEDIA_URL).mock(
        return_value=httpx.Response(
            200, content=b"img", headers={"content-type": "image/jpeg"}
        )
    )

    long_caption = "А" * 250
    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=long_caption)

    assert result.ok is True
    # Second call to client(...) carries SendStoryRequest with caption
    send_request = client.call_args_list[1][0][0]
    assert len(send_request.caption) == 200


# ──────────────────────────────────────────────
# publish_story — limit / flood paths
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_publish_daily_limit_exceeded(mock_ss, mock_tg_class, publisher):
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    can_send = MagicMock()
    can_send.count_remains = 0
    client.return_value = can_send
    mock_tg_class.return_value = client

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is False
    assert result.retry_later is True
    assert "limit" in result.error.lower()


@pytest.mark.asyncio
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_publish_flood_wait_error(mock_ss, mock_tg_class, publisher):
    from telethon.errors import FloodWaitError

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.side_effect = FloodWaitError(request=None, capture=300)
    mock_tg_class.return_value = client

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is False
    assert result.retry_later is True
    assert "FloodWait" in result.error
    assert "300" in result.error


# ──────────────────────────────────────────────
# publish_story — error paths
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_no_media(publisher):
    result = await publisher.publish_story(FakeAccount(), [], caption=None)
    assert result.ok is False
    assert "no media" in result.error


@pytest.mark.asyncio
async def test_publish_missing_credentials():
    pub = TelegramPublisher()  # no credentials, no env
    result = await pub.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)
    assert result.ok is False
    assert "credentials" in result.error.lower()


@pytest.mark.asyncio
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_publish_network_error(mock_ss, mock_tg_class, publisher):
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.side_effect = ConnectionError("Connection refused")
    mock_tg_class.return_value = client

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is False
    assert result.retry_later is False
    assert "Connection refused" in result.error


# ──────────────────────────────────────────────
# fetch_insights
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_fetch_insights_ok(mock_ss, mock_tg_class, publisher):
    mock_tg_class.return_value = _make_insights_client(
        views_count=120, reactions_count=5, forwards_count=2
    )

    metrics = await publisher.fetch_insights(FakeAccount(), "42")

    assert metrics["views"] == 120
    assert metrics["reactions_count"] == 5
    assert metrics["forwards_count"] == 2


@pytest.mark.asyncio
async def test_fetch_insights_bad_external_id(publisher):
    metrics = await publisher.fetch_insights(FakeAccount(), "not_an_int")
    assert metrics == {}


@pytest.mark.asyncio
@patch("app.adapters.telegram.TelegramClient")
@patch("app.adapters.telegram.StringSession")
async def test_fetch_insights_empty_views(mock_ss, mock_tg_class, publisher):
    result = MagicMock()
    result.views = []

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.return_value = result
    mock_tg_class.return_value = client

    metrics = await publisher.fetch_insights(FakeAccount(), "42")
    assert metrics == {}
