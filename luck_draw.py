#!/usr/bin/env python3
"""
Bilibili 动态抽奖工具
用法: python luck_draw.py <动态URL或ID> [选项]

示例:
  python luck_draw.py https://t.bilibili.com/123456 --conditions 转发 评论
  python luck_draw.py 123456 --conditions 转发 评论 点赞 --count 3
"""

import argparse
import random
import re
import sys
import time
from typing import Optional

import requests

# ============================================================
# Bilibili API 封装
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

API_DYNAMIC_DETAIL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
API_REPOST_LIST = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail/forward"
API_REPLY_LIST = "https://api.bilibili.com/x/v2/reply"
API_LIKE_LIST = "https://api.vc.bilibili.com/dynamic_like/v1/dynamic_like/spec_item_likes"


def parse_dynamic_id(url_or_id: str) -> str:
    """从 URL 或纯数字中解析出动态 ID"""
    # 纯数字
    if url_or_id.isdigit():
        return url_or_id
    # t.bilibili.com/123456
    m = re.search(r"t\.bilibili\.com/(\d+)", url_or_id)
    if m:
        return m.group(1)
    # bilibili.com/opus/123456
    m = re.search(r"bilibili\.com/opus/(\d+)", url_or_id)
    if m:
        return m.group(1)
    print(f"[错误] 无法解析动态 ID: {url_or_id}")
    sys.exit(1)


def make_session(sessdata: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    if sessdata:
        s.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")
    return s


# ---------- 动态详情 ----------

def get_dynamic_detail(sess: requests.Session, dynamic_id: str) -> dict:
    """获取动态详情，返回原始 item"""
    r = sess.get(API_DYNAMIC_DETAIL, params={"id": dynamic_id, "timezone_offset": -480})
    data = r.json()
    if data.get("code") != 0:
        print(f"[错误] 获取动态详情失败: {data.get('message', '未知错误')}")
        sys.exit(1)
    return data["data"]["item"]


# ---------- 转发列表 ----------

def fetch_repost_users(sess: requests.Session, dynamic_id: str) -> dict[int, str]:
    """返回 {uid: 用户名} 的转发用户"""
    users: dict[int, str] = {}
    offset = ""
    while True:
        params = {"id": dynamic_id, "offset": offset}
        r = sess.get(API_REPOST_LIST, params=params)
        data = r.json()
        if data.get("code") != 0:
            print(f"  [警告] 获取转发列表失败: {data.get('message')}")
            break
        items = data.get("data", {}).get("items") or []
        if not items:
            break
        for item in items:
            modules = item.get("modules", {})
            author = modules.get("module_author", {})
            mid = author.get("mid")
            name = author.get("name", "")
            if mid:
                users[int(mid)] = name
        offset = str(data["data"].get("offset", ""))
        if not data["data"].get("has_more"):
            break
        time.sleep(0.3)
    return users


# ---------- 评论列表 ----------

def fetch_reply_users(sess: requests.Session, dynamic_id: str, oid: str, dtype: int = 17) -> dict[int, str]:
    """
    获取评论用户。dtype=17 表示动态评论区。
    oid 通常是动态 id_str 或 rid。
    """
    users: dict[int, str] = {}
    pn = 1
    while True:
        params = {"type": dtype, "oid": oid, "sort": 0, "ps": 30, "pn": pn}
        r = sess.get(API_REPLY_LIST, params=params)
        data = r.json()
        if data.get("code") != 0:
            print(f"  [警告] 获取评论列表失败: {data.get('message')}")
            break
        replies = data.get("data", {}).get("replies") or []
        if not replies:
            break
        for reply in replies:
            mid = reply["member"]["mid"]
            name = reply["member"]["uname"]
            users[int(mid)] = name
            # 也收集子评论
            sub_replies = reply.get("replies") or []
            for sr in sub_replies:
                smid = sr["member"]["mid"]
                sname = sr["member"]["uname"]
                users[int(smid)] = sname
        pn += 1
        time.sleep(0.3)
    return users


# ---------- 点赞列表 ----------

def fetch_like_users(sess: requests.Session, dynamic_id: str) -> dict[int, str]:
    """获取点赞用户"""
    users: dict[int, str] = {}
    pn = 1
    while True:
        params = {"dynamic_id": dynamic_id, "pn": pn, "ps": 50}
        r = sess.get(API_LIKE_LIST, params=params)
        data = r.json()
        if data.get("code") != 0:
            print(f"  [警告] 获取点赞列表失败: {data.get('message')}")
            break
        item_likes = data.get("data", {}).get("item_likes") or []
        if not item_likes:
            break
        for like in item_likes:
            mid = like.get("uid")
            name = like.get("uname", "")
            if mid:
                users[int(mid)] = name
        if not data.get("data", {}).get("has_more"):
            break
        pn += 1
        time.sleep(0.3)
    return users


# ============================================================
# 抽奖逻辑
# ============================================================

def run_lottery(
    dynamic_url: str,
    conditions: list[str],
    count: int = 1,
    sessdata: Optional[str] = None,
    exclude_uids: Optional[list[int]] = None,
):
    dynamic_id = parse_dynamic_id(dynamic_url)
    sess = make_session(sessdata)
    exclude = set(exclude_uids or [])

    print(f"\n{'='*50}")
    print(f"  Bilibili 动态抽奖工具")
    print(f"{'='*50}")
    print(f"  动态 ID : {dynamic_id}")
    print(f"  参与条件: {' + '.join(conditions)}")
    print(f"  抽取人数: {count}")
    print(f"{'='*50}\n")

    # 获取动态详情
    print("[1/2] 获取动态详情...")
    detail = get_dynamic_detail(sess, dynamic_id)
    author_name = detail.get("modules", {}).get("module_author", {}).get("name", "未知")
    author_mid = detail.get("modules", {}).get("module_author", {}).get("mid", 0)
    print(f"  动态作者: {author_name} (UID: {author_mid})")

    # 获取 oid 用于评论接口
    basic = detail.get("basic", {})
    comment_id_str = basic.get("comment_id_str", dynamic_id)
    comment_type = basic.get("comment_type", 17)

    # 排除动态作者
    exclude.add(int(author_mid))

    # 收集各条件的用户
    print("\n[2/2] 收集参与用户...")
    condition_users: dict[str, dict[int, str]] = {}

    if "转发" in conditions:
        print("  - 获取转发用户...")
        condition_users["转发"] = fetch_repost_users(sess, dynamic_id)
        print(f"    找到 {len(condition_users['转发'])} 人")

    if "评论" in conditions:
        print("  - 获取评论用户...")
        condition_users["评论"] = fetch_reply_users(sess, dynamic_id, comment_id_str, comment_type)
        print(f"    找到 {len(condition_users['评论'])} 人")

    if "点赞" in conditions:
        print("  - 获取点赞用户...")
        condition_users["点赞"] = fetch_like_users(sess, dynamic_id)
        print(f"    找到 {len(condition_users['点赞'])} 人")

    if not condition_users:
        print("\n[错误] 未指定任何有效条件!")
        sys.exit(1)

    # 取交集: 必须满足所有条件
    eligible_sets = [set(u.keys()) for u in condition_users.values()]
    eligible_uids = eligible_sets[0]
    for s in eligible_sets[1:]:
        eligible_uids &= s

    # 排除黑名单
    eligible_uids -= exclude

    # 合并用户名（从任一条件取）
    all_users: dict[int, str] = {}
    for u in condition_users.values():
        all_users.update(u)

    eligible = [(uid, all_users.get(uid, "未知")) for uid in eligible_uids]

    print(f"\n  满足所有条件的用户: {len(eligible)} 人")

    if len(eligible) == 0:
        print("\n[结果] 没有用户满足所有条件，无法抽奖。")
        return

    if len(eligible) < count:
        print(f"\n[警告] 满足条件的用户不足 {count} 人，将抽取全部 {len(eligible)} 人。")
        count = len(eligible)

    # 抽奖
    print(f"\n{'='*50}")
    print("  正在抽奖...")
    print(f"{'='*50}\n")

    winners = random.sample(eligible, count)

    for i, (uid, name) in enumerate(winners, 1):
        satisfied = [c for c, u in condition_users.items() if uid in u]
        print(f"  🎉 第 {i} 位中奖用户:")
        print(f"     用户名 : {name}")
        print(f"     UID    : {uid}")
        print(f"     主页   : https://space.bilibili.com/{uid}")
        print(f"     满足条件: {', '.join(satisfied)}")
        print()

    print(f"{'='*50}")
    print("  抽奖完成!")
    print(f"{'='*50}\n")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bilibili 动态抽奖工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python luck_draw.py https://t.bilibili.com/123456 --conditions 转发 评论
  python luck_draw.py 123456 --conditions 点赞 --count 3
  python luck_draw.py 123456 --conditions 转发 评论 点赞 --sessdata "your_sessdata"
        """,
    )
    parser.add_argument("dynamic", help="Bilibili 动态 URL 或 ID")
    parser.add_argument(
        "--conditions", "-c",
        nargs="+",
        choices=["转发", "评论", "点赞"],
        required=True,
        help="参与条件（可多选，用户需满足所有条件）",
    )
    parser.add_argument("--count", "-n", type=int, default=1, help="抽取人数（默认 1）")
    parser.add_argument("--sessdata", "-s", help="B站 SESSDATA cookie（可选，提升稳定性）")
    parser.add_argument(
        "--exclude", "-e",
        nargs="*",
        type=int,
        default=[],
        help="排除的 UID 列表",
    )

    args = parser.parse_args()
    run_lottery(
        dynamic_url=args.dynamic,
        conditions=args.conditions,
        count=args.count,
        sessdata=args.sessdata,
        exclude_uids=args.exclude,
    )


if __name__ == "__main__":
    main()
