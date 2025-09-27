import unittest

from deck_analyzer import (
    normalize_name,
    build_suggested_deck,
    round_targets_to_60,
)


class TestSingleDeckSuggestion(unittest.TestCase):
    def test_single_deck_should_clone(self):
        # 準備：只有一副牌組的卡片清單（section, raw_name, cnt, url）
        # 類別合計：pokemon15 + goods15 + tools3 + supporter12 + stadium3 + energy12 = 60
        deck_id = "TEST-DECK-1"
        cards = [
            # Pokemon 15
            ("ポケモン", "リオル M1L 028/063", 3, "https://example/riolu"),
            ("ポケモン", "メガルカリオex M1L 029/063", 3, "https://example/lucario"),
            ("ポケモン", "ハリテヤマ M1L 025/063", 2, "https://example/hariteyama"),
            ("ポケモン", "ソルロック M1L 027/063", 2, "https://example/solrock"),
            ("ポケモン", "マクノシタ M1L 024/063", 3, "https://example/makunosita"),
            ("ポケモン", "ルナトーン M1L 026/063", 2, "https://example/lunatone"),
            # Goods 15
            ("グッズ", "パワープロテイン", 4, "https://example/power-protein"),
            ("グッズ", "ファイトゴング", 4, "https://example/fight-gong"),
            ("グッズ", "ハイパーボール", 4, "https://example/hyper-ball"),
            ("グッズ", "夜のタンカ", 3, "https://example/night-rescue"),
            # Tools 3
            ("ポケモンのどうぐ", "ふうせん", 2, "https://example/air-balloon"),
            ("ポケモンのどうぐ", "マキシマムベルト(ACE SPEC)", 1, "https://example/maximum-belt"),
            # Supporter 12
            ("サポート", "リーリエの決心", 4, "https://example/lillie"),
            ("サポート", "博士の研究", 3, "https://example/professor-research"),
            ("サポート", "ナンジャモ", 2, "https://example/nanjamo"),
            ("サポート", "フトゥー博士のシナリオ", 2, "https://example/ftwo"),
            ("サポート", "ボスの指令", 1, "https://example/boss-order"),
            # Stadium 3
            ("スタジアム", "ボウルタウン", 2, "https://example/bowl-town"),
            ("スタジアム", "タウンデパート", 1, "https://example/town-dept"),
            # Energy 12
            ("エネルギー", "基本闘エネルギー", 10, "https://example/basic-fighting"),
            ("エネルギー", "リバーサルエネルギー", 2, "https://example/reversal"),
        ]

        cats = ["pokemon", "goods", "tools", "supporter", "stadium", "energy"]
        # 聚合結構（模擬只有一副牌組的統計結果）
        card_totals = {c: {} for c in cats}
        card_decks = {c: {} for c in cats}
        name_primary_url = {c: {} for c in cats}
        name_display = {c: {} for c in cats}
        per_cat_sum = {c: 0 for c in cats}

        # 映射 section -> category 的最小化版本（直接用關鍵字包含）
        def to_cat(sec):
            s = sec or ""
            if "ポケモンのどうぐ" in s:
                return "tools"
            if "グッズ" in s:
                return "goods"
            if "サポート" in s:
                return "supporter"
            if "スタジアム" in s:
                return "stadium"
            if "エネルギー" in s:
                return "energy"
            if "ポケモン" in s:
                return "pokemon"
            return None

        for sec, raw_name, cnt, url in cards:
            cat = to_cat(sec)
            assert cat in cats
            per_cat_sum[cat] += cnt
            norm = normalize_name(raw_name)
            card_totals[cat][norm] = card_totals[cat].get(norm, 0) + cnt
            card_decks[cat].setdefault(norm, set()).add(deck_id)
            name_display[cat].setdefault(norm, raw_name)
            if url:
                name_primary_url[cat].setdefault(norm, url)

        total_decks = 1
        # 依單副牌組的類別合計算平均（皆為整數）並產生目標分配
        avg_counts = {k: per_cat_sum[k] / total_decks for k in cats}
        targets = round_targets_to_60(avg_counts)

        # 不啟用 ACE 強制定義（保持與原牌組一致）
        ace_names = {normalize_name("マキシマムベルト(ACE SPEC)")}  # 提供 ACE 名稱集合（避免被過濾）
        suggested = build_suggested_deck(
            targets,
            card_totals,
            card_decks,
            name_primary_url,
            name_display,
            total_decks,
            ace_names,
            use_ace_spec=True,
        )

        # 轉為「類別 -> 名稱 -> 張數」比較（使用 normalize_name）
        def to_map(card_list):
            out = {c: {} for c in cats}
            for sec, raw_name, cnt, _ in card_list:
                cat = to_cat(sec)
                out[cat][normalize_name(raw_name)] = out[cat].get(normalize_name(raw_name), 0) + cnt
            return out

        expected_map = to_map(cards)
        got_map = {c: {} for c in cats}
        for cat, name, cnt, _ in suggested:
            n = normalize_name(name)
            got_map[cat][n] = got_map[cat].get(n, 0) + cnt

        # 類別合計與逐名張數須完全一致
        for c in cats:
            if sum(expected_map[c].values()) != sum(got_map[c].values()):
                print("EXPECTED TOTAL", c, expected_map[c])
                print("GOT TOTAL", c, got_map[c])
            assert sum(expected_map[c].values()) == sum(got_map[c].values()), f"category total mismatch: {c}"
            if expected_map[c] != got_map[c]:
                print("EXPECTED", c, expected_map[c])
                print("GOT", c, got_map[c])
            assert expected_map[c] == got_map[c], f"per-name mismatch in category: {c}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
