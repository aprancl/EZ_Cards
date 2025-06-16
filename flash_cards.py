import pdb
import urwid
import sqlite3
import random
from datetime import datetime
from googletrans import Translator

# Files
WORDS_FILE = "portuguese.txt"
DB_FILE = "vocab.db"

# Setup
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
translator = Translator()

cursor.execute('''
CREATE TABLE IF NOT EXISTS words (
    word TEXT PRIMARY KEY,
    translation TEXT,
    seen_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

with open(WORDS_FILE, encoding='utf-8') as f:
    all_words = [line.strip() for line in f if line.strip()]
random.shuffle(all_words)

# State
current_word = None
revealed = False
awaiting_answer = False
manual_mode = False

def get_next_word():
    for word in all_words:
        cursor.execute("SELECT translation FROM words WHERE word = ?", (word,))
        result = cursor.fetchone()
        if not result or not result[0]:
            return word
    return random.choice(all_words)

def total_progress():
    cursor.execute("SELECT COUNT(*) FROM words WHERE translation IS NOT NULL")
    learned = cursor.fetchone()[0]
    return f"Progress: {learned}/{len(all_words)} words learned"

def save_translation(word, translation):
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO words (word, translation, seen_count, correct_count, last_seen)
        VALUES (?, ?, 1, 0, ?)
        ON CONFLICT(word) DO UPDATE SET
            translation=excluded.translation,
            seen_count=words.seen_count+1,
            last_seen=excluded.last_seen
    """, (word, translation, now))
    conn.commit()

def update_stats(word, correct):
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE words SET
            seen_count = seen_count + 1,
            correct_count = correct_count + ?,
            last_seen = ?
        WHERE word = ?
    """, (1 if correct else 0, now, word))
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
        "  enter  → Flip Card\n"
        "  enter again  → Next Card\n"
        "  ESC    → Exit"
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

def show_flashcard(word, reveal=False, ask=False):
    cursor.execute("SELECT translation FROM words WHERE word = ?", (word,))
    result = cursor.fetchone()

    if not result:
        # Word not in DB — attempt translation silently
        translation = attempt_translation(word)
        if translation:
            save_translation(word, translation)
        else:
            # No internet: ask for manual entry
            global manual_mode
            manual_mode = True
            return make_flashcard_widget(
                urwid.Edit(f"Portuguese: {word}\n\nNo internet.\nEnter translation manually:\n> ")
            )

    # Now load again (whether we just saved it or it existed)
    cursor.execute("SELECT translation FROM words WHERE word = ?", (word,))
    result = cursor.fetchone()

    if not reveal:
        return make_flashcard_widget(
            urwid.Text(f"Portuguese: {word}\n\nPress SPACE to reveal the translation")
        )
    elif not ask:
        return make_flashcard_widget(
            urwid.Text(f"Portuguese: {word}\n\nTranslation: {result[0]}\n\nPress any key to continue...")
        )
    else:
        return make_flashcard_widget(
            urwid.Text("Did you know this word?\nPress 'y' or 'n'")
        )

def handle_input(key):
    global current_word, main_widget, revealed, manual_mode

    if key == 'esc':
        raise urwid.ExitMainLoop()

    widget = main_widget.original_widget.body.original_widget.original_widget

    # Handle manual mode for offline translation entry
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

    # Flashcard flow using ENTER
    if key == 'enter':
        if not revealed:
            revealed = True
            main_widget.original_widget = show_flashcard(current_word, reveal=True)
        else:
            update_stats(current_word, correct=True)  # optionally always record as correct
            revealed = False
            current_word = get_next_word()
            main_widget.original_widget = show_flashcard(current_word)
# Start app
current_word = get_next_word()
main_widget = urwid.WidgetPlaceholder(show_flashcard(current_word))
loop = urwid.MainLoop(main_widget, unhandled_input=handle_input)
loop.run()
