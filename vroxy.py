from __future__ import unicode_literals
import os
import logging as log
from aiohttp import web
from configparser import ConfigParser
from typing import List
import hmac
from aiohttp.web import middleware, Response

# ── ConfigParser ile config nesnesini direkt burada oluştur ──
config = ConfigParser()
config["server"] = {
    "host": os.getenv("VROXY_HOST", "0.0.0.0"),
    "port": os.getenv("PORT", "8420"),
    "whitelist": os.getenv("VROXY_WHITELIST", ""),
    "auth_tokens": os.getenv("VROXY_AUTH_TOKENS", ""),
}

# settings.ini dosyası varsa oku (eski davranış korunuyor)
settings_file = os.path.join(os.getcwd(), "settings.ini")
if os.path.isfile(settings_file):
    config.read(settings_file)

# ── Middleware fonksiyonunu direkt burada tanımla ──
def makeTokenAuthzMiddleware(tokens: List[str]):
    """Authorizes requests based on a static list of bearer tokens"""

    @middleware
    async def _tokenAuthzMiddleware(request, handler):
        auth_token = ""
        # Authorization: Bearer <token>
        if auth_header := request.headers.get("Authorization"):
            header_parts: List[str] = auth_header.split(None, 1)
            if len(header_parts) == 2 and header_parts[0].lower() == "bearer":
                auth_token = header_parts[1]
        # Query param ile token kabul et (antipattern ama kabul edilebilir risk)
        if auth_query := request.query.get("token"):
            auth_token = auth_query
        for t in tokens:
            # compare_digest ile timing attack önleme
            if hmac.compare_digest(t, auth_token):
                return await handler(request)

        return Response(status=401, text="Missing authorization token")

    return _tokenAuthzMiddleware

# Diğer import'lar (app/resolver ve app/exceptions hâlâ var, onları da taşımak istersen söyle)
from app.resolver import resolveUrl
from app.exceptions import *

routes = web.RouteTableDef()
log.basicConfig(level=log.DEBUG)

@routes.view("/healthz")
class Health(web.View):
    async def get(self):
        return web.Response(status=200, text="OK")

@routes.view("/")
class YTDLProxy(web.View):
    async def head(self):
        if not self.request.query.get("url") and not self.request.query.get("u"):
            res = web.Response(status=404)
            return res
        return await self.process()

    async def get(self):
        if not self.request.query.get("url") and not self.request.query.get("u"):
            res = web.Response(status=404, text="Missing Url Param")
            return res
        return await self.process()

    async def process(self):
        url = None
        res = web.Response(status=500)
        try:
            url = await resolveUrl(self.request.query)
            res = web.Response(status=307, headers={"Location": url})
        except Error400BadRequest:
            res = web.Response(status=400)
        except Error403Forbidden:
            res = web.Response(status=403)
        except Error403Whitelist:
            res = web.Response(status=403, text="Domain not in whitelist")
        except Error404NotFound:
            res = web.Response(status=404)
        except Error408Timeout:
            res = web.Response(status=408)
        except Error410Gone:
            res = web.Response(status=410)
        except Error429TooManyRequests:
            res = web.Response(status=429)
        except Exception:
            res = web.Response(status=500)
        return res

async def strip_headers(req: web.Request, res: web.StreamResponse):
    del res.headers['Server']

app = web.Application()

# auth_tokens varsa middleware ekle
if auth_tokens_config := config["server"].get("auth_tokens"):
    auth_tokens = [t.strip() for t in auth_tokens_config.split(",")]
    authz_middleware = makeTokenAuthzMiddleware(auth_tokens)
    app.middlewares.append(authz_middleware)

app.add_routes(routes)
app.on_response_prepare.append(strip_headers)

print("Starting Vroxy server.")

if os.environ.get("TMUX"):
    print("--- TMUX USAGE REMINDER ---")
    print("If the service is running in a TMUX instance, you can exit without killing the service with CTRL+B and then press D")
    print("If you run the CTRL+C command, you will kill the service making your urls return 502.")
    print(f"Remember you can restart the service by exiting the TMUX instance with CTRL+B and then D, then run 'bash {os.path.dirname(__file__)}/vroxy_reload.sh'", flush=True)

web.run_app(app, host=config["server"]["host"], port=int(config["server"]["port"]))
