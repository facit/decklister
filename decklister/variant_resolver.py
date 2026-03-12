# Known base set sizes (number of unique cards in the standard set)
BASE_SET_SIZES = {
    "SOR": 252,
    "SHD": 262,
    "TWI": 257,
    "JTL": 262,
    "LOF": 264,
    "SEC": 264,
    "LAW": 264,
}

LEADER_CARD_RANGE = (1, 18)  # Cards 1-18 are leaders in every set


def get_base_set_size(card_set):
    """Get the base set size for a set. Returns None if unknown."""
    return BASE_SET_SIZES.get(card_set.upper())


def resolve_variant(card_set, card_number, hyperspace=False, showcase=False):
    """
    Resolve the variant card number for a given card.

    Args:
        card_set: The card set identifier (e.g., 'SOR').
        card_number: The base card number (str or int).
        hyperspace: If True, use the hyperspace variant.
        showcase: If True, use the showcase variant (leaders only).
            Overrides hyperspace if both are True.

    Returns:
        The resolved card number as a string.
    """
    num = int(card_number)
    x = get_base_set_size(card_set)

    if x is None:
        # Unknown set — no variant treatment
        return str(card_number)

    is_leader = LEADER_CARD_RANGE[0] <= num <= LEADER_CARD_RANGE[1]

    # Showcase overrides hyperspace, but only applies to leaders
    if showcase and is_leader:
        return str(4 * x - 52 + num)

    if hyperspace:
        return str(num%x + x)

    return str(card_number)
