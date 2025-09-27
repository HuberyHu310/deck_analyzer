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
                new_list.append(("energy","基本?????", removed, ""))
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
                new_list.append(("energy","基本?????", restored, ""))
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
