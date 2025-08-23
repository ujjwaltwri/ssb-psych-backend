# seed_tat_unsplash_simple.py
import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from unsplash.api import Api
from unsplash.auth import Auth

# --- Initialize Services ---
load_dotenv()

# Supabase
supabase_url: str = os.environ.get("SUPABASE_URL")
# Temporarily use the service_role key to bypass RLS for this script
service_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdxdnR4emRjaWh3a2R0bHlnaXp6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTgxNTIwMywiZXhwIjoyMDcxMzkxMjAzfQ.lpHthU5bs4IXZ17rICCy8KysvjH0SngxaZA30gcEJ9c"
supabase: Client = create_client(supabase_url, service_key)

# Unsplash
unsplash_access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
auth = Auth(unsplash_access_key, "", "", "")
api = Api(auth)

def check_image_exists_in_db(photo_id):
    """Check if an image with this photo ID already exists in the database"""
    try:
        result = supabase.table("tat_images").select("id").ilike("description", f"%{photo_id}%").execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"  - Error checking existing image in DB: {e}")
        return False

def fetch_and_upload_images():
    search_keywords = [
        "lonely black and white", "challenge silhouette", "tense meeting", 
        "decision path", "doubt portrait", "helping hand monochrome",
        "teamwork struggle", "looking out window sad", "ambiguous face",
        "contemplation shadow", "group conflict", "isolated figure"
    ]
    
    images_per_keyword = 3  # Reduced to avoid too many duplicates
    bucket_name = "tat-images"
    successful_uploads = 0
    skipped_count = 0
    error_count = 0
    
    print("Starting TAT image seeding from Unsplash...")
    
    for keyword in search_keywords:
        try:
            print(f"\nSearching for images with keyword: '{keyword}'...")
            
            search_results = api.search.photos(keyword, per_page=images_per_keyword)
            
            if not search_results or 'results' not in search_results:
                print(f"  - No results found for '{keyword}'")
                continue
            
            for photo in search_results['results']:
                photo_id = photo.id
                file_name = f"unsplash_{photo_id}.jpg"
                
                print(f"  - Processing photo ID: {photo_id}")
                
                # Check if already exists in database
                if check_image_exists_in_db(photo_id):
                    print(f"  - Skipping {photo_id} (already in database)")
                    skipped_count += 1
                    continue
                
                try:
                    # Download image
                    photo_url = photo.urls.regular
                    image_response = requests.get(photo_url, stream=True, timeout=30)
                    image_response.raise_for_status()
                    image_bytes = image_response.content
                    
                    # Try to upload to storage (with upsert to handle duplicates)
                    try:
                        upload_result = supabase.storage.from_(bucket_name).upload(
                            file_name, 
                            image_bytes, 
                            {"content-type": "image/jpeg", "upsert": "true"}  # Allow overwrite
                        )
                    except Exception as storage_error:
                        # If file already exists, try to get its public URL anyway
                        if "already exists" in str(storage_error).lower() or "duplicate" in str(storage_error).lower():
                            print(f"  - File {file_name} already exists in storage, using existing file")
                        else:
                            raise storage_error
                    
                    # Get public URL
                    public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
                    
                    # Insert into database (only with existing columns)
                    db_result = supabase.table("tat_images").insert({
                        "image_url": public_url,
                        "description": f"Unsplash photo by {photo.user.name} - Keyword: '{keyword}' - ID: {photo_id}"
                    }).execute()
                    
                    print(f"  - Successfully saved {file_name}")
                    successful_uploads += 1
                    
                except Exception as photo_error:
                    print(f"  - Error processing photo {photo_id}: {photo_error}")
                    error_count += 1
                    continue
                    
        except Exception as keyword_error:
            print(f"An error occurred for keyword '{keyword}': {keyword_error}")
            error_count += 1
            continue
    
    print(f"\nTAT image library seeding complete!")
    print(f"Successfully uploaded: {successful_uploads}")
    print(f"Skipped (duplicates): {skipped_count}")
    print(f"Errors: {error_count}")

def show_current_images():
    """Show what images are currently in the database"""
    try:
        result = supabase.table("tat_images").select("*").execute()
        print(f"\nCurrently have {len(result.data)} images in database:")
        for i, img in enumerate(result.data[:10], 1):  # Show first 10
            desc = img.get('description', 'No description')[:80]
            print(f"  {i}. {desc}...")
        if len(result.data) > 10:
            print(f"  ... and {len(result.data) - 10} more")
    except Exception as e:
        print(f"Error fetching existing images: {e}")

if __name__ == "__main__":
    # Show current state
    show_current_images()
    
    # Run the seeding
    fetch_and_upload_images()
    
    # Show final state
    show_current_images()