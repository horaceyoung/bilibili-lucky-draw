#!/usr/bin/env python3
"""
B站动态抽奖工具 - 本地服务器
启动后浏览器打开 http://localhost:8080

提供以下 API:
  GET /api/dynamic?id=xxx                   - 动态详情
  GET /api/reposts?id=xxx&offset=           - 转发列表（需 SESSDATA）
  GET /api/comments?oid=xxx&next=0          - 评论列表（cursor 分页）
  GET /api/likes?id=xxx&pn=1                - 点赞列表（需 SESSDATA）
  GET /api/follow?fids=1,2,3                - 关注关系检查（需 SESSDATA）

所有请求可附带 &sessdata=xxx 参数
"""

import hashlib
import http.cookiejar
import http.server
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

PORT = 8080

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
}


def bili_get(url: str, sessdata: str = "") -> dict:
    """发起 GET 请求到 B站 API，返回解析后的 JSON"""
    req = urllib.request.Request(url, headers=BASE_HEADERS)
    if sessdata:
        req.add_header("Cookie", f"SESSDATA={sessdata}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ============================================================
# Route handlers
# ============================================================

def handle_dynamic(params: dict) -> dict:
    """获取动态详情（旧版 API，无需登录）"""
    dynamic_id = params.get("id", [""])[0]
    if not dynamic_id:
        return {"code": -1, "message": "missing id"}
    url = (
        "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/"
        f"get_dynamic_detail?dynamic_id={dynamic_id}"
    )
    return bili_get(url, params.get("sessdata", [""])[0])


def handle_reposts(params: dict) -> dict:
    """获取转发列表（旧版 API，需要 SESSDATA）"""
    dynamic_id = params.get("id", [""])[0]
    offset = params.get("offset", [""])[0]
    sessdata = params.get("sessdata", [""])[0]
    if not dynamic_id:
        return {"code": -1, "message": "missing id"}
    url = (
        "https://api.vc.bilibili.com/dynamic_repost/v1/dynamic_repost/"
        f"repost_detail?dynamic_id={dynamic_id}&ps=20&offset={offset}"
    )
    return bili_get(url, sessdata)


def handle_comments(params: dict) -> dict:
    """获取评论列表（reply/main 接口，cursor 分页，无需登录）"""
    oid = params.get("oid", [""])[0]
    comment_type = params.get("type", ["11"])[0]
    next_cursor = params.get("next", ["0"])[0]
    mode = params.get("mode", ["2"])[0]
    sessdata = params.get("sessdata", [""])[0]
    if not oid:
        return {"code": -1, "message": "missing oid"}
    url = (
        f"https://api.bilibili.com/x/v2/reply/main?"
        f"type={comment_type}&oid={oid}&mode={mode}&ps=20&next={next_cursor}"
    )
    return bili_get(url, sessdata)


def handle_likes(params: dict) -> dict:
    """获取点赞列表（旧版 API，需要 SESSDATA）"""
    dynamic_id = params.get("id", [""])[0]
    pn = params.get("pn", ["1"])[0]
    sessdata = params.get("sessdata", [""])[0]
    if not dynamic_id:
        return {"code": -1, "message": "missing id"}
    url = (
        "https://api.vc.bilibili.com/dynamic_like/v1/dynamic_like/"
        f"spec_item_likes?dynamic_id={dynamic_id}&ps=50&pn={pn}"
    )
    return bili_get(url, sessdata)


def handle_follow(params: dict) -> dict:
    """检查关注关系"""
    fids = params.get("fids", [""])[0]
    sessdata = params.get("sessdata", [""])[0]
    if not fids:
        return {"code": -1, "message": "missing fids"}
    url = f"https://api.bilibili.com/x/relation/relations?fids={fids}"
    return bili_get(url, sessdata)


def handle_video(params: dict) -> dict:
    """获取视频详情（支持 bvid 或 aid）"""
    bvid = params.get("bvid", [""])[0]
    aid = params.get("aid", [""])[0]
    sessdata = params.get("sessdata", [""])[0]
    if bvid:
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    elif aid:
        url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
    else:
        return {"code": -1, "message": "missing bvid or aid"}
    return bili_get(url, sessdata)


ROUTES = {
    "/api/dynamic": handle_dynamic,
    "/api/reposts": handle_reposts,
    "/api/comments": handle_comments,
    "/api/likes": handle_likes,
    "/api/follow": handle_follow,
    "/api/video": handle_video,
}


class ReuseServer(http.server.HTTPServer):
    allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ROUTES:
            params = urllib.parse.parse_qs(parsed.query)
            try:
                result = ROUTES[path](params)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self._respond(200, body)
            except urllib.error.HTTPError as e:
                body = e.read()
                self._respond(e.code, body)
            except Exception as e:
                err = json.dumps({"code": -1, "message": str(e)}, ensure_ascii=False)
                self._respond(502, err.encode("utf-8"))
        else:
            super().do_GET()

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        req = args[0] if args else ""
        if "/api/" in req:
            path = req.split()[1] if " " in req else req
            # 简化显示
            route = urllib.parse.urlparse(path).path
            print(f"  [API] {route}")
        elif "GET / " in req or "GET /index" in req:
            print(f"  [页面] index.html")
        # 静态资源不打印


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with ReuseServer(("", PORT), Handler) as httpd:
        print(f"\n{'='*50}")
        print(f"  B站动态抽奖工具")
        print(f"{'='*50}")
        print(f"  浏览器打开: http://localhost:{PORT}")
        print(f"  按 Ctrl+C 停止")
        print()
        print(f"  提示: 转发和点赞接口需要填写 SESSDATA")
        print(f"  获取方式: 登录B站 -> F12 -> Application -> Cookies")
        print(f"           -> 找到 SESSDATA 的值并复制")
        print(f"{'='*50}\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")


if __name__ == "__main__":
    main()
