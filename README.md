# Deck Analyzer / ACE SPEC Crawler

以台灣繁體中文撰寫的專案說明，協助從文章頁面蒐集寶可夢卡牌牌組、統計常見用牌，並輸出一份示範「60 張建議牌組」。另含「ACE SPEC」卡表爬蟲腳本，方便建立/比對 ACE SPEC 清單。

---

## 功能總覽
- 從來源文章頁（例如 Pokecabook）擷取多個 `deckID`，逐一開啟官方牌表頁抓取卡名/張數。
- 計算各類別平均張數、各卡片平均張數與使用率，並依此產生「60 張建議牌組」。
- 依 ACE 規則：可關閉 ACE、或強制指定 1 張 ACE、或啟用自動挑選 1 張 ACE。
- 下載建議牌組中不重複的卡圖，並嘗試合成拼圖（需安裝 Pillow）。
- 匯出多份 CSV（UTF-8 with BOM）供 Excel/Google 試算表使用，內含 HYPERLINK 便於點擊回原始網址。
- ACE SPEC 爬蟲支援關鍵字搜尋、翻頁、數量上限、輸出 CSV/JSON，並下載卡圖縮圖。

## 專案結構
- `deck_analyzer.py`：主流程（抓牌組 → 統計 → 產生建議 60 張 → 輸出 CSV 與圖片拼圖）。
- `ace_spec_crawler.py`：ACE SPEC 卡片爬蟲（Selenium + requests/BeautifulSoup 輔助）。
- `debug_ace_spec.bat`：Windows 便利批次檔，用於快速執行 `ace_spec_crawler.py` 的除錯流程。
- `output/`：輸出資料夾（首次執行會自動建立）。

## 環境需求
- Python 3.9+（建議 64 位元）
- Google Chrome（Selenium 透過 webdriver-manager 自動管理 chromedriver）
- 套件：
  - 必要：`selenium`、`webdriver-manager`、`beautifulsoup4`、`requests`、`lxml`
  - 選用（產生拼圖）：`Pillow`

安裝範例：
```
pip install selenium webdriver-manager beautifulsoup4 requests lxml pillow
```

## 使用方式（牌組分析）
1) 設定來源網址
- 編輯 `deck_analyzer.py` 內的變數（靠近檔案前段）：
  - `POKECABOOK_SOURCES`: List[str] 多個來源頁面（建議）。
  - 或以單一 `POKECABOOK_URL` 指定一頁。

2) 重要可調參數（檔案 `deck_analyzer.py`）
- 類別與 ACE：
  - `USE_ACE_SPEC: bool` 啟用/停用 ACE（啟用時會保留恰好 1 張）。
  - `FORCE_ACE_SPEC_NAME: Optional[str]` 指定 ACE 名稱（例如日文卡名），空值 = 不強制。
  - `ACE_SPEC_LIST: List[Tuple[str, str]]` ACE 名稱與官方網址清單（偵測與提示會以此為準）。
- 來源/數量/日期：
  - `RECENT_DECKS_LIMIT: int | None` 每來源最多統計幾個 deckID；None = 全部。
  - `ANALYZE_DATE_FROM`、`ANALYZE_DATE_TO`（`YYYY-MM-DD` 或 None）限制來源日期區間。
- 牌名過濾：
  - `FILTER_CARD_KEYWORDS: List[str]` 只分析含特定關鍵字的牌組（空陣列=不過濾）。
  - `FILTER_REQUIRE_ALL: bool` True=需全部關鍵字都符合；False=任一符合即可。
- 建議牌組門檻：
  - `SUGGEST_MIN_USAGE_RATE: float` 卡片納入候選的最低「使用率」。
  - `SUGGEST_MIN_DECKS: int` 卡片至少出現於多少副牌組才納入候選。
- 快取與效能：
  - `USE_SQLITE_CACHE`, `USE_URL_NAME_CACHE`, `REFRESH_CACHE`, `CLEAR_CACHE_ON_DISABLE`
  - `MAX_SOURCE_PROCS`（多來源並行處理數）、`IMG_DOWNLOAD_THREADS`（下載卡圖 Thread 數）

3) 執行
```
python deck_analyzer.py
```

4) 主要輸出（每個來源各自分目錄 `output/src_<safe_tag>/`）
- `suggested_deck.csv`：建議 60 張牌組（含多鏈結 HYPERLINK）。
- `decks_parsed.csv`：逐張展開的原始解析結果（deck_id / 區段 / 卡名 / 張數 / 連結）。
- `deck_stats.csv`：每副牌組的類別統計（pokemon/goods/tools/supporter/stadium/energy/total）。
- `ace_spec_stats.csv`：ACE SPEC 出現紀錄（deck_id / 名稱 / 連結 / 張數）。
- `card_usage_summary.csv`：各卡平均張數與出現副數彙整。
- `suggested_images/`：建議牌組不重複卡圖下載。
- `collage/`：若安裝 Pillow，輸出建議牌組的拼圖 JPG。

5) 常見訊息
- 未安裝 Pillow：僅下載個別卡圖；不會輸出拼圖，終端機會提示安裝指令。
- 非基本能量張數上限：流程會在最後套用「4 張上限」（ACE 卡至少保留 1）。

## 使用方式（ACE SPEC 爬蟲）
基本範例：
```
python ace_spec_crawler.py --keyword "ACE SPEC" --pages 2 --limit 20 --headless --format both
```
參數：
- `--keyword` 預設「ACE SPEC」。
- `--pages` 最多翻頁數（預設 10）。
- `--limit` 最多點開卡片數（0=不限制）。
- `--headless` 隱藏瀏覽器視窗。
- `--debug-stop-after-step2` 在「輸入關鍵字」後停住，用於手動觀察。
- `--keep-browser-open` 搭配 debug，保留瀏覽器不關閉。
- `--out` 輸出檔名前綴（預設 `output/ace_spec_catalog`）。
- `--format` `csv`/`json`/`both`（預設 both）。

Windows 快速測試：
```
debug_ace_spec.bat
```
會互動詢問關鍵字（預設 ACE SPEC），並以 debug 模式執行。

輸出內容：
- CSV 欄位：`name_jp, type, url, image_url, local_image`
- JSON：同欄位結構陣列；圖片另下載至 `output/ace_images/`

## 疑難排解
- 無法自動開啟瀏覽器：請確認已安裝 Chrome，或網路可下載驅動（webdriver-manager）。
- Windows 終端機亂碼：請確保使用 UTF-8（PowerShell 建議使用 Windows Terminal 或切換為 UTF-8 編碼）。
- 目標網站結構更動：若解析失敗，請回報來源網址與錯誤訊息，以便調整選擇器與規則。
- 需求套件缺漏：請比照上方 pip 安裝指令安裝；拼圖功能需 `Pillow`。

## 開發提示
- `deck_analyzer.py:1500` 起有主程式入口；執行時會印出流程與輸出路徑。
- 可依需求調整常數與規則（類別對應、名稱正規化、ACE 規則、門檻值）。
- 變更前建議以小型來源測試，觀察輸出 CSV 是否符合預期。

---

若你要我幫忙修改參數、加入新來源或執行一次產出，請告訴我來源網址與偏好設定（是否使用 ACE、門檻、日期範圍等）。

