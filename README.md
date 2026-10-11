# Smart Oil Gauge for Home Assistant

A custom integration for the [Smart Oil Gauge](https://www.smartoilgauge.com)
heating-oil tank monitor. It reads the same data as the web app at
app.smartoilgauge.com: tank level, usage rate, days until the tank runs low,
usage history, deliveries and sensor health. Each tank on the account
becomes a device in Home Assistant.

Smart Oil Gauge doesn't offer an API for owners, so the integration logs in
the way the website does and reads the website's own data calls. If the
company changes the site, the integration may need an update.

Not affiliated with Smart Oil Gauge or Connected Consumer Fuel.

## Install

1. In HACS, open the menu → **Custom repositories**, add
   `https://github.com/kkrankall/smartoil-gauge` as an **Integration**.
2. Download **Smart Oil Gauge** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Smart Oil Gauge**
   and log in with your app.smartoilgauge.com username (or email) and password.

## Entities

For each tank:

| Entity | Notes |
|---|---|
| Gallons | Current reading, as shown on the website. |
| Level | Percent of the tank's nominal capacity. |
| Usage rate | Gallons per day: the website's rolling average over the past week or two. |
| Days to low level | Days until the level reaches the low-level alert set on the website (1/4 tank by default). |
| Days to 1/8 tank | Days until 1/8 of a tank. |
| Gallons to fill | Room left up to the tank's fillable capacity. |
| Used last 7 / 30 / 365 days | Gallons burned in each period, net of deliveries, as the website's graph reports them. |
| Last fill, Last fill amount | The most recent delivery, found as a jump of at least 20 gallons (or 10% of the tank) between readings. |
| Temperature | Temperature at the gauge, in °F. |
| Last reading | When the gauge last uploaded a reading (about hourly). |
| Low level | On while the level is below the low-level alert. |
| Sensor offline | On after 96 hours without a reading, when the website also flags the gauge offline. |
| Battery, Sensor status, Capacity, Fillable capacity, Low level alert | Diagnostic. |

The days-to estimates follow the website's own rules: no estimate while the
gauge is offline or while usage is under 0.2 gallons a day.

## How it works

- Polls every 30 minutes. The gauge itself uploads about once an hour.
- The login uses the website's session cookie. The cookie is saved, so a
  Home Assistant restart doesn't log in again. The integration only sends
  your password when the site says the session has expired.
- If the password stops working, Home Assistant shows a **Reauthenticate**
  prompt instead of retrying, so the integration can't lock your account.
- **Download diagnostics** on the integration gives the raw tank data, with
  your username, ZIP code, sensor ID and dealer link removed.

## Development

```
pip install pytest-homeassistant-custom-component
pytest
```

The tests run the client against a fake site that mirrors the real login
form and data calls, and check the values against captured responses.
