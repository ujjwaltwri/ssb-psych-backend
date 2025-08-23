# main.py

import os
import random
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

from supabase import create_client, Client
import google.generativeai as genai

# --- Load Environment Variables & Initialize Services ---
load_dotenv()
app = FastAPI()
@app.get("/")
def health_check():
    return {"status": "ok", "message": "PsychePrep API is healthy"}
# Supabase & Gemini Clients
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# CORS Middleware
origins = ["http://localhost:3000", "https://psycheprep.vercel.app"] # Added deployed URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class WatResponse(BaseModel):
    word: str
    response: str
class WatSessionData(BaseModel):
    responses: List[WatResponse]

# --- NEW Pydantic Models for SRT ---
class SrtResponse(BaseModel):
    situation: str
    response: str
class SrtSessionData(BaseModel):
    responses: List[SrtResponse]

# --- Authentication ---
async def get_current_user(request: Request):
    token = request.headers.get('authorization', '').replace('Bearer ', '')
    if not token: raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user_res = supabase.auth.get_user(token)
        return user_res.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

# --- API Endpoints ---

@app.get("/api/new-wat-test")
def get_new_wat_test():
    try:
        words_res = supabase.table('wat_words').select('word_text').execute()
        words = [item['word_text'] for item in words_res.data]
        random.shuffle(words)
        return {"words": words[:60]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch words: {e}")

# --- NEW Endpoint to get SRT test ---
@app.get("/api/new-srt-test")
def get_new_srt_test():
    try:
        situations_res = supabase.table('srt_situations').select('situation_text').execute()
        situations = [item['situation_text'] for item in situations_res.data]
        random.shuffle(situations)
        # This line MUST return a dictionary with the key "situations"
        return {"situations": situations[:60]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch situations: {e}")

@app.post("/api/save-wat-session")
async def save_wat_session(session_data: WatSessionData, current_user = Depends(get_current_user)):
    try:
        responses_list = [response.dict() for response in session_data.responses]
        data_to_insert = {"user_id": current_user.id, "test_type": "WAT", "responses": responses_list}
        res = supabase.table('test_sessions').insert(data_to_insert).execute()
        return {"message": "Session saved successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

# --- NEW Endpoint to save SRT session ---
@app.post("/api/save-srt-session")
async def save_srt_session(session_data: SrtSessionData, current_user = Depends(get_current_user)):
    try:
        responses_list = [response.dict() for response in session_data.responses]
        data_to_insert = {"user_id": current_user.id, "test_type": "SRT", "responses": responses_list}
        res = supabase.table('test_sessions').insert(data_to_insert).execute()
        return {"message": "Session saved successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/api/analyze-session/{session_id}")
async def analyze_session(session_id: int, current_user = Depends(get_current_user)):
    try:
        session_res = supabase.table('test_sessions').select('responses, test_type').eq('id', session_id).eq('user_id', current_user.id).single().execute()
        if not session_res.data:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        responses = session_res.data['responses']
        test_type = session_res.data['test_type']
        
        # --- UPDATED to handle different test types ---
        if test_type == 'WAT':
            formatted_responses = "\n".join([f"- {item['word']}: {item['response']}" for item in responses if item['response']])
            # (The detailed WAT prompt is the same as before)
            prompt = f"""You are an expert defense psychologist... (rest of WAT prompt)"""
        elif test_type == 'SRT':
            formatted_responses = "\n".join([f"- Situation: {item['situation']}\n  - Response: {item['response']}" for item in responses if item['response']])
            prompt = f"""
            You are an expert defense psychologist evaluating a candidate for an officer role based on their Situation Reaction Test (SRT) responses.

            **Candidate's Responses:**
            {formatted_responses}

            **Your Task:**
            Analyze the candidate's reactions. Assess their problem-solving skills, sense of responsibility, calmness under pressure, and social adaptability. The responses should ideally be practical, optimistic, and show officer-like qualities.

            **Output Format:**
            Return your analysis as a single, valid JSON object with the same keys as the WAT analysis (overall_summary, positive_traits, areas_for_improvement, olq_rating, selection_potential_analysis).
            """
        else:
            raise HTTPException(status_code=400, detail=f"Analysis for test type '{test_type}' not supported.")

        ai_response = model.generate_content(prompt)
        cleaned_json_string = ai_response.text.strip().replace("```json", "").replace("```", "")
        analysis_json = json.loads(cleaned_json_string)
        
        update_res = supabase.table('test_sessions').update({'analysis': analysis_json}).eq('id', session_id).execute()

        return {"message": "Analysis complete", "analysis": update_res.data[0]['analysis']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during analysis: {e}")
    # Server startup
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)