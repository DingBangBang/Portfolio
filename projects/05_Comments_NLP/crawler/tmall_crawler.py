# -*- coding: utf-8 -*-
"""天猫评论爬虫（重写原脚本的采集部分）。

跟老脚本的区别只有三点，别的没动：
1. cookie / 代理 / 翻页数挪到 config.yaml（原来写死在代码里，一提交就泄露）；
2. print 换成 logging；
3. sleep 从固定 10 秒改成 3~6 秒随机 —— 固定间隔太规律，反而更容易被识别。

原来的正则提取逻辑照抄，能跑通的东西就不改了。
"""

import csv
import logging
import random
import re
import time
from pathlib import Path

import requests
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("tmall")

BASE_DIR = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0"


def load_config(path=None):
    cfg_path = Path(path or BASE_DIR / "config.yaml")
    if not cfg_path.exists():
        cfg_path = BASE_DIR / "config.example.yaml"
        log.warning("没找到 config.yaml，用示例配置（cookie 是空的，肯定爬不到）")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_url(cfg, page):
    c = cfg["crawler"]
    return (
        "https://rate.tmall.com/list_detail_rate.htm"
        "?itemId=%s&spuId=%s&sellerId=%s&order=3&currentPage=%d"
        "&append=0&content=1&tagId=&posi=&picture=&groupId="
        % (c["item_id"], c["spu_id"], c["seller_id"], page)
    )


def fetch_page(cfg, page, retries=2):
    """抓一页。失败就重试，还是失败就返回空串让上层跳过。

    注意：这里没做 cookie 失效的判断，表现就是拿到空数据。
    TODO 里写了要加，但一直没加，因为换 cookie 本身也就两分钟。
    """
    headers = {"user-agent": UA, "referer": "https://list.tmall.com/"}
    if cfg["crawler"].get("cookie"):
        headers["cookie"] = cfg["crawler"]["cookie"]
    proxies = {"http": cfg["crawler"]["proxy"]} if cfg["crawler"].get("proxy") else None

    for attempt in range(retries + 1):
        try:
            resp = requests.get(build_url(cfg, page), headers=headers, proxies=proxies, timeout=15)
            resp.encoding = "utf-8"
            if resp.text and "rateContent" in resp.text:
                return resp.text
            log.warning("第 %s 页没拿到评论内容（第 %s 次）", page, attempt + 1)
        except Exception as e:
            log.warning("第 %s 页请求失败：%s（第 %s 次）", page, e, attempt + 1)
        time.sleep(random.uniform(*cfg["crawler"]["delay_seconds"]))
    return ""


def parse(html):
    """正则捞字段。天猫返回的是一段 jsonp，直接当字符串处理最省事。

    四个列表长度一般一致；万一对不齐，zip 会按最短的截断，比直接崩掉好。
    """
    nicks = re.findall(r'"displayUserNick":"(.*?)"', html)
    skus = re.findall(r'"auctionSku":"(.*?)"', html)
    dates = re.findall(r'"rateDate":"(.*?)"', html)
    contents = re.findall(r'"rateContent":"(.*?)"', html)
    return [
        {"用户名": n, "购买规格": s, "评论时间": d, "评论内容": c}
        for n, s, d, c in zip(nicks, skus, dates, contents)
    ]


def crawl(cfg):
    rows = []
    c = cfg["crawler"]
    for page in range(int(c["start_page"]), int(c["start_page"]) + int(c["pages"])):
        log.info("爬第 %s 页", page)
        page_rows = parse(fetch_page(cfg, page))
        if not page_rows:
            log.warning("第 %s 页 0 条，可能是 cookie 过期或被限流", page)
        else:
            log.info("第 %s 页拿到 %s 条", page, len(page_rows))
            rows.extend(page_rows)
        # 随机 sleep，别太规律
        time.sleep(random.uniform(*c["delay_seconds"]))
    return rows


def save(rows, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "tmall_comments.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["用户名", "购买规格", "评论时间", "评论内容"])
        writer.writeheader()
        writer.writerows(rows)
    log.info("存了 %s 条到 %s", len(rows), path)


def main():
    cfg = load_config()
    if not cfg.get("crawler", {}).get("cookie"):
        raise SystemExit("config.yaml 里 crawler.cookie 是空的，先去浏览器复制一份")
    save(crawl(cfg), cfg.get("output_dir", "outputs"))


if __name__ == "__main__":
    main()
