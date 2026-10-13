#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站 UP主动态监控：抓取指定 UP 的最新动态，发现新动态就通过 Bark 推送到 iPhone。
纯标准库实现，无需 pip install。
配置通过环境变量传入（见 README）。
"""

import os
import sys
import hmac
import json
import time
import hashlib
import urllib.parse
import urllib.request

# ============ 配置（从环境变量读取）============
UID = os.environ.get("BILI_UID", "470672214")          # 要监控的 UP 主 UID
BARK_KEY = os.environ.get("BARK_KEY", "").strip()       # Bark 的推送 key（必填）
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app").rstrip("/")
SESSDATA = os.environ.get("BILI_SESSDATA", "").strip()  # 可选：登录 cookie
# 完整浏览器 Cookie（机房 IP 过 412 的关键；GitHub 必填）。填了它就以它为准。
FULL_COOKIE = os.environ.get("BILI_COOKIE", "").strip()
STATE_FILE = os.environ.get("STATE_FILE", "seen.json")  # 记录已推送过的动态 ID

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# WBI 签名用的乱序表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


_BUVID_COOKIE = ""  # 运行时自动填充


def _cookies():
    # 填了完整 Cookie 就直接用它（里面已含 buvid3 等被 B站认证过的值）
    if FULL_COOKIE:
        return FULL_COOKIE
    c = []
    if _BUVID_COOKIE:
        c.append(_BUVID_COOKIE)
    if SESSDATA:
        c.append("SESSDATA=" + SESSDATA)
    return "; ".join(c)


def http_get(url, headers=None, timeout=15):
    h = {"User-Agent": UA,
         "Referer": "https://space.bilibili.com/%s/dynamic" % UID}
    if headers:
        h.update(headers)
    ck = _cookies()
    if ck:
        h["Cookie"] = ck
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def http_post(url, json_body=None, timeout=15):
    h = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    ck = _cookies()
    if ck:
        h["Cookie"] = ck
    data = None
    if json_body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def ensure_buvid():
    """领取并激活 buvid cookie。动态接口有软风控：不激活会返回 code=0 但 items 为空。"""
    global _BUVID_COOKIE
    if FULL_COOKIE:
        return  # 用完整 Cookie 时不需要自己领 buvid
    if _BUVID_COOKIE:
        return
    try:
        raw = http_get("https://api.bilibili.com/x/frontend/finger/spi")
        data = json.loads(raw)["data"]
        _BUVID_COOKIE = "buvid3=%s; buvid4=%s" % (data["b_3"], data["b_4"])
    except Exception as e:
        print("[警告] 领取 buvid 失败，可能被风控:", repr(e))
        return
    # 领取 bili_ticket 以“激活”buvid，否则动态列表为空
    try:
        ts = int(time.time())
        hexsign = hmac.new(b"XgwSnGZ1p", ("ts%d" % ts).encode(),
                           hashlib.sha256).hexdigest()
        turl = ("https://api.bilibili.com/bapis/"
                "bilibili.api.ticket.v1.Ticket/GenWebTicket"
                "?key_id=ec02&hexsign=%s&context[ts]=%d&csrf=" % (hexsign, ts))
        t = json.loads(http_post(turl, json_body={}))
        ticket = (t.get("data") or {}).get("ticket", "")
        if ticket:
            _BUVID_COOKIE += "; bili_ticket=" + ticket
    except Exception as e:
        print("[警告] 领取 bili_ticket 失败，动态可能为空:", repr(e))


def get_wbi_keys():
    """从 nav 接口拿到 img_key / sub_key。"""
    raw = http_get("https://api.bilibili.com/x/web-interface/nav")
    data = json.loads(raw)
    wbi = data["data"]["wbi_img"]
    img = wbi["img_url"].rsplit("/", 1)[-1].split(".")[0]
    sub = wbi["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    return img, sub


def get_mixin_key(img_key, sub_key):
    s = img_key + sub_key
    return "".join(s[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def enc_wbi(params, img_key, sub_key):
    """给参数加上 WBI 签名（wts + w_rid）。"""
    mixin = get_mixin_key(img_key, sub_key)
    params = dict(params)
    params["wts"] = int(time.time())
    params = {k: params[k] for k in sorted(params)}
    # 过滤特殊字符
    for k, v in params.items():
        params[k] = "".join(c for c in str(v) if c not in "!'()*")
    query = urllib.parse.urlencode(params)
    w_rid = hashlib.md5((query + mixin).encode()).hexdigest()
    params["w_rid"] = w_rid
    return urllib.parse.urlencode(params)


def _fetch_once():
    img_key, sub_key = get_wbi_keys()
    params = {
        "offset": "",
        "host_mid": UID,
        "timezone_offset": -480,
        "platform": "web",
        "features": "itemOpusStyle",
    }
    qs = enc_wbi(params, img_key, sub_key)
    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?" + qs
    data = json.loads(http_get(url))
    code = data.get("code")
    if code != 0:
        # -352/-412 等为风控码，可重试
        raise RuntimeError("接口返回码 %s: %s" % (code, data.get("message")))
    return (data.get("data") or {}).get("items") or []


def fetch_dynamics():
    """拉取该 UP 主的动态列表，返回 (up名, [(id, 摘要, 链接), ...])。带重试应对风控。"""
    global _BUVID_COOKIE
    items = []
    last_err = None
    for attempt in range(4):
        _BUVID_COOKIE = ""      # 每次重试换一套新 buvid
        ensure_buvid()
        try:
            items = _fetch_once()
            if items:
                break
            last_err = "返回空列表（软风控）"
        except Exception as e:
            last_err = repr(e)
        if attempt < 3:
            time.sleep(3 + attempt * 3)
    if not items:
        raise RuntimeError("多次重试仍失败：%s" % last_err)
    result = []
    for it in items:
        # 跳过置顶动态，避免每次都当成"新"的
        modules = it.get("modules") or {}
        module_tag = modules.get("module_tag") or {}
        if module_tag.get("text") == "置顶":
            continue
        did = it.get("id_str")
        if not did:
            continue
        text = extract_text(it)
        link = "https://t.bilibili.com/" + did
        result.append((did, text, link))
    up_name = ""
    if items:
        m0 = items[0].get("modules") or {}
        up_name = (m0.get("module_author") or {}).get("name", "")
    return up_name, result


def extract_text(item):
    """从动态里提取一段可读文字作为推送内容。"""
    modules = item.get("modules") or {}
    dyn = modules.get("module_dynamic") or {}
    # 纯文字 / 图文
    desc = dyn.get("desc") or {}
    if desc.get("text"):
        return desc["text"][:100]
    # 视频等带 major
    major = dyn.get("major") or {}
    if major.get("type") == "MAJOR_TYPE_ARCHIVE":
        arc = major.get("archive", {})
        return "【视频】" + arc.get("title", "")[:80]
    if major.get("type") == "MAJOR_TYPE_OPUS":
        opus = major.get("opus", {})
        title = opus.get("title") or ""
        summary = (opus.get("summary", {}) or {}).get("text", "")
        return (title + " " + summary).strip()[:100]
    if major.get("type") == "MAJOR_TYPE_ARTICLE":
        art = major.get("article", {})
        return "【专栏】" + art.get("title", "")[:80]
    return "发布了新动态"


def load_seen():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    # 只保留最近 100 条，避免文件无限增长
    data = list(seen)[-100:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)


def push_bark(title, body, jump_url):
    """推送成功返回 True，失败返回 False（失败的动态不标记已读，下轮重试）。"""
    if not BARK_KEY:
        print("[警告] 未配置 BARK_KEY，跳过推送。内容：", title, body)
        return False
    payload = {
        "title": title,
        "body": body,
        "url": jump_url,
        "group": "B站动态",
        "sound": "glass",
    }
    url = "%s/%s" % (BARK_SERVER, BARK_KEY)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[Bark]", resp.read().decode("utf-8")[:120])
        return True
    except Exception as e:
        print("[Bark 推送失败]", repr(e))
        return False


def main():
    first_run = not os.path.exists(STATE_FILE)
    seen = load_seen()
    up_name, dynamics = fetch_dynamics()
    if not dynamics:
        print("没有抓到动态，可能被风控或接口变化。")
        return

    current_ids = [d[0] for d in dynamics]
    new_items = [d for d in dynamics if d[0] not in seen]

    if first_run:
        # 首次运行只记录，不推送历史动态，避免一次性刷屏
        for did in current_ids:
            seen.add(did)
        save_seen(seen)
        print("首次运行，已记录 %d 条现有动态，之后有新动态才推送。" % len(current_ids))
        return

    if not new_items:
        print("无新动态。当前共 %d 条，均已推送过。" % len(current_ids))
        return

    # 新的在前，按时间顺序推送（旧->新）
    pushed = 0
    for did, text, link in reversed(new_items):
        title = (up_name or "关注的UP") + " 发新动态了"
        print("推送新动态:", did, text[:40])
        if push_bark(title, text, link):
            seen.add(did)   # 只有推送成功才标记已读
            pushed += 1
        time.sleep(1)

    save_seen(seen)
    print("本次推送 %d/%d 条新动态。" % (pushed, len(new_items)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("运行出错:", repr(e))
        sys.exit(1)
