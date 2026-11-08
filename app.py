"""Lumen: an entirely Python + native Streamlit tarot application."""

import csv
import json
import math
import sqlite3
from datetime import datetime

import streamlit as st

from tarot import (
    DECK_PATH, SPREADS, filter_deck, list_readings, load_deck,
    make_reading, reading_text, save_reading, symbol,
)

st.set_page_config(page_title="Lumen · Tarot", page_icon="☾", layout="wide")


@st.cache_data(show_spinner=False)
def get_deck(modified_at: int) -> list[dict]:
    return load_deck()


def card_details(card: dict) -> None:
    upright, reversed_tab, love, career = st.tabs(["Upright", "Reversed", "Love", "Career"])
    with upright:
        st.write(card["upright_meaning"])
    with reversed_tab:
        st.write(card["reversed_meaning"])
    with love:
        st.write(card["love_meaning"])
    with career:
        st.write(card["career_meaning"])
    st.caption("Love and career meanings are general; the CSV does not separate them by orientation.")
    details = [f"{card['arcana']} Arcana", card["suit"], card["element"], card["zodiac_sign"]]
    st.caption(" · ".join(value for value in details if value))
    st.caption(f"Yes / no association in the deck: {card['yes_or_no']}")
    if card["guide_url"].startswith("https://"):
        st.link_button("Read the card guide ↗", card["guide_url"])


@st.dialog("Inside the card", width="large")
def inspect_card(card: dict) -> None:
    st.title(f"{symbol(card)}  {card['card_name']}", anchor=False)
    card_details(card)


def show_reading(reading: dict, key_prefix: str) -> None:
    if reading["question"]:
        st.caption("YOUR QUESTION")
        st.write(reading["question"])
    columns = st.columns(len(reading["cards"]), gap="large")
    for index, (column, drawn) in enumerate(zip(columns, reading["cards"])):
        card = drawn["card"]
        with column, st.container(border=True):
            st.caption(f"{index + 1:02d} / {drawn['position'].upper()}")
            st.title(symbol(card), anchor=False)
            st.subheader(card["card_name"], anchor=False)
            st.badge("Reversed" if drawn["reversed"] else "Upright",
                     color="orange" if drawn["reversed"] else "violet")
            st.caption(f"{card['arcana']} Arcana · {card['suit'] or card['element']}")
            st.divider()
            st.write(card["reversed_meaning" if drawn["reversed"] else "upright_meaning"])
            if st.button("Explore this card ↗", key=f"{key_prefix}_detail_{index}", width="stretch"):
                inspect_card(card)


def reading_room(deck: list[dict]) -> None:
    st.caption("01 / THE READING ROOM")
    st.title("A moment for possibility.", anchor=False)
    st.write("Take a breath. Hold a question. See what the cards bring into focus.")
    st.space("small")
    with st.container(border=True):
        with st.form("draw_form"):
            st.subheader("What’s on your mind?", anchor=False)
            question = st.text_input("Your question", placeholder="What could I use a fresh perspective on?",
                                     max_chars=500, help="Optional. Leave this empty for an open reading.")
            left, right = st.columns([2, 1], gap="large")
            with left:
                spread = st.radio("Choose your spread", list(SPREADS), horizontal=True)
                st.caption("One card for a focus. Three cards for past, present, and future.")
            with right:
                allow_reversed = st.toggle("Include reversed cards", value=True)
                st.caption("Reversed cards use their own meanings from your deck.")
            draw = st.form_submit_button("✧  Draw your cards", type="primary", width="stretch")
        if draw:
            st.session_state.reading = make_reading(deck, spread, question, allow_reversed)

    reading = st.session_state.get("reading")
    if not reading:
        st.space("medium")
        left, middle, right = st.columns(3)
        for col, icon, title, body in [
            (left, "☾", "Make a little space", "Let a question settle, or simply arrive with an open mind."),
            (middle, "✧", "Follow a thread", "Read the meanings and notice what connects with your experience."),
            (right, "✎", "Keep a reflection", "Save your reading and a thought to return to later."),
        ]:
            with col:
                st.subheader(f"{icon}  {title}", anchor=False)
                st.caption(body)
        return

    st.space("small")
    st.subheader("Your cards, your perspective.", anchor=False)
    show_reading(reading, "current")
    st.space("small")
    with st.container(border=True):
        st.subheader("What stands out to you?", anchor=False)
        note = st.text_area("Your reflection", key=f"reflection_{reading['id']}",
                            placeholder="An idea, a feeling, or one small next step…", max_chars=10000)
        save_col, export_col = st.columns(2)
        if save_col.button("Save to your journal", type="primary", width="stretch"):
            try:
                save_reading(reading, note)
                st.success("Reading saved. Find it in Your journal.")
            except (OSError, sqlite3.Error) as error:
                st.error(f"Could not save the journal: {error}")
        export_col.download_button("Download this reading", reading_text(reading, note),
                                   file_name=f"lumen-{reading['id'][:8]}.txt", mime="text/plain",
                                   width="stretch")


def card_library(deck: list[dict]) -> None:
    st.caption("02 / THE CARD LIBRARY")
    st.title("Get to know your deck.", anchor=False)
    st.write("78 cards. A whole world of meanings. Find the one you’re curious about.")
    query = st.text_input("Search the deck", placeholder="Try The Moon, new beginnings, or intuition…")
    col1, col2, col3, col4 = st.columns(4)
    arcana = col1.selectbox("Arcana", ["All", "Major", "Minor"])
    suit = col2.selectbox("Suit", ["All", "Cups", "Pentacles", "Swords", "Wands"])
    element = col3.selectbox("Element", ["All", "Air", "Earth", "Fire", "Water"])
    orientation = col4.selectbox("Meaning", ["Upright", "Reversed"])
    cards = filter_deck(deck, query, arcana, suit, element)
    fingerprint = (query, arcana, suit, element)
    if st.session_state.get("library_filters") != fingerprint:
        st.session_state.library_filters = fingerprint
        st.session_state.library_page = 1
    if not cards:
        st.info("No cards match these filters. Try another search or select All in the filters.")
        return
    page_count = math.ceil(len(cards) / 9)
    label_col, page_col = st.columns([3, 1])
    label_col.caption(f"{len(cards)} cards found · Select a card to see all its meanings.")
    page = page_col.selectbox("Page", range(1, page_count + 1),
                              format_func=lambda n: f"Page {n} of {page_count}", key="library_page")
    visible = cards[(page - 1) * 9:page * 9]
    for offset in range(0, len(visible), 3):
        for column, card in zip(st.columns(3, gap="medium"), visible[offset:offset + 3]):
            with column, st.container(border=True):
                st.caption(f"{card['arcana'].upper()} ARCANA · {card['suit'] or card['element']}")
                st.title(symbol(card), anchor=False)
                st.subheader(card["card_name"], anchor=False)
                st.caption(orientation)
                st.write(card["reversed_meaning" if orientation == "Reversed" else "upright_meaning"])
                if st.button("Discover the meaning ↗", key=f"library_{card['card_number']}", width="stretch"):
                    inspect_card(card)


def journal() -> None:
    st.caption("03 / YOUR JOURNAL")
    st.title("A place to return to.", anchor=False)
    st.write("Your saved cards, questions, and reflections, gathered in one place.")
    try:
        readings = list_readings()
    except (OSError, sqlite3.Error, json.JSONDecodeError) as error:
        st.error(f"Could not open the journal: {error}")
        return
    if not readings:
        with st.container(border=True):
            st.subheader("Your story starts with a card.", anchor=False)
            st.write("Draw a reading in the Reading room, add a reflection, and save it here.")
        return
    left, right = st.columns([3, 1])
    query = left.text_input("Search your journal", placeholder="Search questions, cards, or reflections…")
    right.download_button("Export journal", json.dumps(readings, indent=2, ensure_ascii=False),
                          file_name="lumen-journal.json", mime="application/json", width="stretch")
    matching = [r for r in readings if query.casefold() in json.dumps(r, ensure_ascii=False).casefold()]
    st.caption(f"{len(matching)} of {len(readings)} saved readings")
    if not matching:
        st.info("No saved readings match your search.")
    for reading in matching:
        timestamp = datetime.fromisoformat(reading["created_at"]).strftime("%d %b %Y · %H:%M")
        names = ", ".join(item["card"]["card_name"] for item in reading["cards"])
        with st.expander(f"{timestamp} — {reading['question'] or names}"):
            st.caption(reading["spread"])
            show_reading(reading, reading["id"])
            note = st.text_area("Your reflection", value=reading["note"],
                                key=f"journal_note_{reading['id']}", max_chars=10000)
            save_col, download_col = st.columns(2)
            if save_col.button("Update reflection", key=f"update_{reading['id']}", width="stretch"):
                try:
                    save_reading(reading, note)
                    st.success("Reflection updated.")
                except (OSError, sqlite3.Error) as error:
                    st.error(f"Could not update the reflection: {error}")
            download_col.download_button("Download reading", reading_text(reading, note),
                                         file_name=f"lumen-{reading['id'][:8]}.txt", mime="text/plain",
                                         key=f"download_{reading['id']}", width="stretch")
    st.caption("Journal entries are stored locally in this project’s data folder.")


def main() -> None:
    try:
        deck = get_deck(DECK_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        st.error(f"Could not load the deck: {error}")
        st.info("Place tarot_card_meanings.csv in the project’s data folder, then refresh.")
        st.stop()
    with st.sidebar:
        st.title("☾  LUMEN", anchor=False)
        st.caption("A quiet space for tarot.")
        st.divider()
        page = st.radio("Find your space", ["Reading room", "The card library", "Your journal"],
                        label_visibility="collapsed")
        st.divider()
        st.caption("THE DECK")
        left, right = st.columns(2)
        left.metric("Major Arcana", sum(c["arcana"] == "Major" for c in deck))
        right.metric("Minor Arcana", sum(c["arcana"] == "Minor" for c in deck))
        with st.expander("About this space"):
            st.write("Every meaning comes from your 78-card CSV. Readings draw cards randomly, without duplicates.")
            st.write("Use the cards as prompts for reflection. The next step is yours.")
            st.caption("Built entirely with Python and native Streamlit components.")
        st.caption("✧  Make room for a different perspective.")
    if page == "Reading room":
        reading_room(deck)
    elif page == "The card library":
        card_library(deck)
    else:
        journal()
    st.divider()
    st.caption("☾  LUMEN     ·     78 cards, endless conversations.")


if __name__ == "__main__":
    main()
