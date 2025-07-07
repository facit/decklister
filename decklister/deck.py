import json

class Card:
    def __init__(self, card_json):
        card_id=card_json.get("id")
        card_set, card_number = card_id.split("_", 1)
        self.card_set=card_set
        self.card_number=card_number
        self.count=card_json.get("count", 1)
        
    def __repr__(self):
        return f"{self.count}x {self.card_set}_{self.card_number}"

class Deck:
    """
    Represents a deck of cards, including both the main deck and sideboard.
    Attributes:
        main_deck (list): List of Card objects in the main deck.
        sideboard (list): List of Card objects in the sideboard.
    Methods:
        __init__(self, main_deck=None, sideboard=None):
            Initializes a Deck instance with optional main_deck and sideboard lists.
            If not provided, initializes as empty lists.
        from_json(cls, json_data):
            Class method to create a Deck instance from a JSON-like dictionary.
            Expects 'deck' and 'sideboard' keys in the dictionary, each containing
            a list of card dictionaries with 'id' (format: 'set_number') and optional 'count'.
            Splits the 'id' to extract card_set and card_number for Card construction.
        from_json_file(cls, path):
            Class method to create a Deck instance from a JSON file.
            Reads the file at the given path, loads the JSON data, and delegates
            to from_json() for Deck construction.
    Usage Notes:
        - To add new fields to cards, update the Card class and adjust the from_json method accordingly.
        - To support additional deck sections (e.g., commander), add new attributes and parsing logic.
        - Ensure the JSON structure matches the expected format for correct parsing.
    """
    def __init__(self, main_deck=None, sideboard=None, leader_card=None, second_leader_card=None, base_card=None):
        self.main_deck = main_deck if main_deck else []
        self.sideboard = sideboard if sideboard else []
        self.leader_card = leader_card if leader_card else None
        self.second_leader_card = second_leader_card if second_leader_card else None
        self.base_card = base_card if base_card else None

    @classmethod
    def from_json(cls, json_data):
        leader_card = json_data.get("leader")
        if leader_card is not None:
            leader_card = Card(leader_card)
        second_leader_card = json_data.get("secondleader")
        if second_leader_card is not None:
            second_leader_card = Card(second_leader_card)
        base_card = json_data.get("base")
        if base_card is not None:
            base_card = Card(base_card)
        main_deck = []
        sideboard = []
        for card_json in json_data.get("deck", []):
            main_deck.append(Card(card_json))
        for card_json in json_data.get("sideboard", []):
            sideboard.append(Card(card_json))
        return cls(main_deck, sideboard, leader_card, second_leader_card, base_card)

    @classmethod
    def from_json_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_json(data)