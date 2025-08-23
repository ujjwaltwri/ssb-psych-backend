# seed_tat.py

import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
from PIL import Image

# --- Initialize Services ---
load_dotenv()

# Supabase
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Stability AI
stability_api = client.StabilityInference(
    key=os.environ.get("STABILITY_API_KEY"),
    verbose=True,
    engine="stable-diffusion-xl-1024-v1-0",
)

# --- Main Script Logic ---

def generate_and_upload_images():
    # Prompts designed to create ambiguous, SSB-style images
    prompts = [
        "A photorealistic, black and white photo of a young person looking at a half-open door, ambiguous expression, dramatic lighting.",
        "1960s style photo, a group of people around a table looking at blueprints with concern, low contrast.",
        "A lonely figure standing on a hill looking down at a town in the distance at dusk, grainy photo.",
        "A young doctor sitting on the edge of a hospital bed, looking tired and thoughtful, a patient is out of focus in the background.",
        "Two people having a tense conversation across a simple wooden table. Black and white, film noir style.",
        "A person working late at night in an office, illuminated only by a desk lamp, looking stressed.",
        "A group of students working together on a difficult project, showing expressions of both frustration and determination.",
        "A figure walking away down a long, empty country road in the fog.",
        "An older person giving advice to a younger person, their faces show a mix of seriousness and care. Soft focus.",
        "A person standing at a crossroads, looking confused about which path to take. Moody lighting."
    ]

    bucket_name = "tat-images"

    print("Starting TAT image generation and upload...")

    for i, prompt_text in enumerate(prompts):
        try:
            print(f"\n({i+1}/{len(prompts)}) Generating image for prompt: '{prompt_text[:40]}...'")
            
            # 1. Generate the image using Stability AI
            answers = stability_api.generate(prompt=prompt_text, seed=random.randint(1, 10000))
            
            image_bytes = None
            for resp in answers:
                for artifact in resp.artifacts:
                    if artifact.finish_reason == generation.FILTER:
                        print("Warning: Generation failed safety filter, skipping.")
                        continue
                    if artifact.type == generation.ARTIFACT_IMAGE:
                        image_bytes = artifact.binary
            
            if not image_bytes:
                print("Image generation failed for this prompt.")
                continue

            # 2. Upload the generated image bytes to Supabase Storage
            file_name = f"generated_image_{i+1}_{random.randint(100, 999)}.png"
            print(f"Uploading '{file_name}' to Supabase Storage...")
            
            # The upload requires the file to be in bytes
            supabase.storage.from_(bucket_name).upload(file_name, image_bytes, {"content-type": "image/png"})

            # 3. Get the public URL of the uploaded image
            public_url_res = supabase.storage.from_(bucket_name).get_public_url(file_name)
            
            # 4. Save the URL to the tat_images database table
            print("Saving URL to database...")
            supabase.table("tat_images").insert({
                "image_url": public_url_res,
                "description": prompt_text
            }).execute()

            print("Successfully generated and saved image.")

        except Exception as e:
            print(f"An error occurred for a prompt: {e}")
            continue
            
    print("\nTAT image library creation complete.")

if __name__ == "__main__":
    import random
    generate_and_upload_images()