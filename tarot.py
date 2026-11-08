"""CSV-backed tarot readings and a local, persistent journal."""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
DECK_PATH = ROOT / "data" / "tarot_card_meanings.csv"
JOURNAL_PATH = ROOT / "data" / "journal.sqlite3"
FIELDS = {
    "card_number", "card_name", "arcana", "suit", "element",
    "upright_meaning", "reversed_meaning", "love_meaning", "career_meaning",
    "yes_or_no", "zodiac_sign", "guide_url",
}
SPREADS = {
    "One card": ("Your focus",),
    "Three cards": ("Past", "Present", "Future"),
}
SYMBOLS = {"Wands": "✶", "Cups": "☾", "Swords": "✧", "Pentacles": "✦"}
MAJOR_SYMBOLS = {
    "The Fool": "✷", "The Magician": "✧", "The High Priestess": "☾",
    "The Empress": "❀", "The Emperor": "♜", "The Hierophant": "✥",
    "The Lovers": "♡", "The Chariot": "✵", "Strength": "∞",
    "The Hermit": "✶", "Wheel of Fortune": "☸", "Justice": "⚖",
    "The Hanged Man": "◇", "Death": "❋", "Temperance": "◒",
    "The Devil": "♜", "The Tower": "ϟ", "The Star": "☆",
    "The Moon": "☾", "The Sun": "☀", "Judgement": "✺", "The World": "◎",
}


def load_deck(path: Path = DECK_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = FIELDS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"The CSV is missing columns: {', '.join(sorted(missing))}")
        cards = [{key: (value or "").strip() for key, value in row.items()}
                 for row in reader]
    if not cards:
        raise ValueError("The CSV contains no cards.")
    if any(not card["card_name"] or not card["upright_meaning"] or
           not card["reversed_meaning"] for card in cards):
        raise ValueError("Every card needs a name, upright meaning, and reversed meaning.")
    if len({card["card_number"] for card in cards}) != len(cards):
        raise ValueError("Card numbers must be unique.")
    return cards


def symbol(card: dict) -> str:
    return MAJOR_SYMBOLS.get(card["card_name"], SYMBOLS.get(card["suit"], "✧"))


def make_reading(deck: list[dict], spread: str, question: str = "",
                 allow_reversed: bool = True) -> dict:
    positions = SPREADS[spread]
    rng = random.SystemRandom()
    selected = rng.sample(deck, len(positions))
    return {
        "id": uuid4().hex,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "question": question.strip(),
        "spread": spread,
        "cards": [
            {"card": card, "position": position,
             "reversed": allow_reversed and bool(rng.getrandbits(1))}
            for position, card in zip(positions, selected)
        ],
    }


def filter_deck(deck: list[dict], query: str = "", arcana: str = "All",
                suit: str = "All", element: str = "All") -> list[dict]:
    search = query.casefold().strip()
    return [card for card in deck
            if (arcana == "All" or card["arcana"] == arcana)
            and (suit == "All" or card["suit"] == suit)
            and (element == "All" or card["element"] == element)
            and search in "\n".join(card.values()).casefold()]


def connect_journal(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS readings "
        "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
        "payload TEXT NOT NULL, note TEXT NOT NULL DEFAULT '')"
    )
    return connection


def save_reading(reading: dict, note: str = "", path: Path = JOURNAL_PATH) -> None:
    connection = connect_journal(path)
    try:
        with connection:
            connection.execute(
                "INSERT INTO readings(id, created_at, payload, note) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET note = excluded.note",
                (reading["id"], reading["created_at"], json.dumps(reading), note.strip()),
            )
    finally:
        connection.close()


def list_readings(path: Path = JOURNAL_PATH) -> list[dict]:
    connection = connect_journal(path)
    try:
        rows = connection.execute(
            "SELECT payload, note FROM readings ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    finally:
        connection.close()
    return [{**json.loads(payload), "note": note} for payload, note in rows]


def reading_text(reading: dict, note: str = "") -> str:
    lines = ["LUMEN · TAROT READING", reading["created_at"], reading["spread"]]
    if reading["question"]:
        lines.extend(["", f"Question: {reading['question']}"])
    for drawn in reading["cards"]:
        card = drawn["card"]
        orientation = "Reversed" if drawn["reversed"] else "Upright"
        meaning = card["reversed_meaning" if drawn["reversed"] else "upright_meaning"]
        lines.extend(["", f"{drawn['position']}: {card['card_name']} · {orientation}",
                      meaning, f"Love: {card['love_meaning']}",
                      f"Career: {card['career_meaning']}"])
    if note.strip():
        lines.extend(["", "My reflection", note.strip()])
    return "\n".join(lines) + "\n"
