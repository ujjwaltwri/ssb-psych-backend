# curate_words.py

import os
import json
import random
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai
import nltk
from nltk.corpus import words as nltk_words

# --- Initialize Services (Supabase, Gemini) ---
load_dotenv()
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Main Script Logic ---

def curate_and_add_words(limit=200):
    print("Starting the word curation engine...")
    
    # 1. Get all words from the NLTK corpus
    all_english_words = set(w.lower() for w in nltk_words.words())
    print(f"Loaded {len(all_english_words)} words from NLTK corpus.")

    # 2. Get words already in our database to avoid duplicates
    try:
        res = supabase.table('wat_words').select('word_text').execute()
        existing_words = set(item['word_text'] for item in res.data)
        print(f"Found {len(existing_words)} words already in the database.")
    except Exception as e:
        print(f"Error fetching existing words: {e}")
        existing_words = set()

    # 3. Filter for new, suitable words
    potential_new_words = [
        w for w in all_english_words 
        if 4 <= len(w) <= 10 and w.isalpha() and w not in existing_words
    ]
    random.shuffle(potential_new_words)
    words_to_process = potential_new_words[:limit]
    print(f"Selected {len(words_to_process)} new words to categorize.")

    if not words_to_process:
        print("No new words to process. Exiting.")
        return

    # 4. Use Gemini AI to categorize the new words
    try:
        print("Asking Gemini API to categorize words...")
        prompt = f"""
        Analyze the following list of English words. For each word, categorize it as "Positive", "Negative", or "Neutral" based on its most common connotation.

        Word List:
        {', '.join(words_to_process)}

        Your Task:
        Return a single, valid JSON object where each key is a word from the list and its value is its category string. For example:
        {{
            "happy": "Positive",
            "fear": "Negative",
            "table": "Neutral"
        }}
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        categorized_words = json.loads(cleaned_text)
        print(f"Successfully categorized {len(categorized_words)} words.")
    except Exception as e:
        print(f"An error occurred during AI categorization: {e}")
        return

    # 5. Prepare data for insertion
    words_to_insert = [
        {"word_text": word, "category": category}
        for word, category in categorized_words.items()
    ]

    # 6. Insert new words into Supabase
    try:
        print(f"Inserting {len(words_to_insert)} new words into the database...")
        data, count = supabase.table('wat_words').insert(words_to_insert).execute()
        print("Curation complete. Database has been updated with new words.")
    except Exception as e:
        print(f"An error occurred during database insertion: {e}")


if __name__ == "__main__":
    # You can change the number to add more or fewer words at a time
    curate_and_add_words(limit=750)