"""
Instagram adapter tests — all HTTP mocked with respx, no real network calls.

Publish flow under test:
  1. GET  /{user_id}/content_publishing_limit → quota check
  2. POST /{user_id}/media (media_type=STORIES) → creation_id
  3. (video) GET /{creation_id}?fields=status_code → FINISHED
  4. POST /{user_id}/media_publish (creation_id) → media_id

Insights flow:
  GET /{media_id}/insights?metric=impressions,reach,replies → basic metrics
  GET /{media_id}/insights?metric=navigation&breakdown=... → navigation breakdown
"""
import pytest
import respx
import httpx

from app.adapters.instagram import InstagramPublisher

FAKE_TOKEN = "EAAtest_token_ig"
FAKE_USER_ID = "123456789"
FAKE_CONTAINER_ID = "111222333"
FAKE_MEDIA_ID = "987654321_123456789"
GRAPH = "https://graph.facebook.com/v21.0"

MEDIA_URL_PHOTO = "https://test.supabase.co/storage/v1/object/public/media/story.jpg"
MEDIA_URL_VIDEO = "https://test.supabase.co/storage/v1/object/public/media/story.mp4"


class FakeAccount:
    credentials_enc = None


class FakePhotoMedia:
    url = MEDIA_URL_PHOTO
    media_type = "photo"


class FakeVideoMedia:
    url = MEDIA_URL_VIDEO
    media_type = "video"


@pytest.fixture
def publisher():
    return InstagramPublisher(
        access_token=FAKE_TOKEN,
        ig_user_id=FAKE_USER_ID,
        version="v21.0",
    )


def _quota_ok_response():
    return httpx.Response(
        200,
        json={"data": [{"config": {"quota_total": 100, "quota_duration": 86400}, "quota_usage": 5}]},
    )


def _quota_exhausted_response():
    return httpx.Response(
        200,
        json={"data": [{"config": {"quota_total": 100, "quota_duration": 86400}, "quota_usage": 100}]},
    )


# ──────────────────────────────────────────────
# publish_story — photo
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_publish_photo_story_ok(publisher):
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=_quota_ok_response()
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media").mock(
        return_value=httpx.Response(200, json={"id": FAKE_CONTAINER_ID})
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": FAKE_MEDIA_ID})
    )

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption="Тест сторис")

    assert result.ok is True
    assert result.external_id == FAKE_MEDIA_ID
    assert result.error is None
    assert result.retry_later is False


# ──────────────────────────────────────────────
# publish_story — video (with status polling)
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_publish_video_story_ok(publisher):
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=_quota_ok_response()
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media").mock(
        return_value=httpx.Response(200, json={"id": FAKE_CONTAINER_ID})
    )
    # Status polling — returns FINISHED immediately (no sleep needed)
    respx.get(f"{GRAPH}/{FAKE_CONTAINER_ID}").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": FAKE_MEDIA_ID})
    )

    result = await publisher.publish_story(FakeAccount(), [FakeVideoMedia()], caption=None)

    assert result.ok is True
    assert result.external_id == FAKE_MEDIA_ID


@pytest.mark.asyncio
@respx.mock
async def test_publish_video_processing_error(publisher):
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=_quota_ok_response()
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media").mock(
        return_value=httpx.Response(200, json={"id": FAKE_CONTAINER_ID})
    )
    respx.get(f"{GRAPH}/{FAKE_CONTAINER_ID}").mock(
        return_value=httpx.Response(200, json={"status_code": "ERROR"})
    )

    result = await publisher.publish_story(FakeAccount(), [FakeVideoMedia()], caption=None)

    assert result.ok is False
    assert "ERROR" in result.error


# ──────────────────────────────────────────────
# publish_story — rate limit / error paths
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_publish_quota_exhausted_returns_retry_later(publisher):
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=_quota_exhausted_response()
    )

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is False
    assert result.retry_later is True
    assert "quota" in result.error.lower()


@pytest.mark.asyncio
async def test_publish_no_media_returns_error(publisher):
    result = await publisher.publish_story(FakeAccount(), [], caption=None)
    assert result.ok is False
    assert "no media" in result.error


@pytest.mark.asyncio
async def test_publish_missing_credentials():
    pub = InstagramPublisher()  # no token/user_id, no env
    result = await pub.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)
    assert result.ok is False
    assert "credentials" in result.error.lower()


@pytest.mark.asyncio
@respx.mock
async def test_publish_ig_api_error(publisher):
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=_quota_ok_response()
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": 190, "message": "Invalid OAuth access token"}},
        )
    )

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is False
    assert "190" in result.error


@pytest.mark.asyncio
@respx.mock
async def test_publish_quota_check_failure_is_optimistic(publisher):
    """If content_publishing_limit call fails, we proceed optimistically."""
    respx.get(f"{GRAPH}/{FAKE_USER_ID}/content_publishing_limit").mock(
        return_value=httpx.Response(500)
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media").mock(
        return_value=httpx.Response(200, json={"id": FAKE_CONTAINER_ID})
    )
    respx.post(f"{GRAPH}/{FAKE_USER_ID}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": FAKE_MEDIA_ID})
    )

    result = await publisher.publish_story(FakeAccount(), [FakePhotoMedia()], caption=None)

    assert result.ok is True
    assert result.external_id == FAKE_MEDIA_ID


# ──────────────────────────────────────────────
# fetch_insights
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_fetch_insights_ok(publisher):
    insights_url = f"{GRAPH}/{FAKE_MEDIA_ID}/insights"

    def insights_side_effect(request):
        params = dict(httpx.URL(str(request.url)).params)
        metric = params.get("metric", "")
        if "navigation" in metric:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "name": "navigation",
                            "period": "lifetime",
                            "total_value": {
                                "breakdowns": [
                                    {
                                        "dimension_keys": ["story_navigation_action_type"],
                                        "results": [
                                            {"dimension_values": ["TAP_FORWARD"], "value": 30},
                                            {"dimension_values": ["TAP_BACK"], "value": 10},
                                            {"dimension_values": ["TAP_EXIT"], "value": 15},
                                            {"dimension_values": ["SWIPE_FORWARD"], "value": 5},
                                        ],
                                    }
                                ]
                            },
                        }
                    ]
                },
            )
        # basic metrics call
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "impressions", "period": "lifetime", "values": [{"value": 120}]},
                    {"name": "reach", "period": "lifetime", "values": [{"value": 95}]},
                    {"name": "replies", "period": "lifetime", "values": [{"value": 7}]},
                ]
            },
        )

    respx.get(insights_url).mock(side_effect=insights_side_effect)

    metrics = await publisher.fetch_insights(FakeAccount(), FAKE_MEDIA_ID)

    assert metrics["impressions"] == 120
    assert metrics["reach"] == 95
    assert metrics["replies"] == 7
    assert metrics["taps_forward"] == 30
    assert metrics["taps_back"] == 10
    assert metrics["exits"] == 15
    assert metrics["swipe_forward"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_fetch_insights_basic_only_when_nav_fails(publisher):
    """Navigation call fails — basic metrics are still saved (partial data)."""
    insights_url = f"{GRAPH}/{FAKE_MEDIA_ID}/insights"
    call_count = 0

    def insights_side_effect(request):
        nonlocal call_count
        call_count += 1
        params = dict(httpx.URL(str(request.url)).params)
        if "navigation" in params.get("metric", ""):
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "impressions", "period": "lifetime", "values": [{"value": 80}]},
                ]
            },
        )

    respx.get(insights_url).mock(side_effect=insights_side_effect)

    metrics = await publisher.fetch_insights(FakeAccount(), FAKE_MEDIA_ID)

    assert metrics.get("impressions") == 80
    assert "taps_forward" not in metrics


@pytest.mark.asyncio
async def test_fetch_insights_empty_external_id(publisher):
    metrics = await publisher.fetch_insights(FakeAccount(), "")
    assert metrics == {}


@pytest.mark.asyncio
async def test_fetch_insights_missing_credentials():
    pub = InstagramPublisher()  # no token
    metrics = await pub.fetch_insights(FakeAccount(), FAKE_MEDIA_ID)
    assert metrics == {}
