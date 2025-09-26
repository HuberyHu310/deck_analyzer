#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ACE SPEC 專用爬蟲（瀏覽器版，精簡可讀）

流程（印出每一步）：
 1) 開啟瀏覽器並進入搜尋頁
 2) 在搜尋欄位輸入關鍵字（預設：ACE SPEC）
 3) 按下搜尋按鈕
 4) 在搜尋結果頁逐一點擊卡片（a#card-show-idX），抓取詳情頁 h1 名稱與 URL，只取前 N 筆（預設 5）

輸出：CSV（UTF-8 with BOM）、JSON（ensure_ascii=False）到 output/
參數：--keyword, --pages, --limit, --headless, --out, --format
相依：selenium, webdriver-manager, beautifulsoup4（僅用於保險，不依賴解析）
"""

import os
import sys
import csv
import json
import time
import argparse
import re
from typing import List, Dict, Tuple
from urllib.parse import urljoin

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- IO helpers ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IMG_SUBDIR = "ace_images"
IMG_DIR = os.path.join(OUTPUT_DIR, IMG_SUBDIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)


def write_csv(path: str, rows: List[Dict[str, str]]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name_jp", "type", "url", "image_url", "local_image"])
        for r in rows:
            w.writerow([
                r.get("name_jp", ""),
                r.get("type", ""),
                r.get("url", ""),
                r.get("image_url", ""),
                r.get("local_image", ""),
            ])


def write_json(path: str, rows: List[Dict[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


# ---- Browser flow ----
def browser_collect_cards(
    keyword: str,
    limit: int,
    max_pages: int,
    headless: bool,
    debug_stop_after_step2: bool = False,
    keep_browser_open: bool = False,
) -> List[Dict[str, str]]:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.keys import Keys

    opts = Options()
    if headless:
        # 相容性較好的 headless
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1200,1000")
    # 降低 GPU 噪音與失敗機率
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("--use-angle=swiftshader")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    BASE_SEARCH = "https://www.pokemon-card.com/card-search/"
    header_btn_css = "#header_search_tab_cont0 > form > div.SearchTextForm > button"

    rows: List[Dict[str, str]] = []
    opened = 0

    def try_get_image_url() -> str:
        # Prefer real card image; only accept og:image when it points to card_images
        try:
            meta = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
            img = (meta.get_attribute("content") or "").strip()
            if img and "/assets/images/card_images/" in img:
                return urljoin(driver.current_url, img)
        except Exception:
            pass
        # Common card image selectors on pokemon-card.com
        candidates = [
            "img[src*='/assets/images/card_images/']",
            "img.fit",
            ".CardImage img",
            ".image img",
            "img.p-card-img",
        ]
        for sel in candidates:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                src = (el.get_attribute("src") or el.get_attribute("data-src") or "").strip()
                if src:
                    return urljoin(driver.current_url, src)
            except Exception:
                continue
        return ""

    def try_get_h1_name() -> str:
        try:
            h1 = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.Heading1.mt20")))
            return (h1.text or "").strip()
        except Exception:
            try:
                h1b = driver.find_element(By.TAG_NAME, "h1")
                return (h1b.text or "").strip()
            except Exception:
                return ""

    def _normalize_type_label(text: str) -> str:
        t = (text or "").strip().lower()
        # Japanese labels commonly appearing on site
        jp_map = [
            ("グッズ", "item"),
            ("サポート", "supporter"),
            ("スタジアム", "stadium"),
            ("ポケモンのどうぐ", "tool"),
            ("どうぐ", "tool"),
            ("特殊エネルギー", "special_energy"),
            ("基本エネルギー", "energy"),
            ("エネルギー", "energy"),
            ("ポケモン", "pokemon"),
            ("ace spec", "ace_spec"),
        ]
        for k, v in jp_map:
            if k.lower() in t:
                return v
        if "support" in t:
            return "supporter"
        if "stadium" in t:
            return "stadium"
        if "tool" in t:
            return "tool"
        if "special" in t and "energy" in t:
            return "special_energy"
        if "energy" in t:
            return "energy"
        if "pokemon" in t:
            return "pokemon"
        if "item" in t or "goods" in t:
            return "item"
        if "ace spec" in t:
            return "ace_spec"
        return ""

    def try_get_card_type() -> str:
        # Heuristics over various potential containers
        containers = [
            ".TagList", ".CardTag", ".CardLabel", ".Label", ".Tag", ".type", ".cardType",
        ]
        for sel in containers:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    t = _normalize_type_label(el.text)
                    if t:
                        return t
                except Exception:
                    continue
        # Label field like "カードの種類"
        try:
            lab = driver.find_element(By.XPATH, "//*[contains(text(),'カードの種類')]")
            try:
                sib = lab.find_element(By.XPATH, "following::*[1]")
                t = _normalize_type_label(sib.text)
                if t:
                    return t
            except Exception:
                pass
        except Exception:
            pass
        # Fallback: scan whole body
        try:
            all_txt = driver.find_element(By.TAG_NAME, 'body').text
            return _normalize_type_label(all_txt)
        except Exception:
            return ""

    # 跨 context 嘗試填入關鍵字（頂層 + 所有 iframe）
    def _fill_all_contexts_fill(keyword_text: str) -> bool:
        from selenium.webdriver.common.by import By as _By
        from selenium.webdriver.common.keys import Keys as _Keys
        def fill_in_context() -> bool:
            selectors = [
                "input.KSTextInput_text[name='keyword']",
                "#header_search_tab_cont0 input.KSTextInput_text[name='keyword']",
                "#header_search_tab_cont0 input[type='text'][name='keyword']",
                "input[name='keyword']",
            ]
            for sel in selectors:
                try:
                    elems = driver.find_elements(_By.CSS_SELECTOR, sel)
                except Exception:
                    elems = []
                for el in elems:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        try:
                            el.click()
                        except Exception:
                            pass
                        try:
                            el.send_keys(_Keys.CONTROL, 'a'); el.send_keys(_Keys.DELETE); el.send_keys(keyword_text)
                        except Exception:
                            try:
                                driver.execute_script(
                                    "arguments[0].focus(); arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                                    el, keyword_text
                                )
                            except Exception:
                                pass
                        try:
                            val = driver.execute_script("return arguments[0].value;", el)
                            print(f"[debug] current input value via {sel}: {val}")
                            if (val or '').strip() == (keyword_text or '').strip():
                                return True
                        except Exception:
                            pass
                    except Exception:
                        continue
            return False
        # 頂層
        if fill_in_context():
            return True
        # iframes
        try:
            iframes = driver.find_elements(_By.TAG_NAME, 'iframe')
        except Exception:
            iframes = []
        for i, fr in enumerate(iframes):
            try:
                driver.switch_to.frame(fr)
                print(f"[debug] switched into iframe #{i}")
                if fill_in_context():
                    driver.switch_to.default_content()
                    return True
            except Exception:
                pass
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
        return False
    try:
        # Step 1
        print(f"[step 1/4] 開啟瀏覽器並進入搜尋頁：{BASE_SEARCH}")
        driver.get(BASE_SEARCH)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        print("[step 1/4] 完成")

        # Step 2 - 點擊展開後輸入
        print(f"[step 2/4] 在搜尋欄輸入關鍵字：{keyword}")
        try:
            driver.find_element(By.CSS_SELECTOR, header_btn_css).click()
        except Exception:
            pass
        # 鎖定輸入框
        input_el = None
        try:
            # 針對你提供的元件：input.KSTextInput_text[name='keyword']
            input_el = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input.KSTextInput_text[name='keyword']"))
            )
        except Exception:
            try:
                input_el = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.NAME, "keyword"))
                )
            except Exception:
                input_el = None
        if input_el is None:
            # shadow DOM/backups
            js_find = """
            const tests = [
              () => document.querySelector('#header_search_tab_cont0 input.KSTextInput_text[name=keyword]'),
              () => document.querySelector('#header_search_tab_cont0 input[type=search]'),
              () => document.querySelector('#header_search_tab_cont0 input[type=text]'),
              () => document.querySelector('input[name=keyword]'),
              () => document.querySelector('ks-textinput')?.shadowRoot?.querySelector('input'),
              () => document.querySelector('[id*="KSTextInput"] input'),
              () => document.querySelector('[class*="KSTextInput"] input'),
            ];
            for (const t of tests) { try { const el = t(); if (el) return el; } catch(e){} }
            return null;
            """
            try:
                input_el = driver.execute_script(js_find)
            except Exception:
                input_el = None
        # 輸入文字（JS 優先）
        if input_el is not None:
            try:
                # 讓輸入框進入視窗中央並點擊聚焦
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", input_el)
                    input_el.click()
                except Exception:
                    pass
                # 以 JS 設值並派發多種事件，涵蓋組字/輸入法情境
                driver.execute_script(
                    "arguments[0].focus();"
                    "arguments[0].value=arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('compositionend',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));"
                    "arguments[0].dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                    input_el, keyword,
                )
            except Exception:
                try:
                    input_el.clear(); input_el.send_keys(keyword)
                except Exception:
                    pass
            # 讀回目前輸入框值，確認是否填入成功
            try:
                cur_val = driver.execute_script("return arguments[0].value;", input_el)
                print(f"[debug] current input value: {cur_val}")
                if (cur_val or "").strip() != (keyword or "").strip():
                    print("[warn] 欄位值與預期不符，改用 send_keys 再嘗試一次…")
                    try:
                        input_el.clear(); input_el.send_keys(keyword)
                        cur_val2 = driver.execute_script("return arguments[0].value;", input_el)
                        print(f"[debug] current input value (retry): {cur_val2}")
                    except Exception:
                        pass
            except Exception:
                pass
        print("[step 2/4] 完成")

        # Debug: 停在步驟 2，且不關閉瀏覽器
        if debug_stop_after_step2:
            print("[debug] 依要求在步驟 2 停止。瀏覽器保持開啟，未送出搜尋。")
            return []

        # Step 3 - 送出搜尋
        print("[step 3/4] 按下搜尋按鈕")
        submitted = False
        try:
            driver.find_element(By.CSS_SELECTOR, header_btn_css).click(); submitted = True
        except Exception:
            try:
                driver.find_element(By.NAME, "SearchButton").click(); submitted = True
            except Exception:
                # 後援：直接 submit 關聯表單
                try:
                    js_submit = '''
var inp = document.querySelector("input.KSTextInput_text[name='keyword']") ||
          document.querySelector("#header_search_tab_cont0 input[name='keyword']") ||
          document.querySelector("input[name='keyword']");
if (inp) {
  var f = inp.form || inp.closest('form');
  if (f) { f.submit(); return true; }
}
return false;
'''
                    ok = driver.execute_script(js_submit)
                    submitted = bool(ok)
                    if submitted:
                        print('[debug] submitted via form.submit()')
                except Exception:
                    pass
        print("[step 3/4] 完成" if submitted else "[warn] 搜尋送出可能未成功，將嘗試直接解析頁面")

        # Step 4 - 解析結果（最多 limit 張）
        print(f"[step 4/4] 解析搜尋結果（最多 {limit} 張）")
        # 保障：若上述定位未成功，跨 context 全面嘗試一次
        try:
            ok_fill = _fill_all_contexts_fill(keyword)
            print(f"[debug] fill_all_contexts result: {ok_fill}")
        except Exception:
            pass

        def process_current_page() -> bool:
            nonlocal opened
            # 直接存在詳情連結的情況
            directs = driver.find_elements(By.CSS_SELECTOR, "a[href*='/card-search/details.php/card/']")
            for a in directs:
                href = a.get_attribute("href")
                if href and "/card-search/details.php/card/" in href:
                    # Open detail in a new tab to capture fields
                    root = driver.current_window_handle
                    handles_before = list(driver.window_handles)
                    new_handle = None
                    try:
                        driver.execute_script("window.open(arguments[0], '_blank');", href)
                        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(handles_before))
                        for h in driver.window_handles:
                            if h not in handles_before:
                                new_handle = h; break
                    except Exception:
                        new_handle = None
                    try:
                        if new_handle:
                            driver.switch_to.window(new_handle)
                        else:
                            driver.get(href)
                        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                        name = try_get_h1_name()
                        url = driver.current_url
                        image_url = try_get_image_url()
                        ctype = try_get_card_type()
                        rows.append({"name_jp": name, "type": ctype, "url": url, "image_url": image_url})
                        print(f"[h1] {name}")
                        print(f"[debug] direct link → url={url}")
                    finally:
                        try:
                            if new_handle:
                                driver.close()
                                driver.switch_to.window(root)
                        except Exception:
                            try:
                                driver.switch_to.window(root)
                            except Exception:
                                pass
                    if (limit and limit > 0) and len(rows) >= limit:
                        return True

            # 逐一點 idX
            cards = driver.find_elements(By.CSS_SELECTOR, "a[id^='card-show-id']")
            for el in cards:
                if (limit and limit > 0) and len(rows) >= limit:
                    return True
                rid = el.get_attribute("id") or "card-show-id?"
                root = driver.current_window_handle
                handles_before = list(driver.window_handles)

                # 嘗試點擊
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    try:
                        el.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", el)
                except Exception:
                    continue

                # 新開分頁？
                new_handle = None
                try:
                    WebDriverWait(driver, 3).until(lambda d: len(d.window_handles) > len(handles_before))
                    handles_after = list(driver.window_handles)
                    for h in handles_after:
                        if h not in handles_before:
                            new_handle = h; break
                except Exception:
                    new_handle = None

                def capture_current() -> None:
                    name = try_get_h1_name()
                    url = driver.current_url
                    image_url = try_get_image_url()
                    ctype = try_get_card_type()
                    rows.append({"name_jp": name, "type": ctype, "url": url, "image_url": image_url})
                    print(f"[h1] {name}")
                    print(f"[debug] opened {rid} → url={url}")

                # 讀取 + 關閉/返回
                try:
                    if new_handle:
                        driver.switch_to.window(new_handle)
                        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                        capture_current()
                        try:
                            driver.close()
                        except Exception:
                            pass
                        driver.switch_to.window(root)
                        WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "a[id^='card-show-id']"))
                    else:
                        try:
                            WebDriverWait(driver, 5).until(lambda d: "/card-search/details.php/card/" in d.current_url)
                        except Exception:
                            pass
                        capture_current()
                        driver.back()
                        WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "a[id^='card-show-id']"))
                except Exception:
                    try:
                        driver.switch_to.window(root)
                    except Exception:
                        pass

                opened += 1
                if (limit and limit > 0) and len(rows) >= limit:
                    return True
            return False

        page = 1
        while page <= max_pages:
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            done = process_current_page()
            if done:
                break
            # 下一頁
            went_next = False
            try:
                driver.find_element(By.CSS_SELECTOR, "a[rel='next']").click(); went_next = True
            except Exception:
                try:
                    driver.find_element(By.XPATH, "//a[contains(.,'次')] | //button[contains(.,'次')]").click(); went_next = True
                except Exception:
                    pass
            if not went_next:
                break
            page += 1

        print(f"[summary] 已收集 {len(rows)} 張（上限 {limit}）")
        return rows

    finally:
        if not (debug_stop_after_step2 and keep_browser_open):
            driver.quit()


# ---- CLI ----
def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ACE SPEC 爬蟲（瀏覽器版）")
    p.add_argument("--keyword", default="ACE SPEC", help="搜尋關鍵字")
    p.add_argument("--pages", dest="max_pages", type=int, default=10, help="最多翻頁數")
    p.add_argument("--limit", type=int, default=0, help="最多點開卡片數（0=不限制）")
    p.add_argument("--headless", action="store_true", help="隱藏瀏覽器視窗")
    # Debug 選項：在步驟 2 停住，且保持瀏覽器開啟
    p.add_argument("--debug-stop-after-step2", action="store_true", help="在步驟 2（輸入關鍵字）後停止")
    p.add_argument("--keep-browser-open", action="store_true", help="與 debug 停止搭配，保持瀏覽器不關閉")
    p.add_argument("--out", dest="out_base", default=os.path.join(OUTPUT_DIR, "ace_spec_catalog"), help="輸出檔名前綴")
    p.add_argument("--format", dest="fmt", choices=["csv", "json", "both"], default="both", help="輸出格式")
    return p.parse_args(argv)


def main(argv: List[str]):
    args = parse_args(argv)
    # 印出當前控制參數，便於 DEBUG
    print("[config] keyword=", args.keyword)
    print("[config] pages=", args.max_pages)
    print("[config] limit=", args.limit)
    print("[config] headless=", args.headless)
    print("[config] debug_stop_after_step2=", getattr(args, 'debug_stop_after_step2', False))
    print("[config] keep_browser_open=", getattr(args, 'keep_browser_open', False))
    print("[config] out_base=", args.out_base)
    print("[config] format=", args.fmt)
    rows = browser_collect_cards(
        keyword=args.keyword,
        limit=args.limit,
        max_pages=args.max_pages,
        headless=args.headless,
        debug_stop_after_step2=args.debug_stop_after_step2,
        keep_browser_open=args.keep_browser_open,
    )
    # Ensure each row includes image_url by fetching detail page if missing
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        requests = None
        BeautifulSoup = None
    if requests is not None and BeautifulSoup is not None:
        sess = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
        def map_type_text(txt: str) -> str:
            t = (txt or "").lower()
            pairs = [
                ("グッズ", "item"), ("サポート", "supporter"), ("スタジアム", "stadium"),
                ("ポケモンのどうぐ", "tool"), ("どうぐ", "tool"), ("特殊エネルギー", "special_energy"),
                ("基本エネルギー", "energy"), ("エネルギー", "energy"), ("ポケモン", "pokemon"),
                ("ace spec", "ace_spec"),
            ]
            for k,v in pairs:
                if k.lower() in t:
                    return v
            if "special" in t and "energy" in t:
                return "special_energy"
            if "energy" in t:
                return "energy"
            if "support" in t:
                return "supporter"
            if "stadium" in t:
                return "stadium"
            if "tool" in t:
                return "tool"
            if "pokemon" in t:
                return "pokemon"
            if "item" in t or "goods" in t:
                return "item"
            return ""
        for r in rows:
            # Ensure image_url
            if not r.get("image_url") and r.get("url"):
                try:
                    resp = sess.get(r["url"], headers=headers, timeout=15)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    img = ""
                    og = soup.select_one("meta[property='og:image']")
                    if og and og.get("content"):
                        ogc = og["content"].strip()
                        if "/assets/images/card_images/" in ogc:
                            img = ogc
                    if not img:
                        el = soup.select_one("img[src*='/assets/images/card_images/']")
                        if el and (el.get("src") or el.get("data-src")):
                            img = (el.get("src") or el.get("data-src")).strip()
                    if img:
                        r["image_url"] = urljoin(r["url"], img)
                except Exception:
                    pass
            # Ensure type
            if not r.get("type") and r.get("url"):
                try:
                    resp = sess.get(r["url"], headers=headers, timeout=15)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    txt = soup.get_text(" ", strip=True)
                    tp = map_type_text(txt)
                    if tp:
                        r["type"] = tp
                except Exception:
                    pass
        # Download images to output/ace_images and set local_image
        for r in rows:
            img_url = r.get("image_url")
            if not img_url:
                continue
            # derive filename from card id or name
            m = re.search(r"/card/(\d+)", r.get("url", ""))
            base_name = (m.group(1) if m else (r.get("name_jp") or "card")).strip()
            base_name = re.sub(r"[^\w\-\u4e00-\u9fa5\u3040-\u30ff\u3000]+", "_", base_name)
            ext = os.path.splitext(img_url.split('?')[0])[1] or ".jpg"
            fname = f"{base_name}{ext}"
            fpath = os.path.join(IMG_DIR, fname)
            try:
                if not os.path.exists(fpath):
                    with sess.get(img_url, headers=headers, timeout=20, stream=True) as resp:
                        resp.raise_for_status()
                        with open(fpath, 'wb') as out:
                            for chunk in resp.iter_content(chunk_size=8192):
                                if chunk:
                                    out.write(chunk)
                rel = os.path.join("output", IMG_SUBDIR, fname)
                r["local_image"] = rel.replace('\\', '/')
            except Exception:
                pass
    base = args.out_base
    if args.fmt in ("csv", "both"):
        csv_path = base + ".csv"
        write_csv(csv_path, rows)
        print(f"CSV 已輸出：{csv_path}")
    if args.fmt in ("json", "both"):
        json_path = base + ".json"
        write_json(json_path, rows)
        print(f"JSON 已輸出：{json_path}")


if __name__ == "__main__":
    main(sys.argv[1:])

