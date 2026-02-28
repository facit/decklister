import json


class Card:
    def __init__(self, card_json):
        card_id = card_json.get("id")
        card_set, card_number = card_id.split("_", 1)
        self.card_set = card_set
        self.card_number = card_number
        self.count = card_json.get("count", 1)

    def __repr__(self):
        return f"{self.count}x {self.card_set}_{self.card_number}"


class Deck:
    """
    Represents a deck of cards with leaders, bases, main deck, and sideboard.

    Supports two JSON formats:
    - List format: "leaders": [...], "bases": [...]
    - Legacy format: "leader": {...}, "secondleader": {...}, "base": {...}
    Using both formats simultaneously for the same field is an error.
    """

    def __init__(self, leaders=None, bases=None, main_deck=None, sideboard=None, metadata=None):
        self.leaders = leaders or []
        self.bases = bases or []
        self.main_deck = main_deck or []
        self.sideboard = sideboard or []
        self.metadata = metadata or {}

    @classmethod
    def from_json(cls, json_data):
        # Parse metadata
        metadata = json_data.get("metadata", {})

        # Parse leaders
        has_leaders_list = "leaders" in json_data
        has_leader_singular = "leader" in json_data or "secondleader" in json_data

        if has_leaders_list and has_leader_singular:
            raise ValueError(
                "Deck JSON cannot contain both 'leaders' and 'leader'/'secondleader'. "
                "Use one format or the other."
            )

        leaders = []
        if has_leaders_list:
            for card_json in json_data["leaders"]:
                leaders.append(Card(card_json))
        elif has_leader_singular:
            if json_data.get("leader") is not None:
                leaders.append(Card(json_data["leader"]))
            if json_data.get("secondleader") is not None:
                leaders.append(Card(json_data["secondleader"]))

        # Parse bases
        has_bases_list = "bases" in json_data
        has_base_singular = "base" in json_data

        if has_bases_list and has_base_singular:
            raise ValueError(
                "Deck JSON cannot contain both 'bases' and 'base'. "
                "Use one format or the other."
            )

        bases = []
        if has_bases_list:
            for card_json in json_data["bases"]:
                bases.append(Card(card_json))
        elif has_base_singular:
            if json_data.get("base") is not None:
                bases.append(Card(json_data["base"]))

        # Parse main deck and sideboard
        main_deck = [Card(c) for c in json_data.get("deck", [])]
        sideboard = [Card(c) for c in json_data.get("sideboard", [])]

        return cls(leaders, bases, main_deck, sideboard, metadata)

    @classmethod
    def from_json_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_json(data)
