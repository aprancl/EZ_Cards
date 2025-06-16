import urwid
import sqlite3
import random
from datetime import datetime
from googletrans import Translator

# Files
WORDS_FILE = "portuguese.txt"
DB_FILE = "vocab.db"

def main():
    global conn, cursor, all_words, current_word, revealed, manual_mode, main_widget, translator

    # Setup
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    translator = Translator()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS words (
        word_in_pt TEXT PRIMARY KEY,
        word_in_eng TEXT,
        status TEXT
    )
    ''')
    conn.commit()

    with open(WORDS_FILE, encoding='utf-8') as f:
        all_words = [line.strip() for line in f if line.strip()]
    random.shuffle(all_words)

    # Initialize state
    current_word = get_next_word()
    revealed = False
    manual_mode = False

    # Main UI loop
    main_widget = urwid.WidgetPlaceholder(show_flashcard(current_word))
    loop = urwid.MainLoop(main_widget, unhandled_input=handle_input)
    loop.run()

def get_next_word():
    for word in all_words:
        cursor.execute("SELECT word_in_eng FROM words WHERE word_in_pt = ?", (word,))
        result = cursor.fetchone()
        if not result or not result[0]:
            return word
    return random.choice(all_words)

def total_progress():
    cursor.execute("SELECT status, COUNT(*) FROM words GROUP BY status")
    rows = cursor.fetchall()
    counts = {'new': 0, 'recognizable': 0, 'comfortable': 0, 'learned': 0}
    for status, count in rows:
        counts[status] = count
    total = sum(counts.values())
    return (
        f"New: {counts['new']}  |  "
        f"Recognizable: {counts['recognizable']}  |  "
        f"Comfortable: {counts['comfortable']}  |  "
        f"Learned: {counts['learned']}  ||  Total: {total}"
    )

def save_translation(word, translation, status="new"):
    cursor.execute("""
        INSERT INTO words (word_in_pt, word_in_eng, status)
        VALUES (?, ?, ?)
        ON CONFLICT(word_in_pt) DO UPDATE SET
            word_in_eng=excluded.word_in_eng,
            status=excluded.status
    """, (word, translation, status))
    conn.commit()

def update_status(word, status):
    cursor.execute("UPDATE words SET status = ? WHERE word_in_pt = ?", (status, word))
    conn.commit()

def attempt_translation(word):
    try:
        result = translator.translate(word, src='pt', dest='en')
        return result.text
    except Exception:
        return None

def make_flashcard_widget(body):
    controls = urwid.Filler(urwid.Text((
        "\nControls:\n"
        "  enter → Flip Card\n"
        "  number (1-4) → Set Status\n"
        "  ESC   → Exit"
    ), align='left'), valign='top')

    layout = urwid.Pile([
        urwid.Filler(body, valign='top', top=1, bottom=1),
        controls
    ])

    footer = urwid.Text(total_progress(), align='center')
    return urwid.Frame(
        header=urwid.Text("📝 Flashcard", align='center'),
        body=urwid.LineBox(urwid.Padding(layout, left=4, right=4)),
        footer=footer
    )

def show_flashcard(word, reveal=False):
    cursor.execute("SELECT word_in_eng FROM words WHERE word_in_pt = ?", (word,))
    result = cursor.fetchone()

    if not result:
        translation = attempt_translation(word)
        if translation:
            save_translation(word, translation)
        else:
            global manual_mode
            manual_mode = True
            return make_flashcard_widget(
                urwid.Edit(f"Portuguese: {word}\n\nNo internet.\nEnter translation manually:\n> ")
            )

    cursor.execute("SELECT word_in_eng FROM words WHERE word_in_pt = ?", (word,))
    result = cursor.fetchone()

    if not reveal:
        return make_flashcard_widget(
            urwid.Text(f"Portuguese: {word}\n\nPress ENTER to reveal the translation")
        )
    else:
        return make_flashcard_widget(
            urwid.Text(
                f"Portuguese: {word}\n\nTranslation: {result[0]}\n\n"
                f"Rate your knowledge:\n1. New  2. Recognizable  3. Comfortable  4. Learned"
            )
        )

def handle_input(key):
    global current_word, main_widget, revealed, manual_mode

    if key == 'esc':
        raise urwid.ExitMainLoop()

    widget = main_widget.original_widget.body.original_widget.original_widget

    if isinstance(widget, urwid.Edit) and manual_mode:
        if key == 'enter':
            lines = widget.edit_text.strip().split('\n')
            translation = lines[-1].strip()
            if translation:
                save_translation(current_word, translation)
                manual_mode = False
                revealed = False
                current_word = get_next_word()
                main_widget.original_widget = show_flashcard(current_word)
        return

    if key == 'enter':
        if not revealed:
            revealed = True
            main_widget.original_widget = show_flashcard(current_word, reveal=True)
        return

    if key in ('1', '2', '3', '4') and revealed:
        status_map = {'1': 'new', '2': 'recognizable', '3': 'comfortable', '4': 'learned'}
        update_status(current_word, status_map[key])
        revealed = False
        current_word = get_next_word()
        main_widget.original_widget = show_flashcard(current_word)


if __name__ == "__main__":
    main()
