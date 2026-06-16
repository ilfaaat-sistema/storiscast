import pytest
from app.adapters.stub import StubPublisher


@pytest.mark.asyncio
async def test_stub_publish_returns_ok():
    adapter = StubPublisher("vk")
    result = await adapter.publish_story(account=None, media=[], caption="test")
    assert result.ok is True
    assert result.external_id is not None
    assert result.external_id.startswith("stub_")


@pytest.mark.asyncio
async def test_stub_fetch_insights_returns_dict():
    adapter = StubPublisher("ig")
    metrics = await adapter.fetch_insights(account=None, external_id="stub_abc123")
    assert isinstance(metrics, dict)
    assert "reach" in metrics


@pytest.mark.asyncio
async def test_stub_all_platforms():
    for platform in ["vk", "tg", "ig", "fb", "wa"]:
        adapter = StubPublisher(platform)
        assert adapter.platform == platform
        result = await adapter.publish_story(None, [], None)
        assert result.ok
