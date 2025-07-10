"""
Utilities and classes for card games, primarily Blackjack.
Includes Card, Deck, and Hand representations.
"""
import random
from collections import namedtuple

# Using namedtuple for Card as it's a simple data structure
_Card = namedtuple("Card", ["suit", "rank", "value"])

def Card(suit, rank):
    """Factory function for creating a Card."""
    return _Card(suit, rank, VALUES[rank])

SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

class Deck:
    """Represents a deck of cards."""
    def __init__(self, num_decks=1):
        self.num_decks = num_decks
        self.cards = []
        self.build()

    def build(self):
        """Builds a full deck of cards and shuffles it."""
        self.cards = [
            Card(suit, rank)
            for _ in range(self.num_decks)
            for suit in SUITS
            for rank in RANKS
        ]
        self.shuffle()

    def shuffle(self):
        """Shuffles the deck."""
        random.shuffle(self.cards)

    def deal(self, num_cards=1):
        """Deals a specified number of cards from the deck."""
        if len(self.cards) < num_cards:
            # Reshuffle if not enough cards, common in casino games
            self.build()

        dealt_cards = [self.cards.pop() for _ in range(num_cards)]
        return dealt_cards if num_cards > 1 else dealt_cards[0]

class Hand:
    """Represents a hand of cards in a game like Blackjack."""
    def __init__(self):
        self.cards = []
        self.value = 0
        self.aces = 0

    def add_card(self, card):
        """Adds a card to the hand."""
        self.cards.append(card)
        self.value += card.value
        if card.rank == 'A':
            self.aces += 1
        self.adjust_for_ace()

    def adjust_for_ace(self):
        """Adjusts the hand value if an Ace is present and the total value exceeds 21."""
        while self.value > 21 and self.aces:
            self.value -= 10
            self.aces -= 1

    def __str__(self):
        return ', '.join(f"{card.rank}{card.suit}" for card in self.cards) 