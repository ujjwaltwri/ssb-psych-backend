# seed_srt.py

import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

# --- Load Environment Variables & Initialize Services ---
load_dotenv()

# Supabase
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Google Gemini
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Main Script Logic ---

def generate_situations():
    themes = [
        "social adaptability and cooperation",
        "sense of responsibility",
        "initiative and self-confidence",
        "speed of decision and determination",
        "courage and integrity",
        "handling pressure and unexpected events",
        "leadership and group influence",
        "effective intelligence and resourcefulness"
    ]
    
    all_new_situations = []

    print("Starting situation generation with Gemini API...")

    for theme in themes:
        print(f"Generating situations for theme: {theme}...")
        try:
            prompt = f"""
            Create 15 unique, short, and practical situations that a young adult might face, designed to test for the Officer Like Quality theme of '{theme}'. The situations should be diverse, covering scenarios at college, with friends, during travel, or in a professional setting.

            Present the output as a single, valid JSON array of strings. For example:
            ["situation 1 text...", "situation 2 text..."]
            """
            
            response = model.generate_content(prompt)
            # Clean up the response to get a valid JSON array
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            situations = json.loads(cleaned_text)
            
            for sit in situations:
                all_new_situations.append({
                    "situation_text": sit,
                    "primary_olq_theme": theme
                })
            
            print(f"Successfully generated {len(situations)} situations for '{theme}'.")

        except Exception as e:
            print(f"An error occurred while generating situations for theme '{theme}': {e}")
            continue # Move to the next theme even if one fails

    if not all_new_situations:
        print("No new situations were generated. Exiting.")
        return

    print(f"\nTotal new situations generated: {len(all_new_situations)}")
    
    try:
        print("Inserting situations into the Supabase database...")
        data, count = supabase.table('srt_situations').insert(all_new_situations).execute()
        print("Successfully inserted all new situations into the database!")
    except Exception as e:
        print(f"An error occurred during database insertion: {e}")


if __name__ == "__main__":
    generate_situations()