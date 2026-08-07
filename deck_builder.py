"""Random legal deck construction using the complete card-instance catalog."""
import random


def build_random_deck(cards, deck_size=50, rng=None):
    """Return unique instance IDs sampled uniformly from the full catalog."""
    rng = rng or random.SystemRandom()
    instance_ids = list(cards)
    if len(instance_ids) < deck_size:
        raise ValueError("catalog does not contain enough unique card instances")
    return rng.sample(instance_ids, deck_size)
