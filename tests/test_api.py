"""The client against a fake app.smartoilgauge.com that behaves like the real one."""

import itertools

import pytest
from aiohttp import ClientSession, CookieJar, web
from aiohttp.test_utils import TestServer

from custom_components.smartoil_gauge.api import (
    SmartOilAuthError,
    SmartOilClient,
    SmartOilConnectionError,
)

from .conftest import load

# Trimmed from the real login page: single-quoted attributes, error paragraph.
LOGIN_PAGE = """<form class="content-container" method="post">
  <input type="text" name='username' id="inputUsername" required autofocus>
  <input type="password" name='user_pass' id="inputPassword" required>
  <input type="checkbox" id="remember" name="remember">
  <p class='app_error'>{error}</p>
  <button class="btn" type="submit">Login</button>
  <input type='hidden' name='ccf_nonce' value='{nonce}' />            </form>"""


class FakeSite:
    """PHP-style sessions: GET login.php starts a session, a good POST logs it in."""

    def __init__(self) -> None:
        self.password = "right"
        self.logged_in: set[str] = set()
        self.nonces: dict[str, str] = {}
        self.logins = 0
        self.down = False
        self._ids = itertools.count(1)

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/login.php", self.login_page)
        app.router.add_post("/login.php", self.login_post)
        app.router.add_get("/app.php", self.app_page)
        app.router.add_post("/ajax/main_ajax.php", self.ajax)
        return app

    async def login_page(self, request: web.Request) -> web.Response:
        sid = f"sid{next(self._ids)}"
        self.nonces[sid] = f"nonce{sid}"
        resp = web.Response(text=LOGIN_PAGE.format(error="", nonce=self.nonces[sid]),
                            content_type="text/html")
        resp.set_cookie("PHPSESSID", sid)
        return resp

    async def login_post(self, request: web.Request) -> web.Response:
        form = await request.post()
        sid = request.cookies.get("PHPSESSID", "")
        self.logins += 1
        if form.get("ccf_nonce") != self.nonces.get(sid) or form.get("user_pass") != self.password:
            return web.Response(content_type="text/html", text=LOGIN_PAGE.format(
                error="Invalid username or password.", nonce=self.nonces.get(sid, "")))
        self.logged_in.add(sid)
        raise web.HTTPFound("/app.php")

    async def app_page(self, request: web.Request) -> web.Response:
        return web.Response(text="app")

    async def ajax(self, request: web.Request) -> web.Response:
        if self.down:
            raise web.HTTPInternalServerError
        form = await request.post()
        # The real site answers these two ways depending on the cookie.
        if "PHPSESSID" not in request.cookies:
            return web.json_response({"Status": 401})
        if request.cookies["PHPSESSID"] not in self.logged_in:
            return web.json_response({"result": "error", "message": "Access Denied"})
        if form["action"] == "get_tanks_list":
            return web.json_response(load("tanks_list.json"))
        if form["action"] == "get_graph_data":
            assert form["data_servers"] == "data.connectedconsumerfuel.com"
            return web.json_response(load("graph_data.json"))
        return web.json_response({"result": "error", "message": "Unknown action"})


@pytest.fixture
async def site(socket_enabled):
    fake = FakeSite()
    server = TestServer(fake.app(), host="127.0.0.1")
    await server.start_server()
    fake.url = server.make_url("/")
    yield fake
    await server.close()


@pytest.fixture
async def session():
    # unsafe=True lets the jar keep cookies for an IP address host.
    async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as s:
        yield s


def _client(site, session, password="right"):
    return SmartOilClient(session, "kevin", password, base_url=site.url)


async def test_logs_in_on_first_call(site, session):
    client = _client(site, session)
    tanks = await client.get_tanks()
    assert [t["tank_id"] for t in tanks] == ["1001"]
    assert site.logins == 1
    assert client.session_cookie in site.logged_in
    graph = await client.get_graph_data(tanks[0])
    assert "2001" in graph["datasets"]
    assert site.logins == 1


async def test_saved_cookie_skips_login(site, session):
    await _client(site, session).get_tanks()
    cookie = _client(site, session).session_cookie
    async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as fresh:
        client = _client(site, fresh)
        client.restore_session(cookie)
        await client.get_tanks()
    assert site.logins == 1


async def test_expired_session_logs_in_again(site, session):
    client = _client(site, session)
    await client.get_tanks()
    site.logged_in.clear()
    await client.get_tanks()
    assert site.logins == 2


async def test_wrong_password(site, session):
    with pytest.raises(SmartOilAuthError, match="Invalid username or password"):
        await _client(site, session, password="wrong").get_tanks()


async def test_site_down(site, session):
    site.down = True
    with pytest.raises(SmartOilConnectionError):
        await _client(site, session).get_tanks()
