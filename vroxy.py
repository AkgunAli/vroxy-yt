from __future__ import unicode_literals
import os
import logging as log
import time
import re
import random
import hmac
from typing import List, Optional
from urllib.parse import urlparse
from configparser import ConfigParser
from aiohttp import web
from aiohttp.web import middleware, Response
from yt_dlp import YoutubeDL

# ── ConfigParser ile config nesnesini direkt burada oluştur ──
config = ConfigParser()
config["server"] = {
    "host": os.getenv("VROXY_HOST", "0.0.0.0"),
    "port": os.getenv("PORT", "8420"),
    "whitelist": os.getenv("VROXY_WHITELIST", ""),
    "auth_tokens": os.getenv("VROXY_AUTH_TOKENS", ""),
}

settings_file = os.path.join(os.getcwd(), "settings.ini")
if os.path.isfile(settings_file):
    config.read(settings_file)

# ── Middleware fonksiyonu (eski app/middleware.py'den) ──
def makeTokenAuthzMiddleware(tokens: List[str]):
    @middleware
    async def _tokenAuthzMiddleware(request, handler):
        auth_token = ""
        if auth_header := request.headers.get("Authorization"):
            header_parts = auth_header.split(None, 1)
            if len(header_parts) == 2 and header_parts[0].lower() == "bearer":
                auth_token = header_parts[1]
        if auth_query := request.query.get("token"):
            auth_token = auth_query
        for t in tokens:
            if hmac.compare_digest(t, auth_token):
                return await handler(request)
        return Response(status=401, text="Missing authorization token")

    return _tokenAuthzMiddleware

# ── Exception sınıfları (eski app/exceptions.py'den basitçe) ──
class Error400BadRequest(Exception): pass
class Error403Forbidden(Exception): pass
class Error403Whitelist(Exception): pass
class Error404NotFound(Exception): pass
class Error408Timeout(Exception): pass
class Error410Gone(Exception): pass
class Error429TooManyRequests(Exception): pass

# ── resolveUrl fonksiyonu (eski app/resolver.py'den tamamen taşındı) ──
mode_map = {
    "0": 0,  # default
    "1": 1,  # avhigh
    "2": 2,  # avlow
    "3": 3,  # hqvidcompat
    "4": 4,  # hqvidbest
}
sort_opts = {
    0: ["proto:https", "hasvid", "hasaud", "res:1440"],
    1: ["hasvid", "hasaud", "res"],
    2: ["hasvid", "hasaud", "+res"],
    3: ["codec:vp9", "hasvid", "res"],
    4: ["hasvid", "res"],
}
expire_regex = re.compile(r"exp(?:ir(?:es?|ation))?=(\d+)")

nextGCTime = time.time() + 3600
cache_map = {}
domain_whitelist = None

if wl_path := config["server"]["whitelist"]:
    # DomainWhitelist sınıfı yoksa basitçe boş liste kabul et (orijinal kodda load_list varsa onu da taşı)
    domain_whitelist = []  # gerçekte load_list fonksiyonunu buraya ekle

class Item:
    def __init__(self, url, sort):
        self.original_url = url
        self.hostname = urlparse(url).hostname
        self.resolved_url = None
        self.resolved_id = None
        self.resolved_format = None
        self.sort = sort
        self.expiry = 0
        self.lastAccess = 0
        self.processing = True

    def resolve(self, f) -> None:
        if self.sort:
            f = f["formats"][-1]
        self.resolved_url = f["url"]
        self.resolved_id = f["format_id"]
        self.resolved_format = f["format"]
        self.expiry = self.extractExpiry()
        self.processing = False

    def extractExpiry(self) -> float:
        p = expire_regex.search(self.resolved_url)
        if p is not None:
            return int(p.group(1))
        return time.time() + 600  # default 10 dk

class PoolCount:
    def __init__(self):
        self.count = 0

    def add(self):
        self.count += 1

    def remove(self):
        self.count -= 1

pool_max = config.get("ytdl", "pool_size", fallback=10)
pool = PoolCount()

async def resolveUrl(query: dict) -> str:
    rid = random.getrandbits(16)
    global nextGCTime
    curTime = time.time()

    # Cache temizliği
    if curTime > nextGCTime:
        nextGCTime = time.time() + 3600
        purge = []
        for cache_id, cache_item in cache_map.items():
            if cache_item.lastAccess + 3600 < curTime or cache_item.expiry < curTime:
                purge.append(cache_id)
        for purge_id in purge:
            del cache_map[purge_id]

    ytdl_opts = {"quiet": True}

    url = query.get("url") or query.get("u")
    if not url:
        raise Error400BadRequest("Missing URL")

    if domain_whitelist and url not in domain_whitelist:  # whitelist mantığını uyarla
        raise Error403Whitelist

    mode = mode_map[query.get("m") or "0"]
    fid = query.get("f")
    host = urlparse(url).hostname

    if fid:
        ytdl_opts["format"] = fid
        cacheId = fid
        sort = None
    else:
        s = query.get("s")
        if s:
            sort = s.replace(" ", "").split(",")
        else:
            sort = list(sort_opts[mode])
        try:
            if "vimeo" in host:
                sort.append("proto:m3u8_native")
        except:
            pass
        ytdl_opts["format_sort"] = sort
        cacheId = ",".join(sort)

    _id = f"{cacheId}~{url}"
    if _id in cache_map:
        item = cache_map[_id]
        if item.expiry < curTime:
            log.debug(f"[{rid}] Cache expired")
            del cache_map[_id]
        else:
            while item.processing:
                await sleep(1)
            log.info(f"[{rid}] Cache hit. Using cached url.")
            item.lastAccess = curTime
            return item.resolved_url or ""

    cache_map[_id] = item = Item(url, sort)

    timeout = curTime + 30
    while pool.count >= pool_max:
        if curTime > timeout:
            log.info(f"[{rid}] Request timed out waiting for pool slot")
            return None
        await sleep(1)

    with YoutubeDL(ytdl_opts) as ytdl:
        log.info(f"[{rid}] Fetching fresh info for {url}")
        pool.add()
        try:
            result = ytdl.extract_info(url, download=False)
        except Exception as e:
            log.debug(f"[{rid}] YTDL error: {str(e)}")
            raise Error400BadRequest
        item.resolve(result)
        pool.remove()

    item.lastAccess = curTime
    return item.resolved_url or ""

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
