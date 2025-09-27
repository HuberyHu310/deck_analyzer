"""
deck_analyzer_v1

重點說明：
- 透過設定常數（CATEGORIES、ACE_SPEC_LIST、Tunables）調整分析匯出。
- ACE SPEC 卡表僅依 ACE_SPEC_LIST 來源，建議以此維護內容。
- 支援以標準化名稱對照牌組資料與統計結果。
- 保留 Windows 主控台編碼處理，避免亂碼。
- 會輸出 CSV 報表並限制建議清單 60 筆。
"""
# 建檔時間（台北時區，UTC+8）：2025-09-25 20:42:32


# ---------------- Imports ----------------
# pip install: requests, beautifulsoup4, selenium, webdriver-manager
import os  # 檔案路徑與環境變數
import sys  # CLI 參數與系統狀態
import re  # 正則表示式工具
import csv  # 匯出 CSV 報表
import time  # 延遲與基礎計時
import json  # JSON 序列化與讀寫
import sqlite3  # SQLite 快取資料庫
import datetime  # 日期與時間處理
from typing import List, Dict, Tuple, Optional, Set  # 型別註記輔助

import requests  # 發送 HTTP 請求
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed  # 多程序與多執行線平行處理
from bs4 import BeautifulSoup, FeatureNotFound  # HTML ???????

from selenium import webdriver  # 啟動瀏覽器自動化
from selenium.webdriver.chrome.service import Service  # 管理 ChromeDriver 服務
from selenium.webdriver.chrome.options import Options  # 設定 Chrome 啟動選項
from selenium.webdriver.common.by import By  # DOM 元素定位方式
from selenium.webdriver.support.ui import WebDriverWait  # Selenium 顯式等待
from selenium.webdriver.support import expected_conditions as EC  # Selenium 等待條件
from webdriver_manager.chrome import ChromeDriverManager  # 自動安裝 ChromeDriver

# Runtime encoding hints for Windows consoles
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONENCODING', 'utf-8')

# ================== Constants & Categories ==================
# Default categories used for summary printing; matched against rec['type']
# Adjust if your pipeline uses different type labels.
CATEGORIES = [
    "pokemon",
    "goods",
    "tools",
    "supporter",
    "stadium",
    "energy",
    "special_energy",
    "ace_spec",
]
## (removed) print_top5_by_category / ace_official_url — not used in current flow



# BeautifulSoup ?????????? lxml???????? parser
_SOUP_PARSER: Optional[str] = None
_SOUP_FALLBACK_WARNED = False

def _make_soup(html: str) -> BeautifulSoup:
    """?? BeautifulSoup ????? lxml ????? html.parser?"""
    global _SOUP_PARSER, _SOUP_FALLBACK_WARNED
    candidates = ("lxml", "html.parser")
    if _SOUP_PARSER:
        try:
            return BeautifulSoup(html, _SOUP_PARSER)
        except FeatureNotFound:
            _SOUP_PARSER = None
    last_exc: Optional[Exception] = None
    for parser in candidates:
        try:
            soup = BeautifulSoup(html, parser)
            _SOUP_PARSER = parser
            if parser != "lxml" and not _SOUP_FALLBACK_WARNED:
                print("[warn] ??? lxml??? html.parser????? pip install lxml ????????")
                _SOUP_FALLBACK_WARNED = True
            return soup
        except FeatureNotFound as exc:
            last_exc = exc
    if last_exc:
        raise last_exc

# ---------------- ACE SPEC Catalog ----------------
# (名稱正規化後的顯示名, 官方URL；若未知則空字串)
ACE_SPEC_LIST = [
    ("きらめく結晶", "https://www.pokemon-card.com/card-search/details.php/card/46813"),
    ("つりざおMAX", "https://www.pokemon-card.com/card-search/details.php/card/46803"),
    ("アンフェアスタンプ", "https://www.pokemon-card.com/card-search/details.php/card/47870"),
    ("エネルギー転送PRO", "https://www.pokemon-card.com/card-search/details.php/card/46281"),
    ("サバイブギプス", "https://www.pokemon-card.com/card-search/details.php/card/45642"),
    ("シークレットボックス", "https://www.pokemon-card.com/card-search/details.php/card/45783"),
    ("スクランブルスイッチ", "https://www.pokemon-card.com/card-search/details.php/card/46435"),
    ("デラックスボム", "https://www.pokemon-card.com/card-search/details.php/card/46035"),
    ("デンジャラス光線", "https://www.pokemon-card.com/card-search/details.php/card/45929"),
    ("トレジャーガジェット", "https://www.pokemon-card.com/card-search/details.php/card/46807"),
    ("ニュートラルセンター", "https://www.pokemon-card.com/card-search/details.php/card/46845"),
    ("ハイパーアロマ", "https://www.pokemon-card.com/card-search/details.php/card/45641"),
    ("パーフェクトミキサー", "https://www.pokemon-card.com/card-search/details.php/card/46197"),
    ("ヒーローマント", "https://www.pokemon-card.com/card-search/details.php/card/48300"),
    ("プライムキャッチャー", "https://www.pokemon-card.com/card-search/details.php/card/48274"),
    ("プレシャスキャリー", "https://www.pokemon-card.com/card-search/details.php/card/46220"),
    ("ポケバイタルA", "https://www.pokemon-card.com/card-search/details.php/card/45930"),
    ("ポケモン回収サイクロン", "https://www.pokemon-card.com/card-search/details.php/card/46810"),
    ("マキシマムベルト", "https://www.pokemon-card.com/card-search/details.php/card/47890"),
    ("ミラクルインカム", "https://www.pokemon-card.com/card-search/details.php/card/46437"),
    ("メガトンブロアー", "https://www.pokemon-card.com/card-search/details.php/card/46285"),
    ("リッチエネルギー", "https://www.pokemon-card.com/card-search/details.php/card/46293"),
    ("レガシーエネルギー", "https://www.pokemon-card.com/card-search/details.php/card/47220"),
    ("偉大な大樹", "https://www.pokemon-card.com/card-search/details.php/card/46040"),
    ("希望のアミュレット", "https://www.pokemon-card.com/card-search/details.php/card/46438"),
    ("覚醒のドラム", "https://www.pokemon-card.com/card-search/details.php/card/45208"),
]

# Single source of truth is ACE_SPEC_LIST; derive URLs and mappings from it.
def _ace_short(u: str) -> str:
    """Return a short, stable ACE SPEC URL form for display/logging."""
    try:
        base = u.split('?', 1)[0]
        return base.replace('/regu/XY', '')
    except Exception:
        return u

def print_ace_spec_list_once():
    """Print ACE_SPEC_LIST once across the whole run (guarded by env var)."""
    if os.environ.get("ACE_PRINTED_ONCE") == "1":
        return
    try:
        print("\n=== ACE SPEC（由 ACE_SPEC_LIST 輸出） ===")
        print("ACE_SPEC_LIST_DETECTED = [")
        for name, u in ACE_SPEC_LIST:
            if not name or not u:
                continue
            safe_name = (name or '').replace('"', '\\"')
            print(f'    ("{safe_name}", "{_ace_short(u)}"),')
        print("]")
    except Exception as _e:
        print(f"[warn] 列印 ACE SPEC 偵測結果失敗：{_e}")
    os.environ["ACE_PRINTED_ONCE"] = "1"

def section_to_category(sec: Optional[str]) -> Optional[str]:
    """Map a section header (JP text from deck list) to an internal category key.
    Uses robust matching with Japanese literals (escaped) and strips count suffixes like （13）.
    """
    if not sec:
        return None
    s = (sec or "").strip()
    # Strip counts like "（13）" or "(13)" and extra spaces
    try:
        import re as _re
        s = _re.sub(r"[\u3000\s]*[（(].*?[）)]", "", s)
    except Exception:
        pass
    # Canonical keyword mapping
    jp_keywords = [
        ("\u30dd\u30b1\u30e2\u30f3\u306e\u3069\u3046\u3050", "tools"),      # ポケモンのどうぐ
        ("\u30b0\u30c3\u30ba", "goods"),                                      # グッズ
        ("\u30b5\u30dd\u30fc\u30c8", "supporter"),                           # サポート
        ("\u30b9\u30bf\u30b8\u30a2\u30e0", "stadium"),                       # スタジアム
        ("\u30a8\u30cd\u30eb\u30ae\u30fc", "energy"),                        # エネルギー
        ("\u7279\u6b8a\u30a8\u30cd\u30eb\u30ae\u30fc", "energy"),           # 特殊エネルギー
        ("\u30dd\u30b1\u30e2\u30f3", "pokemon"),                              # ポケモン
        ("ACE SPEC", "ace_spec"),
    ]
    for key, cat in jp_keywords:
        if key in s:
            return cat
    # Legacy mojibake placeholders fallback
    legacy_map = {
        "?????": "energy",
        "????": "supporter",
        "?????": "stadium",
        "???": "tools",
        "???": "goods",
        "????": "pokemon",
    }
    for key, cat in legacy_map.items():
        if key in s:
            return cat
    return None


# Derived URL list (single source from ACE_SPEC_LIST)

# ---------------- Tunables (moved up for readability) ----------------
# 可調整參數：資料來源（可複數）、範圍、ACE 規則、過濾條件
POKECABOOK_SOURCES: List[str] = [
    "https://pokecabook.com/archives/234601",
    #"https://pokecabook.com/archives/142393",
]
# 相容既有程式碼：提供第一個來源作為預設單一來源常數
POKECABOOK_URL: str = POKECABOOK_SOURCES[0] if POKECABOOK_SOURCES else ""
RECENT_DECKS_LIMIT = 10                  # 每個來源統計近 N 副；None = 全部
USE_ACE_SPEC = True                     # 是否選用 ACE SPEC（標準最多 1 張）
FORCE_ACE_SPEC_NAME: Optional[str] = None  # 固定選用某張（填日文名，例："コンピュータ通信"），None 不指定
FILTER_CARD_KEYWORDS: List[str] = []    # 僅統計含特定卡片（以卡名子字串比對，日文）；空陣列＝不過濾
FILTER_REQUIRE_ALL: bool = False        # True=必須全部符合；False=任一符合即可
# -*- coding: utf-8 -*-
#
# 說明重點：
# - 「完整同名」的判定會先做正規化：移除名稱中以各式括號包住的附加資訊（例：型號、號碼、標記、套牌符號等）。
#   支援的括號：() 、（） 、[] 、【】 、〈〉 、｟｠ 。
#   例如「○○（SV7a 123/190）」與「○○【I】」會被視為同一卡名「○○」。
# - 統計與建議牌組都以「正規化後的名稱」為 key 合併；同名不同 URL 會彙整在一起（輸出列出所有 URL）。
# - 建議牌組：非基本能量卡名最高 4 張（整體層級也檢查），ACE SPEC 恰好/最多 1 張（依參數）。
# - CSV 以 UTF-8 with BOM；URL 欄位為 Excel/Sheets 可點擊的 HYPERLINK 公式；多 URL 以「 | 」連接。
#
APP_VERSION = "15"
MAX_SOURCE_PROCS: int = 4                 # 多來源平行行程上限
IMG_DOWNLOAD_THREADS: int = 8             # 單一來源內圖片下載併發數

# 建議牌組：低使用率過濾門檻（可調整）
# - SUGGEST_MIN_USAGE_RATE: 一張卡至少出現在多少比例的牌組中才納入建議（0.0~1.0）
# - SUGGEST_MIN_DECKS: 至少出現於多少副牌組
SUGGEST_MIN_USAGE_RATE: float = 0.05      # 例：至少 5%
SUGGEST_MIN_DECKS: int = 1                # 例：至少 1 副

# 印出各卡平均每副張數清單的上限（0=不限制）
PRINT_CARD_AVG_LIMIT: int = 20

# 依日期篩選來源文章（以 Pokecabook 文章日期為主）
# 格式："YYYY-MM-DD" 或 None 表示不限制
ANALYZE_DATE_FROM: Optional[str] = None
ANALYZE_DATE_TO: Optional[str] = None


# 輸出檔案基準路徑（與程式同目錄）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs(OUTPUT_DIR, exist_ok=True)


BASE = "https://www.pokemon-card.com"

# ---------- SQLite 快取設定 ----------
CACHE_DB = "deck_cache.sqlite"

# 快取設定（整合）
CACHE_CFG = {
    "sqlite": True,            # 是否啟用 SQLite 牌組快取
    "url_name": True,          # 是否啟用 URL→官方卡名 的記憶體快取
    "refresh": True,          # True=強制重新抓取並覆蓋快取（不讀舊快取）
    "clear_on_disable": True,  # 關閉快取時是否清空既有快取
}

# 相容舊用法（單一來源：CACHE_CFG）
USE_SQLITE_CACHE: bool = CACHE_CFG["sqlite"]
USE_URL_NAME_CACHE: bool = CACHE_CFG["url_name"]
CLEAR_CACHE_ON_DISABLE: bool = CACHE_CFG["clear_on_disable"]
REFRESH_CACHE = CACHE_CFG["refresh"]

def init_cache():
    conn = sqlite3.connect(CACHE_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deck_cache (
            deck_id TEXT PRIMARY KEY,
            fetched_at REAL,
            cards_json TEXT,
            stats_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_cached_deck(deck_id: str):
    if REFRESH_CACHE or not USE_SQLITE_CACHE:
        return None
    try:
        conn = sqlite3.connect(CACHE_DB)
        cur = conn.cursor()
        cur.execute("SELECT cards_json, stats_json FROM deck_cache WHERE deck_id=?", (deck_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        cards = json.loads(row[0])
        stats = json.loads(row[1])
        # cards: list of [section, raw_name, cnt, url]
        # stats: dict
        return cards, stats
    except Exception:
        return None

def clear_cache_sqlite():
    """清除 SQLite 快取（優先刪除檔案；失敗則清空資料表）。"""
    try:
        if os.path.exists(CACHE_DB):
            os.remove(CACHE_DB)
            return True
    except Exception:
        pass
    try:
        conn = sqlite3.connect(CACHE_DB)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS deck_cache")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def save_cached_deck(deck_id: str, cards, stats):
    if 'USE_SQLITE_CACHE' in globals() and not USE_SQLITE_CACHE:
        return
    try:
        conn = sqlite3.connect(CACHE_DB)
        cur = conn.cursor()
        cur.execute("REPLACE INTO deck_cache (deck_id, fetched_at, cards_json, stats_json) VALUES (?,?,?,?)",
                    (deck_id, time.time(), json.dumps(cards, ensure_ascii=False), json.dumps(stats, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠ 快取寫入失敗 {deck_id}: {e}")


# ===== 手動同名合併（可依實際需要擴充） =====
# 1) 名稱別名：key = normalize_name(來源名) → value = normalize_name(目標名)
MANUAL_NAME_ALIASES = {
    # 範例： "○○（舊字體）": "○○", 會在 normalize 之後再替換到同一 key
    # "エーススペック（ACE SPEC）": "エーススペック",
}

# 2) 卡片ID群組：同一群組內的卡片（依官方 URL 中 /card/<ID>/）視為同一卡名統計
#    例如下方把 46189 與 47124 視為同一張卡：
MANUAL_CARDID_GROUPS = [
    ["46189", "47124"],   # 例：你回報的兩張同名卡
]
# 建立查找：card_id -> group_canonical_key（用第一個ID做 group key）
_MANUAL_ID2GROUP = {}
for grp in MANUAL_CARDID_GROUPS:
    if not grp: 
        continue
    key = grp[0]
    for cid in grp:
        _MANUAL_ID2GROUP[cid] = key

_CARD_ID_RE = re.compile(r"/card/(\\d+)/")

# 針對卡片官方頁面名稱的簡易快取（單次執行、記憶體層級）
_CARD_NAME_BY_URL: Dict[str, Optional[str]] = {}

def get_official_card_name(url: str, timeout: int = 20) -> Optional[str]:
    """
    透過 pokemon-card.com 詳細頁 URL 擷取官方卡名（JP）。
    - 使用記憶體快取避免重複請求。
    - 嘗試 h1 或常見名稱選擇器；失敗回傳 None。
    - 僅做為同名合併與顯示用途，原始逐牌輸出不受影響。
    """
    if not url:
        return None
    # 若未啟用記憶體快取，直接跳過快取檢查
    if USE_URL_NAME_CACHE and url in _CARD_NAME_BY_URL:
        return _CARD_NAME_BY_URL[url]
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, timeout=timeout, headers=headers)
        r.raise_for_status()
        s = _make_soup(r.text)
        node = s.select_one("h1") or s.select_one(".cardname, .heading, .ttl")
        name_jp = node.get_text(strip=True) if node else None
        if not name_jp:
            title = s.title.get_text(strip=True) if s.title else ""
            name_jp = re.split(r"[｜|]", title)[0].strip() if title else None
        if USE_URL_NAME_CACHE:
            _CARD_NAME_BY_URL[url] = name_jp
        return name_jp
    except Exception:
        if USE_URL_NAME_CACHE:
            _CARD_NAME_BY_URL[url] = None
        return None

def apply_manual_aliases(norm_name: str, url: str) -> str:
    """先依名稱別名合併，再依 URL 卡片ID 群組合併；回傳合併後的 key。"""
    # 名稱別名
    if norm_name in MANUAL_NAME_ALIASES:
        norm_name = MANUAL_NAME_ALIASES[norm_name]
    # URL 卡片ID群組
    if url:
        m = _CARD_ID_RE.search(url)
        if m:
            cid = m.group(1)
            grp_key = _MANUAL_ID2GROUP.get(cid)
            if grp_key:
                # 以 group key 形成穩定 key，避免與其他名稱衝突（同組ID視為同一卡）
                norm_name = f"IDGROUP::{grp_key}"
    return norm_name


# ---------- 名稱正規化：去掉括號附加資訊（號碼/標記等），壓縮空白 ----------
_BRACKET_PAIRS = [
    ("(", ")"), ("（", "）"), ("[", "]"), ("【", "】"), ("〈", "〉"), ("｟", "｠"),
]
_BRACKET_RE = re.compile(r"[\(（\[【〈｟].*?[\)）\]】〉｠]")  # 非貪婪移除任何括號包住的資訊

def normalize_name(raw: str) -> str:
    if not raw:
        return raw
    name = raw
    # 1) 去除括號資訊（可能包含型號/卡號/標記），多段也移除
    name = _BRACKET_RE.sub("", name)
    # 2) 去除重複空白（含全形空白）
    name = re.sub(r"[\s\u3000]+", " ", name).strip()
    # 移除尾端多餘的破折/連字號
    name = re.sub(r"[\-–—]\s*$", "", name)
    return name

def _parse_date_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(20\d{2})[\-/](\d{1,2})[\-/](\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass
    return None

def collect_deck_ids_with_date(url: str) -> Tuple[List[Tuple[str, Optional[str]]], Optional[str]]:
    resp = requests.get(url, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
    resp.raise_for_status()
    soup = _make_soup(resp.text)
    deck_ids = []
    pat = re.compile(r"/deckID/([A-Za-z0-9\-]+)")
    for a in soup.find_all("a", href=True):
        m = pat.search(a["href"])
        if m:
            deck_ids.append(m.group(1))
    seen, unique = set(), []
    for d in deck_ids:
        if d not in seen:
            seen.add(d); unique.append(d)

    date_str: Optional[str] = None
    try:
        for sel in [
            "meta[property='article:published_time']",
            "meta[name='pubdate']",
            "meta[name='date']",
            "time[datetime]",
        ]:
            el = soup.select_one(sel)
            if el is None:
                continue
            val = el.get("content") or el.get("datetime") or ""
            date_str = _parse_date_from_text(val)
            if date_str:
                break
        if not date_str:
            date_str = _parse_date_from_text(soup.get_text(" ", strip=True))
    except Exception:
        date_str = None

    # 嘗試就近為每個 deck link 推斷日期（若未取到，回退到文章日期）
    pairs: List[Tuple[str, Optional[str]]] = []
    id_to_first_anchor = {}
    for a in soup.find_all("a", href=True):
        m = pat.search(a["href"])
        if not m:
            continue
        did = m.group(1)
        if did in id_to_first_anchor:
            continue
        id_to_first_anchor[did] = a

    def nearest_date_str(anchor) -> Optional[str]:
        # 1) 自身文字
        txt = (anchor.get_text(" ", strip=True) or "")
        ds = _parse_date_from_text(txt)
        if ds:
            return ds
        # 2) 父層文字
        par = anchor.parent
        for _ in range(3):
            if par is None:
                break
            txt = (par.get_text(" ", strip=True) or "")
            ds = _parse_date_from_text(txt)
            if ds:
                return ds
            par = par.parent
        # 3) 同層兄弟節點（前後各數個）
        try:
            sibs = list(anchor.parent.children) if anchor.parent else []
            if sibs:
                idx = sibs.index(anchor)
                rng = [*range(max(0, idx-3), idx), *range(idx+1, min(len(sibs), idx+4))]
                for j in rng:
                    try:
                        txt = (getattr(sibs[j], 'get_text', lambda *a, **k: str(sibs[j]))(" ", strip=True) or "")
                        ds = _parse_date_from_text(txt)
                        if ds:
                            return ds
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    # Enhanced: prefer deck-level date; skip anchors that look like aggregated summaries
    def _nearest_date_info_ex(anchor) -> Tuple[Optional[str], bool]:
        import re as _re
        re_ymd = _re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
        re_ymd_jp = _re.compile(r"(20\d{2})\s*�~\s*(\d{1,2})\s*��\s*(\d{1,2})\s*��")
        re_md = _re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)")
        re_md_jp = _re.compile(r"(\d{1,2})\s*��\s*(\d{1,2})\s*��")
        range_mark_re = _re.compile(r"[~〜～]|\bto\b|\b-\b")
        def _txt(n):
            try: return (n.get_text(" ", strip=True) or "")
            except Exception: return str(n)
        # Build contexts in priority order: self, parent, grandparent, nearby siblings
        contexts = []
        contexts.append(_txt(anchor))
        p = anchor.parent
        for _ in range(2):
            if not p: break
            contexts.append(_txt(p)); p = p.parent
        try:
            sibs = list(anchor.parent.children) if anchor.parent else []
            if sibs:
                idx = sibs.index(anchor)
                for j in [*range(max(0, idx-3), idx), *range(idx+1, min(len(sibs), idx+4))]:
                    try: contexts.append(_txt(sibs[j]))
                    except Exception: pass
        except Exception:
            pass
        # Evaluate one context at a time; if that single context has multiple dates, mark summary
        for t in contexts:
            ymds = re_ymd.findall(t) + re_ymd_jp.findall(t)
            mds = re_md.findall(t) + re_md_jp.findall(t)
            total_tokens = len(ymds) + len(mds)
            if total_tokens >= 2 or (total_tokens >= 1 and range_mark_re.search(t)):
                return None, True
            if total_tokens == 1:
                if ymds:
                    y,mo,da = [int(x) for x in ymds[0]]
                    return f"{y:04d}-{mo:02d}-{da:02d}", False
                mo,da = [int(x) for x in mds[0]]
                cur_year = datetime.datetime.now().year
                return f"{cur_year:04d}-{mo:02d}-{da:02d}", False
        return None, False

    # New helper with richer signals: returns (ymd_str, (mo,da) or None, is_summary)
    def _nearest_date_info_ex2(anchor) -> Tuple[Optional[str], Optional[Tuple[int,int]], bool]:
        import re as _re
        re_ymd = _re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
        re_ymd_jp = _re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
        re_md = _re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)")
        re_md_jp = _re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
        range_mark_re = _re.compile(r"[~〜～]|\bto\b|\b-\b")

        def _txt(n):
            try:
                return (n.get_text(" ", strip=True) or "")
            except Exception:
                return str(n)

        contexts = []
        contexts.append(_txt(anchor))
        p = anchor.parent
        for _ in range(2):
            if not p:
                break
            contexts.append(_txt(p)); p = p.parent
        try:
            sibs = list(anchor.parent.children) if anchor.parent else []
            if sibs:
                idx = sibs.index(anchor)
                for j in [*range(max(0, idx-3), idx), *range(idx+1, min(len(sibs), idx+4))]:
                    try:
                        contexts.append(_txt(sibs[j]))
                    except Exception:
                        pass
        except Exception:
            pass

        for t in contexts:
            ymds = re_ymd.findall(t) + re_ymd_jp.findall(t)
            mds = re_md.findall(t) + re_md_jp.findall(t)
            total_tokens = len(ymds) + len(mds)
            if total_tokens >= 2 or (total_tokens >= 1 and range_mark_re.search(t)):
                return None, None, True
            if total_tokens == 1:
                if ymds:
                    y,mo,da = [int(x) for x in ymds[0]]
                    return f"{y:04d}-{mo:02d}-{da:02d}", None, False
                mo,da = [int(x) for x in mds[0]]
                return None, (int(mo), int(da)), False
        return None, None, False

    # Year roll logic across the listing for month/day-only dates
    cur_exec_year = datetime.datetime.now().year
    _year_cursor: Optional[int] = cur_exec_year
    _prev_month: Optional[int] = None

    for did in unique:
        a = id_to_first_anchor.get(did)
        if not a:
            pairs.append((did, date_str)); continue
        ymd_str, md_tuple, is_summary = _nearest_date_info_ex2(a)
        if is_summary:
            continue
        final_date: Optional[str] = None
        if ymd_str:
            final_date = ymd_str
            try:
                y, m, d = [int(x) for x in ymd_str.split('-')]
                _year_cursor, _prev_month = y, m
            except Exception:
                pass
        elif md_tuple:
            m, d = md_tuple
            y = _year_cursor if _year_cursor is not None else cur_exec_year
            if _prev_month is not None and m > _prev_month:
                y = (y or cur_exec_year) - 1
            final_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            _year_cursor, _prev_month = y, m
        else:
            final_date = date_str
            if final_date:
                try:
                    y, m, d = [int(x) for x in final_date.split('-')]
                    _year_cursor, _prev_month = y, m
                except Exception:
                    pass
        pairs.append((did, final_date))

    return pairs, date_str

## 已改用 ACE_SPEC_LIST 作為單一來源，移除網路檢出名稱流程

def open_driver():
    opts = Options()
    opts.add_argument("--window-size=1200,900")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=ja-JP")
    opts.add_argument("--user-agent=Mozilla/5.0")
    # Suppress verbose Chrome/Chromedriver logging in console
    opts.add_argument("--log-level=3")           # ERROR
    opts.add_argument("--disable-logging")
    opts.add_experimental_option(
        "excludeSwitches", ["enable-logging", "enable-automation"]
    )
    opts.add_experimental_option("useAutomationExtension", False)

    # Reduce webdriver-manager logs
    try:
        os.environ.setdefault("WDM_LOG_LEVEL", "0")
    except Exception:
        pass

    # Route chromedriver logs to DEVNULL when supported
    try:
        import subprocess
        service = Service(ChromeDriverManager().install(), log_output=subprocess.DEVNULL)
    except TypeError:
        # Older selenium: no log_output param
        service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def click_cookies(driver):
    for sel in ["#onetrust-accept-btn-handler", ".cookie a", ".cookie button", "button[aria-label*='同意']"]:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if el.is_displayed() and el.is_enabled():
                    el.click(); time.sleep(0.3)
            except: pass

def save_debug(driver, deck_id, tag):
    """Dump current page HTML to debug_cells/<deck_id>_<tag>.html for troubleshooting."""
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', deck_id)
    os.makedirs("debug", exist_ok=True)
    try: driver.save_screenshot(f"debug/{safe}_{tag}.png")
    except: pass
    try:
        with open(f"debug/{safe}_{tag}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except: pass

def force_list_view(driver, wait: WebDriverWait, deck_id: str):
    """Ensure deck page is rendered in list/table mode so rows are visible."""
    try:
        btn = wait.until(EC.element_to_be_clickable((By.ID, "deckView01")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        try: btn.click()
        except: driver.execute_script("arguments[0].click();", btn)
    except Exception:
        pass
    try:
        lab = driver.find_element(By.CSS_SELECTOR, "label[for='deckView01']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", lab)
        try: lab.click()
        except: driver.execute_script("arguments[0].click();", lab)
    except Exception:
        pass
    driver.execute_script('''
      try {
        if (window.PCGDECK) { PCGDECK.viewItemMode = 1; }
        var list = document.querySelector('#cardListView');
        var imgs = document.querySelector('#cardImagesView');
        if (list) { list.style.display = 'block'; list.classList.add('is-active'); }
        if (imgs) { imgs.style.display = 'none'; imgs.classList.remove('is-active'); }
      } catch(e) {}
    ''')
    try:
        wait.until(EC.visibility_of_element_located((By.ID, "cardListView")))
    except Exception:
        save_debug(driver, deck_id, "list_not_visible")
        raise

_HERF_WARNED_ONCE = False  # Site quirk: some anchors mistakenly use "herf" instead of "href"

def extract_url_from_cell(cell):
    """Best-effort extraction of the card detail URL from a table cell.
    Handles normal href, the site's common onclick pattern, and a known typo "herf".
    """
    global _HERF_WARNED_ONCE
    anchors = cell.find_elements(By.CSS_SELECTOR, "a")
    for a in anchors:
        href = (a.get_attribute("href") or "").strip()
        # Quirk: some pages mistakenly write herf instead of href
        if not href:
            herf = (a.get_attribute("herf") or "").strip()
            if herf:
                href = herf
                if not _HERF_WARNED_ONCE:
                    try:
                        print("[warn] Detected anchor with 'herf' instead of 'href'; handled as href.")
                    except Exception:
                        pass
                    _HERF_WARNED_ONCE = True
        if href and not href.lower().startswith("javascript"):
            return href if not href.startswith("/") else BASE + href
        onclick = (a.get_attribute("onclick") or "")
        m = re.search(r"cardDetailViewCall\('(\d+)'\)", onclick)
        if m:
            card_id = m.group(1)
            return f"{BASE}/card-search/details.php/card/{card_id}/"
    onclick = (cell.get_attribute("onclick") or "")
    m = re.search(r"cardDetailViewCall\('(\d+)'\)", onclick)
    if m:
        card_id = m.group(1)
        return f"{BASE}/card-search/details.php/card/{card_id}/"
    return ""

def parse_table(driver, deck_id: str):
    """Parse list view into rows of (section_jp, raw_name, count, url).
    Cover both table and definition-list layouts, preserving header order.
    """
    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "#cardListView th, #cardListView dt, #cardListView .deckListTable tbody tr, #cardListView table tbody tr, #cardListView li"
    )
    if not rows:
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "section#cardListView th, section#cardListView dt, section#cardListView table tbody tr, section#cardListView li"
        )
    if not rows:
        save_debug(driver, deck_id, "no_rows")
        return []

    out, section = [], ""
    os.makedirs("debug_cells", exist_ok=True)
    for i, r in enumerate(rows):
        ths = r.find_elements(By.TAG_NAME, "th")
        if ths:
            section = ths[0].text.strip(); continue
        # Some pages use <dt> as the section header instead of <th>
        dts = r.find_elements(By.TAG_NAME, "dt")
        if dts:
            section = dts[0].text.strip(); continue
        tds = r.find_elements(By.TAG_NAME, "td")
        if len(tds) >= 2:
            # Fallbacks: if section is still empty, try nearest previous section header
            if not section:
                try:
                    # Previous header row in table form
                    prev_th = r.find_elements(By.XPATH, "preceding-sibling::tr[th][1]/th[1]")
                    if prev_th:
                        section = prev_th[0].text.strip()
                except Exception:
                    pass
            if not section:
                try:
                    # Previous header in definition list form (same parent)
                    prev_dt = r.find_elements(By.XPATH, "preceding-sibling::dt[1]")
                    if prev_dt:
                        section = prev_dt[0].text.strip()
                except Exception:
                    pass
            if not section:
                try:
                    # If we are inside <dd><ul><li>..., find the dt before the enclosing dd
                    prev_dt2 = r.find_elements(By.XPATH, "ancestor::dd[1]/preceding-sibling::dt[1]")
                    if prev_dt2:
                        section = prev_dt2[0].text.strip()
                except Exception:
                    pass
            name_cell = tds[0]
            try:
                with open(f"debug_cells/{deck_id}_row{i}.html", "w", encoding="utf-8") as f:
                    f.write(name_cell.get_attribute("innerHTML"))
            except: pass

            raw_name = name_cell.text.strip()
            url = extract_url_from_cell(name_cell)
            cnt_txt = tds[1].text.strip().replace("枚", "")
            try: cnt = int(re.sub(r"\D", "", cnt_txt) or "0")
            except: cnt = 0
            if raw_name:
                out.append((section, raw_name, cnt, url))
    if not out:
        save_debug(driver, deck_id, "empty_parse")
    return out

def analyze_deck(deck_id: str, cards: List[Tuple[str, str, int, str]]) -> Dict[str, int]:
    """Aggregate per-category counts for one deck.
    Category detection follows priority to avoid misclassifying どうぐ as ポケモン.
    """
    stats = {"deck_id": deck_id,"pokemon":0,"goods":0,"tools":0,"supporter":0,"stadium":0,"energy":0,"total_cards":0}
    for sec, _, cnt, _ in cards:
        cat = section_to_category(sec)
        if cat and cat in stats:
            stats[cat] += cnt
        stats["total_cards"] += cnt
    return stats
def round_targets_to_60(avg_counts: Dict[str, float]) -> Dict[str, int]:
    """
    依各類型平均張數取無條件捨去的整數；若總和不足 60，差額補到 energy。
    """
    order = ["pokemon","goods","tools","supporter","stadium","energy"]
    # 無條件捨去
    targets = {k: int(avg_counts.get(k, 0.0)) for k in order}
    total = sum(targets.values())
    if total < 60:
        # 將差額補到能量
        targets["energy"] = targets.get("energy", 0) + (60 - total)
    elif total > 60:
        # 若不小心超過，保守起見先從能量扣回到 60（避免破壞其他類型）
        over = total - 60
        take = min(over, targets.get("energy", 0))
        targets["energy"] = max(0, targets.get("energy", 0) - take)
        over -= take
        # 若仍有超過，依固定順序嘗試再扣（不會低於 0）
        if over > 0:
            for k in ["stadium","supporter","tools","goods","pokemon"]:
                if over == 0:
                    break
                can = min(over, targets.get(k, 0))
                if can > 0:
                    targets[k] = targets.get(k, 0) - can
                    over -= can
    return targets

def is_basic_energy(name: str) -> bool:
    """判斷是否為基本能量：
    - 官方名通常為「基本草エネルギー／基本炎エネルギー／…」，
      舊邏輯只找『基本エネルギー』會漏判。
    - 這裡同時接受『基本エネルギー』與『基本.+エネルギー』型式。
    """
    if not name:
        return False
    n = normalize_name(name)
    return ("基本エネルギー" in n) or bool(re.search(r"基本.+エネルギー", n))

# ====== 排名/選卡使用（同名＝正規化後名稱；代表 URL 與顯示名） ======
def get_ranked_items(cat: str,
                     card_totals: Dict[str, Dict[str, int]],
                     card_decks: Dict[str, Dict[str, Set[str]]],
                     name_primary_url: Dict[str, Dict[str, str]],
                     name_display: Dict[str, Dict[str, str]],
                     total_decks: int,
                     exclude_names:Set[str]=set()):
    """Rank cards in a category by (avg_overall, used_decks), desc.
    Returns tuples consumed by build_suggested_deck.
    """
    items = []
    for norm_name, total_cnt in card_totals[cat].items():
        if norm_name in exclude_names: continue
        n_decks = len(card_decks[cat].get(norm_name, set()))
        if n_decks == 0: continue
        avg_overall = total_cnt / total_decks if total_decks else 0.0
        avg_present = total_cnt / n_decks
        url = name_primary_url[cat].get(norm_name, "")
        disp = name_display[cat].get(norm_name, norm_name)
        items.append((avg_overall, n_decks, avg_present, norm_name, disp, url))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return items

def build_suggested_deck(targets: Dict[str,int],
                         card_totals, card_decks, name_primary_url, name_display,
                         total_decks: int,
                         ace_jp_norm_names: set,
                         use_ace_spec: bool) -> List[Tuple[str,str,int,str]]:
    """Construct a 60-card suggestion from category targets and usage stats.
    Applies soft per-name caps (≤4 for non-basic energy); final strict caps are
    enforced later by _final_strict_name_cap.
    """
    order = ["pokemon","goods","tools","supporter","stadium","energy"]
    result = []
    for cat in order:
        items = get_ranked_items(cat, card_totals, card_decks, name_primary_url, name_display, total_decks)
        if not use_ace_spec:
            items = [t for t in items if not any(ace in t[3] for ace in ace_jp_norm_names)]
        # 使用率過濾：排除出現比例過低或出現副數過少的卡
        if total_decks > 0:
            def _pass_usage(t):
                avg_overall, n_decks, _, _, _, _ = t
                rate = n_decks / total_decks if total_decks else 0.0
                return (n_decks >= SUGGEST_MIN_DECKS) and (rate >= SUGGEST_MIN_USAGE_RATE)
            items = [t for t in items if _pass_usage(t)]

        target = targets.get(cat, 0)
        picked = []
        used_norm = set()

        for _, _, avg_present, norm_name, disp_name, url in items:
            if sum(c for _,_,c,_ in picked) >= target: break
            if norm_name in used_norm: continue
            copies = max(1, int(round(avg_present)))
            if not is_basic_energy(disp_name):
                copies = min(copies, 4)
            copies = min(copies, max(1, target - sum(c for _,_,c,_ in picked)))
            picked.append((cat, disp_name, copies, url))
            used_norm.add(norm_name)

        i = 0
        while sum(c for _,_,c,_ in picked) < target and i < len(items):
            _, _, _, norm_name, disp_name, url = items[i]
            if norm_name not in used_norm:
                picked.append((cat, disp_name, 1, url))
                used_norm.add(norm_name)
            i += 1

        while sum(c for _,_,c,_ in picked) > target:
            cat_, name_, copies_, url_ = picked[-1]
            need_trim = sum(c for _,_,c,_ in picked) - target
            if copies_ > need_trim:
                picked[-1] = (cat_, name_, copies_ - need_trim, url_)
            else:
                picked.pop()
        result.extend(picked)

    # 調整總數 = 60（用 energy 調整）
    total_cards = sum(c for _,_,c,_ in result)
    if total_cards != 60:
        idxs = [i for i,(cat,_,_,_) in enumerate(result) if cat=="energy"]
        if total_cards < 60:
            if idxs:
                i = idxs[0]
                cat,name,copies,url = result[i]
                result[i] = (cat,name,copies + (60-total_cards),url)
            else:
                result.append(("energy","基本エネルギー", 60-total_cards, ""))
        else:
            for i in idxs:
                over = total_cards - 60
                if over <= 0: break
                cat,name,copies,url = result[i]
                dec = min(copies, over)
                result[i] = (cat,name,copies-dec,url)
                over -= dec
            while sum(c for _,_,c,_ in result) > 60 and result:
                cat,name,copies,url = result[-1]
                if copies > 1: result[-1] = (cat,name,copies-1,url)
                else: result.pop()
    return result

def enforce_ace_spec_policy(suggested: List[Tuple[str,str,int,str]],
                            ace_jp_norm_names: set,
                            use_flag: bool,
                            force_name: Optional[str],
                            card_totals, card_decks, name_primary_url, name_display, total_decks: int,
                            ace_targets: Dict[str,str]) -> Tuple[List[Tuple[str,str,int,str]], str]:
    """Enforce ACE SPEC selection rules on a suggested deck.
    - Disabled: remove all ACE, convert counts to energy
    - Enabled: keep exactly one ACE (optionally force by name) or add one heuristically
    Returns (new_suggested, note).
    """
    ace_indices = []
    for i,(cat,name,copies,url) in enumerate(suggested):
        if any(ace in normalize_name(name) for ace in ace_jp_norm_names):
            ace_indices.append(i)

    if not use_flag:
        removed = 0
        new_list = []
        for i,(cat,name,copies,url) in enumerate(suggested):
            if i in ace_indices:
                removed += copies
                continue
            new_list.append((cat,name,copies,url))
        if removed > 0:
            for j,(cat,name,copies,url) in enumerate(new_list):
                if cat == "energy":
                    new_list[j] = (cat,name,copies+removed,url); removed = 0; break
            if removed > 0:
                new_list.append(("energy","基本エネルギー", removed, ""))
        return new_list, "已移除所有 ACE SPEC（因 USE_ACE_SPEC=False）。"

    keep_idx = None
    if ace_indices:
        if force_name:
            f_norm = normalize_name(force_name)
            for i in ace_indices:
                if f_norm in normalize_name(suggested[i][1]):
                    keep_idx = i; break
        if keep_idx is None:
            keep_idx = ace_indices[0]

        new_list = []
        restored = 0
        for i,(cat,name,copies,url) in enumerate(suggested):
            if i == keep_idx:
                new_list.append((cat,name,1,url))
                if copies > 1:
                    restored += (copies - 1)
            elif i in ace_indices:
                restored += copies
            else:
                new_list.append((cat,name,copies,url))
        if restored > 0:
            for j,(cat,name,copies,url) in enumerate(new_list):
                if cat == "energy":
                    new_list[j] = (cat,name,copies+restored,url); restored = 0; break
            if restored > 0:
                new_list.append(("energy","基本エネルギー", restored, ""))
        return new_list, "已限制為恰好 1 張 ACE SPEC（保留既有）。"

    # 沒有 ACE → 需要加入 1 張
    chosen_name, chosen_url = None, ""
    if force_name:
        chosen_name = force_name
        chosen_url  = ace_targets.get(normalize_name(force_name), "")
    else:
        best = None
        for cat in ["goods","tools","supporter"]:
            for norm_name, total_cnt in card_totals[cat].items():
                if not any(ace in norm_name for ace in ace_jp_norm_names): continue
                n_decks = len(card_decks[cat].get(norm_name, set()))
                if n_decks == 0: continue
                avg_overall = total_cnt / total_decks if total_decks else 0.0
                tup = (avg_overall, name_display[cat].get(norm_name, norm_name), name_primary_url[cat].get(norm_name, ""))
                if (best is None) or (tup > best):
                    best = tup
        if best:
            _, chosen_name, chosen_url = best
        else:
            if ace_targets:
                # 取第一個目標（顯示用 raw key 不詳，此處使用 normalize 前名可能不可得，直接用 key）
                any_norm = list(ace_targets.keys())[0]
                chosen_name = any_norm
                chosen_url  = ace_targets[any_norm]
            else:
                chosen_name = "ACE SPEC"
                chosen_url  = ""

    suggested.append(("goods", chosen_name, 1, chosen_url))
    total_cards = sum(c for _,_,c,_ in suggested)
    if total_cards > 60:
        for i,(cat,name,copies,url) in enumerate(suggested):
            if cat=="energy" and copies>1:
                dec = min(copies-1, total_cards-60)
                suggested[i] = (cat,name,copies-dec,url)
                total_cards -= dec
                if total_cards == 60: break
        while total_cards > 60 and suggested:
            cat,name,copies,url = suggested[-1]
            if any(ace in normalize_name(name) for ace in ace_jp_norm_names):
                suggested.insert(0, suggested.pop())
                continue
            if copies > 1:
                suggested[-1] = (cat,name,copies-1,url); total_cards -= 1
            else:
                suggested.pop(); total_cards -= 1
    return suggested, f"已加入 1 張 ACE SPEC：{chosen_name}"

def fetch_deck(driver, deck_id: str):
    url = f"{BASE}/deck/confirm.html/deckID/{deck_id}"
    wait = WebDriverWait(driver, 40)
    driver.get(url); click_cookies(driver)
    force_list_view(driver, wait, deck_id)
    return parse_table(driver, deck_id)

def filter_deck_by_cards(cards, keywords: List[str], require_all: bool) -> bool:
    """Filter a deck by keywords in raw names.
    require_all=True → every keyword must appear at least once.
    require_all=False → any one keyword appears.
    """
    if not keywords:
        return True
    names = [name for _, name, _, _ in cards]
    if require_all:
        return all(any(kw in n for n in names) for kw in keywords)
    else:
        return any(any(kw in n for n in names) for kw in keywords)


# ---------------- Image helpers for suggested deck ----------------
def _safe_filename(name: str) -> str:
    import re as _re
    n = (name or '').strip() or 'card'
    n = _re.sub(r"[^\w\-\u4e00-\u9fa5\u3040-\u30ff\u3000]+", "_", n)
    return n[:100]


def get_card_image_url_http(url: str, timeout: int = 20) -> Optional[str]:
    """從卡片詳情頁抓取卡圖 URL（偏好 /assets/images/card_images/）。"""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        s = _make_soup(r.text)
        og = s.select_one("meta[property='og:image']")
        if og and og.get('content') and '/assets/images/card_images/' in og['content']:
            return og['content']
        el = s.select_one("img[src*='/assets/images/card_images/']")
        if el is not None:
            return el.get('src') or el.get('data-src')
        return None
    except Exception:
        return None


def download_image(url: str, out_path: str) -> bool:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=30, headers={"User-Agent":"Mozilla/5.0"}) as resp:
            resp.raise_for_status()
            with open(out_path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception:
        return False


def make_collage(image_paths: List[str], cols: int, rows: int, cell_w: int, cell_h: int, out_path: str, labels: Optional[List[str]] = None) -> Optional[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        print("[warn] Pillow 未安裝，無法產生拼圖；請先安裝：pip install pillow")
        return None
    W, H = cols * cell_w, rows * cell_h
    canvas = Image.new('RGB', (W, H), (255, 255, 255))

    def open_fit(p: str):
        try:
            im = Image.open(p).convert('RGB')
        except Exception:
            im = Image.new('RGB', (cell_w, cell_h), (230, 230, 230))
        w, h = im.size
        scale = min(cell_w / max(1, w), cell_h / max(1, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        im = im.resize((nw, nh), Image.LANCZOS)
        pad = Image.new('RGB', (cell_w, cell_h), (255, 255, 255))
        pad.paste(im, ((cell_w - nw)//2, (cell_h - nh)//2))
        return pad

    for idx, p in enumerate(image_paths[:cols*rows]):
        r, c = divmod(idx, cols)
        x, y = c * cell_w, r * cell_h
        tile = open_fit(p)
        # 標籤（張數）置中偏下，圓形外框，數字置中且放大
        if labels and idx < len(labels) and labels[idx]:
            try:
                d = ImageDraw.Draw(tile)
                raw_tag = labels[idx]
                num_text = raw_tag[1:] if raw_tag.lower().startswith('x') else raw_tag
                # 圓形尺寸與位置（置中稍微偏下）
                diameter = int(min(cell_w, cell_h) * 0.22)
                cx = cell_w // 2
                cy = int(cell_h * 0.90)
                left = cx - diameter // 2
                top = cy - diameter // 2
                right = cx + diameter // 2
                bottom = cy + diameter // 2
                # 背景圓與外框
                d.ellipse([left, top, right, bottom], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
                # 字型：嘗試較大的 TrueType，失敗改用預設
                font = None
                for fname in ("DejaVuSans-Bold.ttf", "arial.ttf", "NotoSansCJK-Regular.ttc"):
                    try:
                        font = ImageFont.truetype(fname, size=max(14, int(diameter * 0.55)))
                        break
                    except Exception:
                        font = None
                if font is None:
                    font = ImageFont.load_default()
                # 文字置中於圓心
                placed = False
                try:
                    # Pillow >= 8 支援 anchor
                    d.text((cx, cy), num_text, fill=(0, 0, 0), font=font, anchor="mm")
                    placed = True
                except Exception:
                    placed = False
                if not placed:
                    try:
                        bbox = d.textbbox((0, 0), num_text, font=font)
                        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except Exception:
                        tw = int(d.textlength(num_text, font=font)) if hasattr(d, 'textlength') else int(diameter * 0.5)
                        th = int(diameter * 0.55)
                    tx = cx - tw // 2
                    ty = cy - th // 2
                    d.text((tx, ty), num_text, fill=(0, 0, 0), font=font)
            except Exception:
                pass
        canvas.paste(tile, (x, y))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, quality=90)
    return out_path

def _date_in_range(date_str: Optional[str], dfrom: Optional[str], dto: Optional[str]) -> bool:
    """檢查 YYYY-MM-DD 是否在 [dfrom, dto] 範圍內；任一為 None 則不限制該端。date_str 為 None 視為通過。"""
    if not date_str:
        return True
    try:
        y, m, d = [int(x) for x in date_str.split('-')]
        dt = datetime.date(y, m, d)
    except Exception:
        return True
    if dfrom:
        try:
            y, m, d = [int(x) for x in dfrom.split('-')]
            if dt < datetime.date(y, m, d):
                return False
        except Exception:
            pass
    if dto:
        try:
            y, m, d = [int(x) for x in dto.split('-')]
            if dt > datetime.date(y, m, d):
                return False
        except Exception:
            pass
    return True

def analyze_source(src: str) -> None:
    print(f"\n===== 來源：{src} =====")
    deck_pairs, src_date = collect_deck_ids_with_date(src)
    deck_ids = [d for d,_ in deck_pairs]
    deck_date_map = {d:(dt or src_date) for d, dt in deck_pairs}
    if not _date_in_range(src_date, ANALYZE_DATE_FROM, ANALYZE_DATE_TO):
        print(f"來源日期 {src_date or '未知'} 不在範圍內（from={ANALYZE_DATE_FROM or '-'}, to={ANALYZE_DATE_TO or '-'}），略過本來源。")
        return

    if RECENT_DECKS_LIMIT is not None:
        deck_ids = deck_ids[:RECENT_DECKS_LIMIT]
        print(f"只統計近 {RECENT_DECKS_LIMIT} 副 → 共 {len(deck_ids)} 個 deckID")
    else:
        print(f"統計全部 → 共 {len(deck_ids)} 個 deckID")
    if src_date:
        print(f"來源日期：{src_date}")

    # 來源專屬輸出目錄
    safe_tag = re.sub(r'[^A-Za-z0-9_-]+', '_', src)[:40]
    OUT = os.path.join(OUTPUT_DIR, f"src_{safe_tag}")
    os.makedirs(OUT, exist_ok=True)

    # 將此來源的執行輸出同步寫入檔案，便於之後分析
    log_path = os.path.join(OUT, f"run_{RUN_TIMESTAMP}.log")
    _orig_stdout, _orig_stderr = sys.stdout, None
    try:
        _log_file = open(log_path, "w", encoding="utf-8")
        class _Tee:
            def __init__(self, *streams): self.streams = streams
            def write(self, s):
                for st in self.streams:
                    try: st.write(s)
                    except Exception: pass
            def flush(self):
                for st in self.streams:
                    try: st.flush()
                    except Exception: pass
        sys.stdout = _Tee(_orig_stdout, _log_file)
    except Exception:
        _log_file = None

    # 每個來源使用獨立的 SQLite 快取檔，避免交互覆寫與鎖定
    global CACHE_DB
    CACHE_DB = os.path.join(OUT, f"deck_cache_{safe_tag}.sqlite")

    # ACE 目標（單一來源）
    ace_targets_raw = {normalize_name(n): _ace_short(u) for n, u in ACE_SPEC_LIST if n and u}
    try:
        print_ace_spec_list_once()
        if False:
            print("\n=== ACE SPEC（由 ACE_SPEC_LIST 輸出） ===")
            print("ACE_SPEC_LIST_DETECTED = [")
            for name, u in ACE_SPEC_LIST:
                if not name or not u:
                    continue
                safe_name = name.replace('"', '\\"')
                print(f'    ("{safe_name}", "{_ace_short(u)}"),')
            print("]")
    except Exception as _e:
        print(f"[warn] 列印 ACE SPEC 偵測結果失敗：{_e}")

    # 快取策略
    try:
        if 'USE_SQLITE_CACHE' in globals() and not USE_SQLITE_CACHE and ('CLEAR_CACHE_ON_DISABLE' in globals() and CLEAR_CACHE_ON_DISABLE):
            ok = clear_cache_sqlite()
            print(f"[cache] SQLite 快取已清除：{ok}")
        if 'USE_URL_NAME_CACHE' in globals() and not USE_URL_NAME_CACHE:
            _CARD_NAME_BY_URL.clear()
    except Exception:
        pass

    # 初始化
    init_cache()
    ace_jp_norm_names = set(ace_targets_raw.keys())
    driver = None  # lazy init driver
    all_rows, all_stats, ace_occurrences = [], [], []
    ace_deck_sets = {jp: set() for jp in ace_jp_norm_names}

    cats = ["pokemon","goods","tools","supporter","stadium","energy"]
    card_totals = {c:{} for c in cats}
    card_decks  = {c:{} for c in cats}
    name_primary_url = {c:{} for c in cats}
    name_all_urls   = {c:{} for c in cats}
    name_display    = {c:{} for c in cats}

    # Per-date accumulators for daily analysis
    date_totals = {}  # date -> cat -> norm -> count
    date_decks  = {}  # date -> cat -> norm -> set(deck_id)
    date_primary= {}  # date -> cat -> norm -> url
    date_allurls= {}  # date -> cat -> norm -> set(url)
    date_display= {}  # date -> cat -> norm -> display name

    try:
        for did in deck_ids:
            try:
                cached = get_cached_deck(did)
                if cached is not None:
                    cards, stats = cached
                    print(f"♻ 使用快取：{did}")
                    # 壞快取偵測：總張數 > 0 但六大類全為 0，或所有 section 皆為空
                    bad_cache = False
                    try:
                        if isinstance(stats, dict):
                            cat_sum = sum(int(stats.get(k, 0)) for k in ("pokemon","goods","tools","supporter","stadium","energy"))
                            if int(stats.get("total_cards", 0)) > 0 and cat_sum == 0:
                                bad_cache = True
                    except Exception:
                        bad_cache = True
                    try:
                        if cards and all(not (str(sec or '').strip()) for sec, _, _, _ in cards):
                            bad_cache = True
                    except Exception:
                        pass
                    if bad_cache:
                        print(f"[cache] 偵測到壞快取，重新抓取：{did}")
                        if driver is None:
                            driver = open_driver()
                        cards = fetch_deck(driver, did)
                        stats = analyze_deck(did, cards)
                        save_cached_deck(did, cards, stats)
                else:
                    if driver is None:
                        driver = open_driver()
                    cards = fetch_deck(driver, did)
                    stats = analyze_deck(did, cards)
                    save_cached_deck(did, cards, stats)

                if not filter_deck_by_cards(cards, FILTER_CARD_KEYWORDS, FILTER_REQUIRE_ALL):
                    print(f"✗ {did} 跳過（不符合卡片過濾條件）")
                    continue

                # 收集本牌組的 section 範例以利診斷
                sec_samples = set()
                for sec, raw_name, cnt, url in cards:
                    try:
                        if sec:
                            sec_samples.add(str(sec))
                    except Exception:
                        pass

                # 逐 deck 診斷：若六大類總和為 0 但總張數 > 0，輸出 section 範例供排查
                try:
                    cat_sum = sum(int(stats.get(k, 0)) for k in ("pokemon","goods","tools","supporter","stadium","energy"))
                    if int(stats.get("total_cards", 0)) > 0 and cat_sum == 0:
                        diag_dir = os.path.join(OUT, "diagnostics")
                        os.makedirs(diag_dir, exist_ok=True)
                        diag_path = os.path.join(diag_dir, f"sections_{did}.txt")
                        with open(diag_path, "w", encoding="utf-8") as df:
                            df.write("Sections captured for deck " + did + "\n")
                            for s in sorted({(s or '').strip() for s in sec_samples if s}):
                                df.write(s + "\n")
                            df.write("\nFirst 10 cards (section, name, cnt):\n")
                            for sec, raw_name, cnt, url in cards[:10]:
                                sec_str = (sec or '').strip()
                                df.write(f"- {sec_str} | {raw_name} | {cnt}\n")
                        print(f"[diag] 已輸出分類為 0 的區塊標題樣本：{diag_path}")
                except Exception:
                    pass
                time.sleep(0.5)
            except Exception as e:
                print(f"⚠ {did} 失敗：{e}")
                continue
    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass
        # 還原 stdout 並關閉 log
        try:
            if _log_file:
                _log_file.flush(); _log_file.close()
        except Exception:
            pass
        try:
            if _orig_stdout is not None:
                sys.stdout = _orig_stdout
        except Exception:
            pass

    # 統計與輸出
    total_decks = len([1 for _ in all_stats])
    print("\n=== ACE SPEC 統計結果 ===")
    if not ace_occurrences:
        print("⚠ 提醒：在所有牌組中沒有找到任何 ACE SPEC 卡片！")
    for jp_norm in ace_targets_raw.keys():
        total_count = sum(int(cnt) for _, n, _, cnt in ace_occurrences if n == jp_norm)
        used_decks = len(ace_deck_sets[jp_norm])
        if used_decks == 0:
            continue
        if used_decks == 0:
            print(f"⚠ 提醒：{jp_norm} 在所統計的牌組中都沒有出現。")
        else:
            rate = used_decks / total_decks if total_decks else 0
            print(f"{jp_norm}: 張數總合 {total_count} ｜ 使用率 {used_decks}/{total_decks} = {rate:.1%}")

    print("\n=== 各類型平均張數（每副牌組平均） ===")
    cats = ["pokemon","goods","tools","supporter","stadium","energy"]
    cat_sums = {c:0 for c in cats}
    for s in all_stats:
        for c in cats:
            cat_sums[c] += s[c]
    cat_avgs = {c: (cat_sums[c]/total_decks if total_decks else 0.0) for c in cats}
    for c in cats:
        print(f"{c}: {cat_avgs[c]:.2f}")

    # 依日期分類牌組（使用來源頁面解析到的日期；無則顯示為 未知）
    print("\n=== 牌組日期分布（以來源網址的日期資訊） ===")
    date_buckets = {}
    for s in all_stats:
        d = s.get("date") or "未知"
        date_buckets.setdefault(d, 0)
        date_buckets[d] += 1
    # 由近到遠（新到舊）；未知日期放最後
    known = []
    unknown = []
    for d, cnt in date_buckets.items():
        try:
            y, m, dd = [int(x) for x in str(d).split('-')]
            known.append(((y, m, dd), d, cnt))
        except Exception:
            unknown.append((d, cnt))
    known.sort(key=lambda t: t[0], reverse=True)
    for _, d, cnt in known:
        print(f"{d}: {cnt} 副")
    for d, cnt in unknown:
        print(f"{d}: {cnt} 副")

    rows_summary = []
    for cat in cats:
        for norm_name, total_cnt in card_totals[cat].items():
            decks_with_card = len(card_decks[cat].get(norm_name, set()))
            avg_overall = (total_cnt / total_decks) if total_decks else 0.0
            avg_when_present = (total_cnt / decks_with_card) if decks_with_card else 0.0
            disp = name_display[cat].get(norm_name, norm_name)
            url_set = name_all_urls[cat].get(norm_name, set())
            if url_set:
                parts = [f'=HYPERLINK("{u}","link{idx+1}")' for idx, u in enumerate(sorted(url_set))]
                urls_formula = parts[0] if len(parts)==1 else ("=" + "&\" | \"&".join(parts))
            else:
                urls_formula = ""
            rows_summary.append([cat, disp, urls_formula, decks_with_card, total_cnt, f"{avg_when_present:.3f}", f"{avg_overall:.3f}"])
    with open(os.path.join(OUT, "card_usage_summary.csv"),"w",encoding="utf-8-sig",newline="") as f:
        w = csv.writer(f)
        w.writerow(["category","card_name_jp","urls","decks_with_card","total_copies","avg_when_present (per decks with card)","avg_overall (per all decks)"])
        w.writerows(rows_summary)
    print("\n已輸出 card_usage_summary.csv（同名合併；列出所有 URL；平均分母=全部牌組）")

    print("\n=== 各類型 平均張數最高 Top 5（avg_overall） ===")
    for cat in cats:
        items = []
        for norm_name, total_cnt in card_totals[cat].items():
            if total_decks == 0: continue
            avg_overall = total_cnt / total_decks
            disp = name_display[cat].get(norm_name, norm_name)
            url = name_primary_url[cat].get(norm_name, "")
            items.append((avg_overall, disp, url, total_cnt))
        if not items:
            print(f"{cat}: 無資料"); continue
        items.sort(key=lambda x: x[0], reverse=True)
        top5 = items[:5]
        print(f"{cat}:")
        for avg, disp, url, total_cnt in top5:
            print(f"  {disp} ｜ 平均 {avg:.3f} 張（總張數 {total_cnt}）→ {url or '（無鏈結）'}")

    # 依請求：印出各張卡片的平均每副張數（可限制每類別最多列出 N 筆）
    print("\n=== 各卡平均每副張數（avg_overall）清單 ===")
    for cat in cats:
        items = []
        for norm_name, total_cnt in card_totals[cat].items():
            avg_overall = (total_cnt / total_decks) if total_decks else 0.0
            decks_with_card = len(card_decks[cat].get(norm_name, set()))
            disp = name_display[cat].get(norm_name, norm_name)
            url = name_primary_url[cat].get(norm_name, "")
            items.append((avg_overall, decks_with_card, total_cnt, disp, url))
        items.sort(key=lambda x: x[0], reverse=True)
        if not items:
            print(f"{cat}: 無資料"); continue
        limit = PRINT_CARD_AVG_LIMIT if PRINT_CARD_AVG_LIMIT and PRINT_CARD_AVG_LIMIT > 0 else len(items)
        print(f"{cat}:（列出 {limit if limit else '全部'} 筆）")
        for i, (avg, n_decks, tot, disp, url) in enumerate(items[:limit], 1):
            print(f"  {i:>2}. {disp} ｜ 平均 {avg:.3f} 張；出現 {n_decks} 副；總張數 {tot} → {url or '（無鏈結）'}")

    targets = round_targets_to_60(cat_avgs)
    print("\n=== 依平均值組出的示範牌組（目標分配） ===")
    print(targets)

    # 說明本次建議牌組的使用率過濾條件
    if total_decks > 0:
        print(f"\n[使用率過濾] 門檻：至少 {SUGGEST_MIN_DECKS} 副、使用率 ≥ {SUGGEST_MIN_USAGE_RATE:.1%}（僅套用於非能量卡的候選清單）")

    suggested = build_suggested_deck(
        targets, card_totals, card_decks, name_primary_url, name_display, total_decks,
        ace_jp_norm_names, USE_ACE_SPEC
    )

    suggested, note = enforce_ace_spec_policy(
        suggested, ace_jp_norm_names, USE_ACE_SPEC, FORCE_ACE_SPEC_NAME,
        card_totals, card_decks, name_primary_url, name_display, total_decks, ace_targets_raw
    )
    print(f"\n[ACE 規則] {note}")

    capped = []
    for cat,name,copies,url in suggested:
        if not is_basic_energy(name) and copies > 4:
            copies = 4
        capped.append((cat,name,copies,url))
    suggested = capped

    cat_totals_out = {c:0 for c in cats}
    for cat in cats:
        cat_totals_out[cat] = sum(k for (c,_,k,_) in suggested if c==cat)
    print("\n=== 建議牌組（60 張） ===")
    total_cards = 0
    for cat in cats:
        block = [(c,n,k,u) for (c,n,k,u) in suggested if c==cat]
        if not block:
            continue
        print(f"[{cat}]（合計 {cat_totals_out[cat]}）")
        for _, name, copies, url in block:
            total_cards += copies
            print(f"  {name} × {copies}  → {url or '（無鏈結）'}")
    print(f"總計：{total_cards} 張")

    with open(os.path.join(OUT, "suggested_deck.csv"),"w",encoding="utf-8-sig",newline="") as f:
        w = csv.writer(f)
        w.writerow(["category","card_name_jp","copies","urls"])
        for cat,name,copies,url in suggested:
            norm = normalize_name(name)
            norm = apply_manual_aliases(norm, '')
            url_set = name_all_urls.get(cat, {}).get(norm, set())
            if url_set:
                parts = [f'=HYPERLINK("{u}","link{idx+1}")' for idx, u in enumerate(sorted(url_set))]
                urls_formula = parts[0] if len(parts)==1 else ("=" + "&\" | \"&".join(parts))
            else:
                urls_formula = ""
            w.writerow([cat,name,copies,urls_formula])

    with open(os.path.join(OUT, "decks_parsed.csv"),"w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(["deck_id","date","section_jp","card_name_jp","count","url"])
        for did, sec, raw_name, cnt, url in all_rows:
            w.writerow([did, deck_date_map.get(did, src_date) or "", sec, raw_name, cnt, url])

    with open(os.path.join(OUT, "deck_stats.csv"),"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["deck_id","date","source_url","pokemon","goods","tools","supporter","stadium","energy","total_cards"]); w.writeheader(); w.writerows(all_stats)

    with open(os.path.join(OUT, "ace_spec_stats.csv"),"w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(["deck_id","ace_spec_name_jp","source_url","count"]); w.writerows(ace_occurrences)

    print("\n=== 下載建議牌組卡片圖檔（不重複）並生成拼圖 ===")
    img_dir = os.path.join(OUT, 'suggested_images')
    collage_dir = os.path.join(OUT, 'collage')
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(collage_dir, exist_ok=True)

    from collections import OrderedDict
    uniq: "OrderedDict[str, Dict[str, any]]" = OrderedDict()
    for cat, name, copies, url in suggested:
        key = url or f"NAME::{normalize_name(name)}"
        if key not in uniq:
            uniq[key] = {"name": name, "url": url, "copies": 0}
        uniq[key]["copies"] += int(copies)

    # 以 ThreadPool 併發下載圖片
    url_to_local: Dict[str, str] = {}

    def _prepare_and_download(item):
        key, info = item
        name, u = info.get("name"), info.get("url")
        img_u = get_card_image_url_http(u) if u else None
        if img_u and img_u.startswith('/'):
            img_u = BASE + img_u
        safe = _safe_filename(name)
        cid = ""
        try:
            m = re.search(r"/card/(\d+)", u or "")
            if m:
                cid = m.group(1)
        except Exception:
            cid = ""
        # 避免不同名稱同 cid 或同名不同 cid 衝突，附上 key 的短雜湊
        short_hash = hex(abs(hash(key)) & 0xFFFF)[2:]
        fname = f"{cid+'_' if cid else ''}{safe}_{short_hash}.jpg"
        out_path = os.path.join(img_dir, fname)
        if img_u and not os.path.exists(out_path):
            ok = download_image(img_u, out_path)
            if not ok:
                try:
                    from PIL import Image, ImageDraw
                    im = Image.new('RGB', (300, 420), (230, 230, 230))
                    d = ImageDraw.Draw(im)
                    d.text((10, 10), (safe or 'card')[:20], fill=(60,60,60))
                    im.save(out_path)
                except Exception:
                    open(out_path, 'wb').close()
        elif not os.path.exists(out_path):
            try:
                from PIL import Image, ImageDraw
                im = Image.new('RGB', (300, 420), (230, 230, 230))
                d = ImageDraw.Draw(im)
                d.text((10, 10), (safe or 'card')[:20], fill=(60,60,60))
                im.save(out_path)
            except Exception:
                open(out_path, 'wb').close()
        return key, out_path

    items = list(uniq.items())
    if items:
        workers = max(1, min(IMG_DOWNLOAD_THREADS, len(items)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for key, out_path in ex.map(_prepare_and_download, items):
                url_to_local[key] = out_path

    image_paths: List[str] = []
    labels: List[str] = []
    for key, info in uniq.items():
        image_paths.append(url_to_local.get(key, ""))
        n = int(info.get("copies", 0))
        # Also mark single-copy cards as x1 (previously left blank)
        labels.append(f"x{n}" if n >= 1 else "")

    import math
    n_cards = max(1, len(image_paths))
    cols = 8
    rows = math.ceil(n_cards / cols)
    collage_path = os.path.join(collage_dir, f'suggested_unique_{n_cards}.jpg')
    made = make_collage(image_paths, cols=cols, rows=rows, cell_w=300, cell_h=420, out_path=collage_path, labels=labels)
    if made:
        print(f"拼圖已輸出（唯一卡片 {n_cards} 張）：{made}")
    else:
        print("未能產生拼圖（可能缺少 Pillow）。仍已下載個別圖片於 output/suggested_images/")

    # ===== 依日期輸出建議牌組（CSV + 拼貼） =====
    date_to_dids = {}
    for s in all_stats:
        d = s.get("date")
        if not d:
            continue
        date_to_dids.setdefault(d, set()).add(s.get("deck_id"))

    from collections import OrderedDict
    for d, dids in sorted(date_to_dids.items()):
        if not dids:
            continue
        cats2 = ["pokemon","goods","tools","supporter","stadium","energy"]
        if d in date_totals:
            totals2 = date_totals[d]
            decks2  = date_decks[d]
            primary2= date_primary[d]
            allurls2= date_allurls[d]
            display2= date_display[d]
        else:
            totals2 = {c:{} for c in cats2}
            decks2  = {c:{} for c in cats2}
            primary2= {c:{} for c in cats2}
            allurls2= {c:{} for c in cats2}
            display2= {c:{} for c in cats2}

        sub_stats = [s for s in all_stats if s.get("deck_id") in dids]
        n_sub = len(sub_stats)
        sums2 = {c:0 for c in cats2}
        for s in sub_stats:
            for c in cats2:
                sums2[c] += s[c]
        avgs2 = {c: (sums2[c]/n_sub if n_sub else 0.0) for c in cats2}
        targets2 = round_targets_to_60(avgs2)
        print(f"\n=== [日期 {d}] 分析摘要 ===")
        print(f"牌組數：{n_sub}")
        for cat in cats2:
            print(f"  {cat}: 平均 {avgs2.get(cat, 0.0):.2f} 張")
        if n_sub > 0:
            print(f"  使用率過濾條件：至少 {SUGGEST_MIN_DECKS} 副、{SUGGEST_MIN_USAGE_RATE:.1%} 使用率")
        print(f"--- [日期 {d}] 各類熱門卡片 Top3（依 avg_overall） ---")
        for cat in cats2:
            items = []
            for norm_name, total_cnt in totals2[cat].items():
                avg_overall = (total_cnt / n_sub) if n_sub else 0.0
                decks_with_card = len(decks2[cat].get(norm_name, set()))
                disp = display2[cat].get(norm_name, norm_name)
                url = primary2[cat].get(norm_name, "")
                items.append((avg_overall, decks_with_card, disp, url))
            if not items:
                print(f"[{cat}] 無資料")
                continue
            items.sort(key=lambda x: x[0], reverse=True)
            top_items = items[:3]
            print(f"[{cat}]")
            for avg_overall, decks_with_card, disp, url in top_items:
                link = url or "（無官方連結）"
                print(f"  {disp}：平均 {avg_overall:.2f} 張，出現於 {decks_with_card} 副牌組 -> {link}")

        sug2 = build_suggested_deck(targets2, totals2, decks2, primary2, display2, n_sub,
                                    ace_jp_norm_names, USE_ACE_SPEC)
        sug2, _ = enforce_ace_spec_policy(sug2, ace_jp_norm_names, USE_ACE_SPEC, FORCE_ACE_SPEC_NAME,
                                          totals2, decks2, primary2, display2, n_sub, ace_targets_raw)
        sug2 = _final_strict_name_cap(sug2, ace_jp_norm_names)
        print(f"\n=== [日期 {d}] 建議牌組（目標 60 張） ===")
        cat_totals2 = {c: 0 for c in cats2}
        total_cards2 = 0
        for cat, name, copies, _ in sug2:
            cat_totals2[cat] = cat_totals2.get(cat, 0) + int(copies)
            total_cards2 += int(copies)
        for cat in cats2:
            block_cards = [(c, n, int(k), u) for (c, n, k, u) in sug2 if c == cat]
            if not block_cards:
                continue
            print(f"[{cat}]（小計 {cat_totals2.get(cat, 0)} 張）")
            for _, name, copies, url in block_cards:
                link = url or "（無官方連結）"
                print(f"  {name} × {copies}  -> {link}")
        print(f"總計：{total_cards2} 張")

        csv_path = os.path.join(OUT, f"suggested_deck__date_{d}.csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["category","card_name_jp","copies","urls"])
            for cat,name,copies,url in sug2:
                norm = normalize_name(name)
                norm = apply_manual_aliases(norm, '')
                url_set = allurls2.get(cat, {}).get(norm, set())
                if url_set:
                    parts = [f'=HYPERLINK("{u}","link{idx+1}")' for idx, u in enumerate(sorted(url_set))]
                    urls_formula = parts[0] if len(parts)==1 else ("=" + "&\" | \"&".join(parts))
                else:
                    urls_formula = ""
                w.writerow([cat,name,copies,urls_formula])

        # 拼貼圖（每日期）
        uniq2 = OrderedDict()
        for cat,name,copies,url in sug2:
            key = url or f"NAME::{normalize_name(name)}"
            if key not in uniq2:
                uniq2[key] = {"name": name, "url": url, "copies": 0}
            uniq2[key]["copies"] += int(copies)
        url_to_local2 = {}
        def _dl(item):
            key, info = item
            name, u = info.get("name"), info.get("url")
            img_u = get_card_image_url_http(u) if u else None
            if img_u and img_u.startswith('/'):
                img_u = BASE + img_u
            safe = _safe_filename(name)
            short_hash = hex(abs(hash(key)) & 0xFFFF)[2:]
            fname = f"{safe}_{short_hash}_{d}.jpg"
            out_path = os.path.join(img_dir, fname)
            if img_u and not os.path.exists(out_path):
                ok = download_image(img_u, out_path)
                if not ok:
                    try:
                        from PIL import Image, ImageDraw
                        im = Image.new('RGB', (300, 420), (230, 230, 230))
                        d2 = ImageDraw.Draw(im)
                        d2.text((10, 10), (safe or 'card')[:20], fill=(60,60,60))
                        im.save(out_path)
                    except Exception:
                        open(out_path, 'wb').close()
            elif not os.path.exists(out_path):
                try:
                    from PIL import Image, ImageDraw
                    im = Image.new('RGB', (300, 420), (230, 230, 230))
                    d2 = ImageDraw.Draw(im)
                    d2.text((10, 10), (safe or 'card')[:20], fill=(60,60,60))
                    im.save(out_path)
                except Exception:
                    open(out_path, 'wb').close()
            return key, out_path
        items = list(uniq2.items())
        if items:
            workers = max(1, min(IMG_DOWNLOAD_THREADS, len(items)))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for key, out_path in ex.map(_dl, items):
                    url_to_local2[key] = out_path
        image_paths = []
        labels = []
        for key, info in uniq2.items():
            image_paths.append(url_to_local2.get(key, ""))
            n = int(info.get("copies", 0))
            labels.append(f"x{n}" if n >= 1 else "")
        import math as _m
        n_cards = max(1, len(image_paths))
        cols = 8
        rows = _m.ceil(n_cards / cols)
        collage_path_d = os.path.join(collage_dir, f'suggested_unique__date_{d}_{n_cards}.jpg')
        _ = make_collage(image_paths, cols=cols, rows=rows, cell_w=300, cell_h=420, out_path=collage_path_d, labels=labels)
        print(f"[日期 {d}] 已輸出：{csv_path} 與拼貼 {collage_path_d}")

def main_wrapper():
    # Print start timestamp as the very first output of main flow
    try:
        _start_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        _start_ts = ""
    print(f"Start Time: {_start_ts}")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sources = POKECABOOK_SOURCES if 'POKECABOOK_SOURCES' in globals() else []
    if (not sources) and ('POKECABOOK_URL' in globals()) and POKECABOOK_URL:
        sources = [POKECABOOK_URL]
    if not sources:
        print("[warn] 未設定來源網址（POKECABOOK_SOURCES/POKECABOOK_URL）")
        return
    # 多來源：可平行處理
    max_workers = min(MAX_SOURCE_PROCS, len(sources)) if MAX_SOURCE_PROCS and len(sources) > 0 else 1
    if max_workers > 1:
        print(f"並行處理來源：{len(sources)}（workers={max_workers}）")
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(analyze_source, sources))
    else:
        for src in sources:
            analyze_source(src)


def _final_strict_name_cap(suggested, ace_norm_names:set):
    """
    Final strict check:
    - Cap total copies per normalized name (non-basic energy) to 4.
    - Trim from the end, prefer trimming non-energy and non-ACE cards.
    - Convert trimmed copies into basic energy to keep 60.
    """
    # Aggregate totals per normalized name
    name_totals = {}
    for _, name, copies, _ in suggested:
        n = normalize_name(name)
        if not is_basic_energy(name):
            name_totals[n] = name_totals.get(n, 0) + copies

    energy_restore = 0
    # Fix violators
    for nname, total in list(name_totals.items()):
        if total <= 4:
            continue
        over = total - 4
        i = len(suggested) - 1
        while over > 0 and i >= 0:
            cat, name, copies, url = suggested[i]
            if normalize_name(name) == nname and not is_basic_energy(name):
                is_ace = any(a in normalize_name(name) for a in ace_norm_names)
                min_left = 1 if is_ace else 0
                dec = min(copies - min_left, over) if copies > min_left else 0
                if dec > 0:
                    new_copies = copies - dec
                    energy_restore += dec
                    if new_copies > 0:
                        suggested[i] = (cat, name, new_copies, url)
                    else:
                        suggested.pop(i)
                    over -= dec
            i -= 1

    # Convert trimmed copies into energy
    if energy_restore > 0:
        placed = False
        for j, (cat, name, copies, url) in enumerate(suggested):
            if cat == "energy":
                suggested[j] = (cat, name, copies + energy_restore, url)
                placed = True
                break
        if not placed:
            suggested.append(("energy", "基本エネルギー", energy_restore, ""))

    # Verify again and hard cap if still violated (edge cases)
    chk = {}
    for _, name, copies, _ in suggested:
        n = normalize_name(name)
        if not is_basic_energy(name):
            chk[n] = chk.get(n, 0) + copies
    violators = [k for k,v in chk.items() if v > 4]
    if violators:
        extra = 0
        for bad in violators:
            need = chk[bad] - 4
            i = len(suggested) - 1
            while need > 0 and i >= 0:
                cat, name, copies, url = suggested[i]
                if normalize_name(name) == bad and not is_basic_energy(name):
                    dec = min(copies, need)
                    copies -= dec
                    extra += dec
                    if copies > 0:
                        suggested[i] = (cat, name, copies, url)
                    else:
                        suggested.pop(i)
                    need -= dec
                i -= 1
        if extra > 0:
            placed = False
            for j, (cat, name, copies, url) in enumerate(suggested):
                if cat == "energy":
                    suggested[j] = (cat, name, copies + extra, url)
                    placed = True
                    break
            if not placed:
                suggested.append(("energy", "基本エネルギー", extra, ""))

    # Ensure total = 60
    tot = sum(c for _, _, c, _ in suggested)
    if tot < 60:
        missing = 60 - tot
        placed = False
        for j, (cat, name, copies, url) in enumerate(suggested):
            if cat == "energy":
                suggested[j] = (cat, name, copies + missing, url)
                placed = True
                break
        if not placed:
            suggested.append(("energy", "基本エネルギー", missing, ""))
    elif tot > 60:
        over = tot - 60
        i = len(suggested) - 1
        while over > 0 and i >= 0:
            cat, name, copies, url = suggested[i]
            is_ace = any(a in normalize_name(name) for a in ace_norm_names)
            if cat != "energy" and not is_ace and copies > 0:
                dec = min(copies, over)
                copies -= dec
                if copies > 0:
                    suggested[i] = (cat, name, copies, url)
                else:
                    suggested.pop(i)
                over -= dec
            i -= 1
        if over > 0:
            i = len(suggested) - 1
            while over > 0 and i >= 0:
                cat, name, copies, url = suggested[i]
                if cat == "energy" and copies > 0:
                    dec = min(copies, over)
                    copies -= dec
                    if copies > 0:
                        suggested[i] = (cat, name, copies, url)
                    else:
                        suggested.pop(i)
                    over -= dec
                i -= 1
    return suggested

if __name__=="__main__":
    if sys.maxsize <= 2**32:
        print("⚠ 建議用 64 位元 Python")
    main_wrapper()










