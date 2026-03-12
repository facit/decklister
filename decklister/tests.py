import pytest
from .card_sizer import CardSizer
from .deck import Deck, Card


# ---- CardSizer Tests ----

class TestCardSizer:
    def test_zero_cards_returns_none(self):
        result = CardSizer.calculate((0, 0, 1000, 1000), 0)
        assert result is None

    def test_negative_cards_returns_none(self):
        result = CardSizer.calculate((0, 0, 1000, 1000), -5)
        assert result is None

    def test_zero_area_returns_none(self):
        result = CardSizer.calculate((100, 100, 100, 100), 10)
        assert result is None

    def test_single_card_fills_area(self):
        w, h, cols, rows, pad = CardSizer.calculate((0, 0, 500, 700), 1)
        assert cols == 1
        assert rows == 1
        assert w > 0 and h > 0
        assert w <= 500 and h <= 700

    def test_aspect_ratio_maintained(self):
        w, h, cols, rows, pad = CardSizer.calculate((0, 0, 1000, 1000), 4)
        ratio = w / h
        expected = 5.0 / 7.0
        assert abs(ratio - expected) < 0.05  # Allow small rounding error

    def test_more_cards_means_smaller_size(self):
        w1, h1, _, _, _ = CardSizer.calculate((0, 0, 1000, 1000), 4)
        w2, h2, _, _, _ = CardSizer.calculate((0, 0, 1000, 1000), 20)
        assert w1 > w2
        assert h1 > h2

    def test_all_cards_fit(self):
        """Verify cols * rows >= card_count."""
        for count in [1, 5, 10, 20, 50]:
            result = CardSizer.calculate((0, 0, 1920, 1080), count)
            assert result is not None
            w, h, cols, rows, pad = result
            assert cols * rows >= count

    def test_cards_fit_within_area(self):
        """Verify total grid doesn't exceed the area."""
        area = (100, 50, 900, 750)
        count = 12
        w, h, cols, rows, pad = CardSizer.calculate(area, count, padding=5)
        avail_w = area[2] - area[0]
        avail_h = area[3] - area[1]
        total_w = cols * w + (cols - 1) * 5
        total_h = rows * h + (rows - 1) * 5
        assert total_w <= avail_w
        assert total_h <= avail_h

    def test_custom_aspect_ratio(self):
        w, h, _, _, _ = CardSizer.calculate((0, 0, 1000, 1000), 1, aspect_ratio=1.0)
        assert abs(w - h) <= 1  # Should be roughly square


# ---- Deck Parsing Tests ----

class TestDeckParsing:
    def test_legacy_format_single_leader(self):
        data = {
            "leader": {"id": "SHD_009", "count": 1},
            "base": {"id": "SOR_030", "count": 1},
            "deck": [{"id": "SEC_068", "count": 3}],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert len(deck.leaders) == 1
        assert deck.leaders[0].card_set == "SHD"
        assert len(deck.bases) == 1
        assert len(deck.main_deck) == 1
        assert deck.main_deck[0].count == 3

    def test_legacy_format_two_leaders(self):
        data = {
            "leader": {"id": "SHD_009", "count": 1},
            "secondleader": {"id": "JTL_003", "count": 1},
            "base": {"id": "SOR_030", "count": 1},
            "deck": [],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert len(deck.leaders) == 2

    def test_list_format_leaders(self):
        data = {
            "leaders": [
                {"id": "SHD_009", "count": 1},
                {"id": "JTL_003", "count": 1},
            ],
            "bases": [{"id": "SOR_030", "count": 1}],
            "deck": [],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert len(deck.leaders) == 2
        assert len(deck.bases) == 1

    def test_list_format_multiple_bases(self):
        data = {
            "leaders": [],
            "bases": [
                {"id": "SOR_030", "count": 1},
                {"id": "SOR_031", "count": 1},
            ],
            "deck": [],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert len(deck.bases) == 2

    def test_conflict_leaders_raises(self):
        data = {
            "leaders": [{"id": "SHD_009"}],
            "leader": {"id": "JTL_003"},
            "deck": [],
            "sideboard": [],
        }
        with pytest.raises(ValueError, match="cannot contain both"):
            Deck.from_json(data)

    def test_conflict_bases_raises(self):
        data = {
            "bases": [{"id": "SOR_030"}],
            "base": {"id": "SOR_031"},
            "deck": [],
            "sideboard": [],
        }
        with pytest.raises(ValueError, match="cannot contain both"):
            Deck.from_json(data)

    def test_metadata_parsed(self):
        data = {
            "metadata": {"name": "My Deck", "author": "me"},
            "leaders": [],
            "bases": [],
            "deck": [],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert deck.metadata["name"] == "My Deck"

    def test_empty_deck(self):
        data = {"deck": [], "sideboard": []}
        deck = Deck.from_json(data)
        assert len(deck.leaders) == 0
        assert len(deck.bases) == 0
        assert len(deck.main_deck) == 0
        assert len(deck.sideboard) == 0

    def test_default_count_is_one(self):
        data = {
            "deck": [{"id": "SEC_068"}],
            "sideboard": [],
        }
        deck = Deck.from_json(data)
        assert deck.main_deck[0].count == 1


# ---- Variant Resolver Tests ----

from .variant_resolver import resolve_variant

class TestVariantResolver:
    def test_no_variants_returns_original(self):
        assert resolve_variant("SOR", "10") == "10"

    def test_hyperspace_known_set(self):
        # SOR has 252 base cards, so hyperspace for card 10 = 10 + 252 = 262
        assert resolve_variant("SOR", "10", hyperspace=True) == "262"

    def test_hyperspace_different_set(self):
        # SHD has 262 base cards, so hyperspace for card 5 = 5 + 262 = 267
        assert resolve_variant("SHD", "5", hyperspace=True) == "267"

    def test_showcase_leader(self):
        # SOR: showcase for leader 3 = 4*252 - 52 + 3 = 959
        assert resolve_variant("SOR", "3", showcase=True) == "959"

    def test_showcase_non_leader_no_change(self):
        # Card 50 is not a leader (1-18), so showcase has no effect
        assert resolve_variant("SOR", "50", showcase=True) == "50"

    def test_showcase_overrides_hyperspace_for_leaders(self):
        # Leader card with both flags: showcase wins
        result = resolve_variant("SOR", "5", hyperspace=True, showcase=True)
        expected_showcase = str(4 * 252 - 52 + 5)
        assert result == expected_showcase

    def test_hyperspace_still_applies_to_non_leaders_with_showcase(self):
        # Non-leader card with both flags: hyperspace applies
        result = resolve_variant("SOR", "50", hyperspace=True, showcase=True)
        expected_hyperspace = str(50 + 252)
        assert result == expected_hyperspace

    def test_unknown_set_returns_original(self):
        assert resolve_variant("XYZ", "10", hyperspace=True) == "10"
        assert resolve_variant("XYZ", "5", showcase=True) == "5"

    def test_leader_boundary(self):
        # Card 18 is the last leader
        assert resolve_variant("SOR", "18", showcase=True) == str(4 * 252 - 52 + 18)
        # Card 19 is not a leader
        assert resolve_variant("SOR", "19", showcase=True) == "19"
