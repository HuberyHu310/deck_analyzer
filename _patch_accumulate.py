import io, os, sys
p = r"deck_analyzer.py"
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()
anchor_after = "save_cached_deck(did, cards, stats)"
next_anchor = "if not filter_deck_by_cards(cards, FILTER_CARD_KEYWORDS, FILTER_REQUIRE_ALL):"
pos1 = s.find(anchor_after)
if pos1 == -1:
    print('anchor_after not found'); sys.exit(1)
pos2 = s.find(anchor_after, pos1 + 1)
if pos2 != -1:
    insert_after_pos = pos2 + len(anchor_after)
else:
    insert_after_pos = pos1 + len(anchor_after)
pos_filter = s.find(next_anchor, insert_after_pos)
if pos_filter == -1:
    print('next_anchor not found'); sys.exit(1)
block = """

                # --------- 累積全域統計與每日統計 ---------
                try:
                    ddate = deck_date_map.get(did) or \"未知\"
                    # 每副牌組的彙總（後續輸出 CSV 與分析使用）
                    stats_row = {
                        \"deck_id\": did,
                        \"date\": ddate,
                        \"source_url\": src,
                        \"pokemon\": int(stats.get(\"pokemon\", 0)),
                        \"goods\": int(stats.get(\"goods\", 0)),
                        \"tools\": int(stats.get(\"tools\", 0)),
                        \"supporter\": int(stats.get(\"supporter\", 0)),
                        \"stadium\": int(stats.get(\"stadium\", 0)),
                        \"energy\": int(stats.get(\"energy\", 0)),
                        \"total_cards\": int(stats.get(\"total_cards\", 0)),
                    }
                    all_stats.append(stats_row)

                    # 初始化每日容器
                    if ddate not in date_totals:
                        date_totals[ddate] = {c: {} for c in cats}
                        date_decks[ddate]  = {c: {} for c in cats}
                        date_primary[ddate]= {c: {} for c in cats}
                        date_allurls[ddate]= {c: {} for c in cats}
                        date_display[ddate]= {c: {} for c in cats}

                    # 逐卡片更新統計
                    found_aces = []
                    for sec, raw_name, cnt, url in (cards or []):
                        cat = section_to_category(sec)
                        if not cat or cat not in cats:
                            continue
                        norm_name = normalize_name(raw_name)
                        # 全部統計
                        card_totals[cat][norm_name] = card_totals[cat].get(norm_name, 0) + int(cnt or 0)
                        deckset = card_decks[cat].setdefault(norm_name, set())
                        deckset.add(did)
                        if norm_name not in name_primary_url[cat] and url:
                            name_primary_url[cat][norm_name] = url
                        name_all_urls[cat].setdefault(norm_name, set())
                        if url:
                            name_all_urls[cat][norm_name].add(url)
                        name_display[cat].setdefault(norm_name, raw_name)

                        # 每日統計
                        date_totals[ddate][cat][norm_name] = date_totals[ddate][cat].get(norm_name, 0) + int(cnt or 0)
                        ddeckset = date_decks[ddate][cat].setdefault(norm_name, set())
                        ddeckset.add(did)
                        if norm_name not in date_primary[ddate][cat] and url:
                            date_primary[ddate][cat][norm_name] = url
                        if norm_name not in date_allurls[ddate][cat]:
                            date_allurls[ddate][cat][norm_name] = set()
                        if url:
                            date_allurls[ddate][cat][norm_name].add(url)
                        date_display[ddate][cat].setdefault(norm_name, raw_name)

                        # ACE SPEC 偵測（名稱包含 ACE 規則關鍵詞）
                        nname = normalize_name(raw_name)
                        if any(ace in nname for ace in ace_jp_norm_names):
                            ace_occurrences.append([did, nname, src, int(cnt or 0)])
                            for ace_key in ace_jp_norm_names:
                                if ace_key in nname:
                                    ace_deck_sets[ace_key].add(did)
                                    if nname not in found_aces:
                                        found_aces.append(nname)

                    # 每副完成列印（日期在前）
                    if found_aces:
                        print(f\"✓ [{ddate}] {did} 完成：{stats} ｜ 找到 ACE SPEC: {found_aces}\")
                    else:
                        print(f\"✓ [{ddate}] {did} 完成：{stats}\")
                except Exception as e:
                    # 不因統計列印失敗而中斷主流程
                    print(f\"[warn] 累積或列印統計時發生例外：{e}\")
"""
ns = s[:insert_after_pos] + block + s[insert_after_pos:]
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(ns)
print('INSERTED')
