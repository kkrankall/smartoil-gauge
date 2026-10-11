"""Home Assistant serves the integration's own icon."""

from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

BRAND = Path(__file__).parents[1] / "custom_components" / "smartoil_gauge" / "brand"


async def test_icon_served(hass: HomeAssistant, hass_client) -> None:
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()
    for image in ("icon.png", "icon@2x.png", "dark_icon.png", "logo.png"):
        resp = await client.get(f"/api/brands/integration/smartoil_gauge/{image}")
        assert resp.status == 200, image
        # logo.png isn't shipped; HA falls back to the icon.
        expected = BRAND / ("icon.png" if image == "logo.png" else image)
        assert await resp.read() == expected.read_bytes(), image
