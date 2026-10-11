"""Client for the Smart Oil Gauge web app (app.smartoilgauge.com).

Smart Oil Gauge has no owner API, so this makes the same calls as the web
app:
    1. GET  /login.php             -> PHPSESSID cookie + ccf_nonce form token
    2. POST /login.php             username, user_pass, remember, ccf_nonce
    3. POST /ajax/main_ajax.php    action=get_tanks_list (level, usage, battery)
    4. POST /ajax/main_ajax.php    action=get_graph_data (history, temperature)

The PHPSESSID cookie carries the login. The client logs in again only when
the site answers "Access Denied".
"""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

BASE_URL = URL("https://app.smartoilgauge.com")
SESSION_COOKIE = "PHPSESSID"
TIMEOUT = aiohttp.ClientTimeout(total=30)
NONCE_RE = re.compile(r"""name=['"]ccf_nonce['"][^>]*value=['"]([^'"]+)['"]""")
APP_ERROR_RE = re.compile(r"""class=['"]app_error['"][^>]*>(.*?)</p>""", re.S)


class SmartOilError(Exception):
    """Base error for the Smart Oil Gauge client."""


class SmartOilConnectionError(SmartOilError):
    """The site could not be reached or answered with something unexpected."""


class SmartOilAuthError(SmartOilError):
    """The site did not accept the username and password."""


class _AccessDenied(SmartOilError):
    """The session cookie is missing or has expired."""


class SmartOilClient:
    """Logs in to app.smartoilgauge.com and reads tank data."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str,
                 base_url: URL = BASE_URL) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._base = base_url

    @property
    def session_cookie(self) -> str | None:
        """The current login cookie, for saving across restarts."""
        cookie = self._session.cookie_jar.filter_cookies(self._base).get(SESSION_COOKIE)
        return cookie.value if cookie else None

    def restore_session(self, value: str) -> None:
        """Reuse a saved login cookie."""
        self._session.cookie_jar.update_cookies({SESSION_COOKIE: value}, response_url=self._base)

    async def login(self) -> None:
        """Log in with the form the web app uses."""
        _LOGGER.debug("Logging in to Smart Oil Gauge as %s", self._username)
        self._session.cookie_jar.clear_domain(self._base.host)
        try:
            async with self._session.get(self._base / "login.php", timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                page = await resp.text()
            match = NONCE_RE.search(page)
            if not match:
                raise SmartOilConnectionError(
                    "Login page has no ccf_nonce field; the site may have changed")
            async with self._session.post(self._base / "login.php", timeout=TIMEOUT, data={
                "username": self._username,
                "user_pass": self._password,
                "remember": "on",
                "ccf_nonce": match.group(1),
            }) as resp:
                resp.raise_for_status()
                page = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartOilConnectionError(f"Login request failed: {err}") from err
        # The login page answers 200 whether or not the password was right,
        # so check that the new session can actually read data.
        try:
            await self._ajax("get_tanks_list", tank_id=0)
        except _AccessDenied:
            match = APP_ERROR_RE.search(page)
            reason = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""
            raise SmartOilAuthError(reason or "Username or password not accepted") from None

    async def _ajax(self, action: str, **params: Any) -> dict[str, Any]:
        try:
            async with self._session.post(
                self._base / "ajax" / "main_ajax.php",
                data={"action": action, **params},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartOilConnectionError(f"{action} failed: {err}") from err
        except ValueError as err:
            raise SmartOilConnectionError(f"{action}: response is not JSON") from err
        if not isinstance(body, dict):
            raise SmartOilConnectionError(f"{action}: unexpected response")
        if body.get("result") == "ok":
            return body
        if str(body.get("Status")) == "401" or body.get("message") == "Access Denied":
            raise _AccessDenied(action)
        raise SmartOilConnectionError(f"{action}: {body.get('message') or body}")

    async def _call(self, action: str, **params: Any) -> dict[str, Any]:
        """Run an ajax call, logging in first if the session has expired."""
        try:
            return await self._ajax(action, **params)
        except _AccessDenied:
            _LOGGER.debug("No valid Smart Oil Gauge session; logging in")
        await self.login()
        try:
            return await self._ajax(action, **params)
        except _AccessDenied as err:
            raise SmartOilConnectionError(f"{action}: access denied right after login") from err

    async def get_tanks(self) -> list[dict[str, Any]]:
        """Return every tank on the account, as the web app's tank list."""
        return (await self._call("get_tanks_list", tank_id=0)).get("tanks") or []

    async def get_graph_data(self, tank: dict[str, Any]) -> dict[str, Any]:
        """Return a tank's usage history (day, week, month, year)."""
        return await self._call("get_graph_data", tank_id=tank["tank_id"],
                                data_servers=tank.get("data_servers") or "")
