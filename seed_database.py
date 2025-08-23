# seed_database.py

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load variables from .env file
load_dotenv()

# Get Supabase credentials from environment variables
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Create a Supabase client
supabase: Client = create_client(url, key)

# --- Define the words to be added ---
words_to_insert = [
    # Positive
    {'word_text': 'Lead', 'category': 'Positive'},
    {'word_text': 'Courage', 'category': 'Positive'},
    {'word_text': 'Team', 'category': 'Positive'},
    {'word_text': 'Friend', 'category': 'Positive'},
    {'word_text': 'Success', 'category': 'Positive'},
    {'word_text': 'Duty', 'category': 'Positive'},
    {'word_text': 'Unite', 'category': 'Positive'},
    {'word_text': 'Help', 'category': 'Positive'},
    {'word_text': 'Win', 'category': 'Positive'},
    {'word_text': 'Achieve', 'category': 'Positive'},
    {'word_text': 'Brave', 'category': 'Positive'},
    {'word_text': 'Trust', 'category': 'Positive'},

    # Negative
    {'word_text': 'Fear', 'category': 'Negative'},
    {'word_text': 'Attack', 'category': 'Negative'},
    {'word_text': 'Defeat', 'category': 'Negative'},
    {'word_text': 'Blame', 'category': 'Negative'},
    {'word_text': 'Alone', 'category': 'Negative'},
    {'word_text': 'Risk', 'category': 'Negative'},
    {'word_text': 'Worry', 'category': 'Negative'},
    {'word_text': 'Quit', 'category': 'Negative'},
    {'word_text': 'Reject', 'category': 'Negative'},
    {'word_text': 'Conflict', 'category': 'Negative'},
    {'word_text': 'Argument', 'category': 'Negative'},
    {'word_text': 'Crisis', 'category': 'Negative'},

    # Neutral
    {'word_text': 'Chair', 'category': 'Neutral'},
    {'word_text': 'System', 'category': 'Neutral'},
    {'word_text': 'Book', 'category': 'Neutral'},
    {'word_text': 'Walk', 'category': 'Neutral'},
    {'word_text': 'City', 'category': 'Neutral'},
    {'word_text': 'Weather', 'category': 'Neutral'},
    {'word_text': 'Project', 'category': 'Neutral'},
    {'word_text': 'Music', 'category': 'Neutral'},
    {'word_text': 'Task', 'category': 'Neutral'},
    {'word_text': 'Morning', 'category': 'Neutral'},
    {'word_text': 'Paper', 'category': 'Neutral'},
    {'word_text': 'Office', 'category': 'Neutral'},
]

# --- Insert the data into the 'wat_words' table ---
try:
    data, count = supabase.table('wat_words').insert(words_to_insert).execute()
    print(f"Successfully inserted {len(words_to_insert)} words into the database.")
except Exception as e:
    print(f"An error occurred: {e}")