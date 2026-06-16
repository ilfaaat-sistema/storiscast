"""
VK adapter tests — all HTTP mocked with respx, no real network calls.

Upload flow under test:
  1. POST stories.getPhotoUploadServer → {"response": {"upload_url": ...}}
  2. GET media from Supabase Storage → binary content
  3. POST upload_url → {"upload_result": "<hash>"}
  4. POST stories.save → {"response": {"count": 1, "items": [...]}}
"""
import json
import pytest
import respx
import httpx

from app.adapters.vk import VKPublisher

FAKE_TOKEN = "vk1.a.test_token"
MEDIA_URL = "https://test.supabase.co/storage/v1/object/public/media/story.jpg"
UPLOAD_URL = "https://pu.vk.com/c12345/upload.php"

VK_API = "https://api.vk.com/method/"


class FakeAccount:
    credentials_enc = None


class FakeMedia:
    url = MEDIA_URL
    media_type = "photo"


class FakeVideoMedia:
    url = "https://test.supabase.co/storage/v1/object/public/media/story.mp4"
    media_type = "video"


@pytest.fixture
def publisher():
    return VKPublisher(access_token=FAKE_TOKEN)


# ──────────────────────────────────────────────
# publish_story — photo
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_publish_photo_story_ok(publisher):
    respx.post(f"{VK_API}stories.getPhotoUploadServer").mock(
        return_value=httpx.Response(200, json={"response": {"upload_url": UPLOAD_URL}})
    )
    respx.get(MEDIA_URL).mock(
        return_value=httpx.Response(
            200,
            content=b"\xff\xd8\xff\xe0fake_jpeg",
            headers={"content-type": "image/jpeg"},
        )
    )
    respx.post(UPLOAD_URL).mock(
        return_value=httpx.Response(200, json={"upload_result": "abc123hash=="})
    )
    respx.post(f"{VK_API}stories.save").mock(
        return_value=httpx.Response(200, json={
            "response": {
                "count": 1,
                "items": [{"id": 789, "owner_id": 111222}],
            }
        })
    )

    result = await publisher.publish_story(FakeAccount(), [FakeMedia()], caption="Тест")

    assert result.ok is True
    assert result.external_id == "111222_789"
    assert result.error is None


@pytest.mark.asyncio
@respx.mock
async def test_publish_video_story_ok(publisher):
    respx.post(f"{VK_API}stories.getVideoUploadServer").mock(
        return_value=httpx.Response(200, json={"response": {"upload_url": UPLOAD_URL}})
    )
    video_url = FakeVideoMedia.url
    respx.get(video_url).mock(
        return_value=httpx.Response(
            200,
            content=b"\x00\x00\x00fake_mp4",
            headers={"content-type": "video/mp4"},
        )
    )
    respx.post(UPLOAD_URL).mock(
        return_value=httpx.Response(200, json={"upload_result": "video_hash=="})
    )
    respx.post(f"{VK_API}stories.save").mock(
        return_value=httpx.Response(200, json={
            "response": {
                "count": 1,
                "items": [{"id": 100, "owner_id": 111222}],
            }
        })
    )

    result = await publisher.publish_story(FakeAccount(), [FakeVideoMedia()], caption=None)

    assert result.ok is True
    assert result.external_id == "111222_100"


# ──────────────────────────────────────────────
# publish_story — error paths
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_no_media_returns_error(publisher):
    result = await publisher.publish_story(FakeAccount(), [], caption=None)
    assert result.ok is False
    assert "no media" in result.error


@pytest.mark.asyncio
@respx.mock
async def test_publish_vk_api_error(publisher):
    respx.post(f"{VK_API}stories.getPhotoUploadServer").mock(
        return_value=httpx.Response(200, json={
            "error": {"error_code": 5, "error_msg": "User authorization failed"}
        })
    )

    result = await publisher.publish_story(FakeAccount(), [FakeMedia()], caption=None)

    assert result.ok is False
    assert "VK API error 5" in result.error


@pytest.mark.asyncio
@respx.mock
async def test_publish_upload_server_http_error(publisher):
    respx.post(f"{VK_API}stories.getPhotoUploadServer").mock(
        return_value=httpx.Response(200, json={"response": {"upload_url": UPLOAD_URL}})
    )
    respx.get(MEDIA_URL).mock(
        return_value=httpx.Response(
            200,
            content=b"data",
            headers={"content-type": "image/jpeg"},
        )
    )
    respx.post(UPLOAD_URL).mock(return_value=httpx.Response(500))

    result = await publisher.publish_story(FakeAccount(), [FakeMedia()], caption=None)

    assert result.ok is False


# ──────────────────────────────────────────────
# fetch_insights
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_fetch_insights_ok(publisher):
    respx.post(f"{VK_API}stories.getStats").mock(
        return_value=httpx.Response(200, json={
            "response": {
                "views":       {"count": 200, "state": "on"},
                "replies":     {"count": 5,   "state": "on"},
                "shares":      {"count": 3,   "state": "on"},
                "likes":       {"count": 12,  "state": "on"},
                "subscribers": {"count": 1,   "state": "on"},
                "answer":      {"count": 0,   "state": "on"},
                "bans":        {"count": 0,   "state": "on"},
                "open_link":   {"count": 2,   "state": "on"},
            }
        })
    )
    respx.post(f"{VK_API}stories.getViewers").mock(
        return_value=httpx.Response(200, json={
            "response": {"count": 50, "items": []}
        })
    )

    metrics = await publisher.fetch_insights(FakeAccount(), "111222_789")

    assert metrics["views"] == 200
    assert metrics["replies"] == 5
    assert metrics["viewers_count"] == 50


@pytest.mark.asyncio
async def test_fetch_insights_bad_external_id(publisher):
    metrics = await publisher.fetch_insights(FakeAccount(), "invalid_id_format_x")
    # "invalid" is not an int — should return empty dict gracefully
    assert metrics == {}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_insights_partial_on_api_error(publisher):
    # getStats succeeds, getViewers fails — should return partial data
    respx.post(f"{VK_API}stories.getStats").mock(
        return_value=httpx.Response(200, json={
            "response": {"views": {"count": 77, "state": "on"}}
        })
    )
    respx.post(f"{VK_API}stories.getViewers").mock(
        return_value=httpx.Response(200, json={
            "error": {"error_code": 15, "error_msg": "Access denied"}
        })
    )

    metrics = await publisher.fetch_insights(FakeAccount(), "111222_789")

    assert metrics.get("views") == 77
    assert "viewers_count" not in metrics


# ──────────────────────────────────────────────
# Token resolution
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_token_from_constructor(publisher):
    """Publisher uses constructor token when account has no credentials."""
    # Verify the token is sent in the API call by checking the request body
    captured = {}

    def capture_request(request):
        body = request.content.decode()
        captured["token"] = next(
            (p.split("=")[1] for p in body.split("&") if p.startswith("access_token=")),
            None,
        )
        return httpx.Response(200, json={"response": {"upload_url": UPLOAD_URL}})

    respx.post(f"{VK_API}stories.getPhotoUploadServer").mock(side_effect=capture_request)
    respx.get(MEDIA_URL).mock(
        return_value=httpx.Response(200, content=b"img", headers={"content-type": "image/jpeg"})
    )
    respx.post(UPLOAD_URL).mock(
        return_value=httpx.Response(200, json={"upload_result": "x"})
    )
    respx.post(f"{VK_API}stories.save").mock(
        return_value=httpx.Response(200, json={
            "response": {"count": 1, "items": [{"id": 1, "owner_id": 1}]}
        })
    )

    await publisher.publish_story(FakeAccount(), [FakeMedia()], caption=None)
    assert captured.get("token") == FAKE_TOKEN
