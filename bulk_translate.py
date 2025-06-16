import sqlite3
from googletrans import Translator
from time import sleep

WORDS_FILE = "portuguese.txt"
DB_FILE = "vocab.db"

translator = Translator()

# Connect to database
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

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

# Load all words
with open(WORDS_FILE, encoding='utf-8') as f:
    all_words = [line.strip() for line in f if line.strip()]

total = len(all_words)
translated = 0
skipped = 0
failed = 0

for i, word in enumerate(all_words, start=1):
    # Skip if already has a translation
    cursor.execute("SELECT translation FROM words WHERE word = ?", (word,))
    result = cursor.fetchone()
    if result and result[0]:
        skipped += 1
        continue

    try:
        result = translator.translate(word, src='pt', dest='en')
        translation = result.text

        cursor.execute("""
            INSERT INTO words (word, translation)
            VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET translation=excluded.translation
        """, (word, translation))
        conn.commit()

        translated += 1
        print(f"[{i}/{total}] ✅ {word} → {translation}")

        # Optional: Sleep to avoid rate-limiting
        sleep(0.5)

    except Exception as e:
        failed += 1
        print(f"[{i}/{total}] ❌ Failed to translate '{word}': {e}")
        sleep(1)

print(f"\n✅ Done. Translated: {translated}, Skipped: {skipped}, Failed: {failed}")
