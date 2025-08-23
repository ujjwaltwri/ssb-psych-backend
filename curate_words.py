# curate_words.py

import os
import json
import random
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai
import nltk
from nltk.corpus import words as nltk_words

# --- Initialize Services ---
load_dotenv()
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Main Script Logic ---
def curate_and_add_words(fetch_limit=1000, final_limit=200):
    print("Starting the word curation engine...")
    
    # 1. Get words from NLTK and the database
    all_english_words = set(w.lower() for w in nltk_words.words())
    try:
        res = supabase.table('wat_words').select('word_text').execute()
        existing_words = set(item['word_text'] for item in res.data)
        print(f"Loaded {len(all_english_words)} words from NLTK and found {len(existing_words)} in DB.")
    except Exception as e:
        existing_words = set()
        print(f"Could not fetch existing words: {e}")

    # 2. Filter for potential new words
    potential_words = [
        w for w in all_english_words 
        if 4 <= len(w) <= 10 and w.isalpha() and w not in existing_words
    ]
    random.shuffle(potential_words)
    words_to_filter = potential_words[:fetch_limit]
    
    if not words_to_filter:
        print("No new words to process. Exiting.")
        return

    # 3. --- NEW: AI-powered filtering for common words ---
    try:
        print(f"Asking AI to filter {len(words_to_filter)} words for commonality...")
        filter_prompt = f"""
        From the following list of words, select only the ones that are common, easily understandable, and suitable for a psychology test. Avoid obscure, archaic, or overly technical terms. Return a JSON array of up to {final_limit} of the best words from the list.

        Word List:
        {', '.join(words_to_filter)}
        
        Example Output:
        ["happy", "table", "fear", "run", "success"]
        """
        response = model.generate_content(filter_prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        filtered_words = json.loads(cleaned_text)
        print(f"AI has selected {len(filtered_words)} high-quality words.")
    except Exception as e:
        print(f"An error occurred during AI filtering: {e}")
        return

    # 4. Use Gemini AI to categorize the filtered words
    try:
        print("Asking AI to categorize the filtered words...")
        categorize_prompt = f"""
        Analyze the following list of English words. For each word, categorize it as "Positive", "Negative", or "Neutral" based on its most common connotation. Return a single, valid JSON object where each key is a word and its value is its category.
        
        Word List:
        {', '.join(filtered_words)}
        """
        response = model.generate_content(categorize_prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        categorized_words = json.loads(cleaned_text)
        print(f"Successfully categorized {len(categorized_words)} words.")
    except Exception as e:
        print(f"An error occurred during AI categorization: {e}")
        return

    # 5. Prepare and insert the final data
    words_to_insert = [
        {"word_text": word, "category": category}
        for word, category in categorized_words.items()
    ]

    try:
        print(f"Inserting {len(words_to_insert)} new words into the database...")
        supabase.table('wat_words').insert(words_to_insert).execute()
        print("Curation complete. Database has been updated with new, high-quality words.")
    except Exception as e:
        print(f"An error occurred during database insertion: {e}")

if __name__ == "__main__":
    curate_and_add_words(fetch_limit=1000, final_limit=200)