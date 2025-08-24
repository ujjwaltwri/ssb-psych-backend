import os
import random
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from supabase import create_client, Client
import google.generativeai as genai

# Load Environment Variables & Initialize Services
load_dotenv()
app = FastAPI()

# Supabase Client
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Google Gemini Client
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# CORS Middleware
origins = ["http://localhost:3000", "https://psycheprep.vercel.app"] 
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models for Data Validation
class WatResponse(BaseModel):
    word: str
    response: str

class WatSessionData(BaseModel):
    responses: List[WatResponse]

class SrtResponse(BaseModel):
    situation: str
    response: str

class SrtSessionData(BaseModel):
    responses: List[SrtResponse]

# Dependency to get current user from JWT
async def get_current_user(request: Request):
    token = request.headers.get('authorization', '').replace('Bearer ', '')
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user_res = supabase.auth.get_user(token)
        return user_res.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

# --- API Endpoints ---
@app.get("/")
def health_check():
    return {"status": "ok", "message": "PsychePrep API is healthy"}

@app.get("/api/new-wat-test")
def get_new_wat_test():
    try:
        words_res = supabase.table('wat_words').select('word_text').execute()
        words = [item['word_text'] for item in words_res.data]
        random.shuffle(words)
        return {"words": words[:60]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch words: {e}")

@app.get("/api/new-srt-test")
def get_new_srt_test():
    try:
        situations_res = supabase.table('srt_situations').select('situation_text').execute()
        situations = [item['situation_text'] for item in situations_res.data]
        random.shuffle(situations)
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
            raise HTTPException(status_code=404, detail="Session not found or access denied.")
        
        responses = session_res.data['responses']
        test_type = session_res.data['test_type']
        if not any(item.get('response', '').strip() for item in responses):
            raise HTTPException(status_code=400, detail="Cannot analyze a session with no responses.")

        if test_type == 'WAT':
            formatted_responses = "\n".join([f"- {item['word']}: {item['response']}" for item in responses if item['response']])
            prompt_template = "Word Association Test (WAT)"
        elif test_type == 'SRT':
            formatted_responses = "\n".join([f"- Situation: {item['situation']}\n  - Response: {item['response']}" for item in responses if item['response']])
            prompt_template = "Situation Reaction Test (SRT)"
        else:
            raise HTTPException(status_code=400, detail=f"Analysis for test type '{test_type}' not supported.")

        prompt = f"""
        **ROLE:** You are a skeptical senior psychologist at a military Service Selection Board (SSB). Your job is to find weaknesses and screen out candidates who are not suitable for officer training. Your tone must be brutally honest, direct, and critical. Do not offer encouragement or praise unless it is exceptionally warranted. Focus on flaws.

        **CONTEXT:** A candidate has completed a {prompt_template}. Their responses are provided below.

        **CANDIDATE'S RESPONSES:**
        {formatted_responses}

        **YOUR TASK:**
        Critically analyze these responses to identify psychological weaknesses, negative thought patterns, and deficiencies in Officer Like Qualities (OLQs). For every assertion you make, you MUST quote the specific response as evidence.

        **OUTPUT FORMAT:**
        Return your analysis as a single, valid JSON object with the following keys:
        - "overall_summary": A blunt, 1-2 sentence assessment of the candidate's primary psychological characteristics as revealed by this test.
        - "positive_traits": A very brief, bulleted list of any 1-2 genuinely officer-like qualities demonstrated. Be highly critical; do not list mediocre points.
        - "areas_for_improvement": A detailed, bulleted list of the most significant psychological concerns, red flags, and weaknesses. For each point, state the issue clearly, quote the evidence, and explain why it is a concern for a military officer.
        - "olq_rating": An object rating a comprehensive set of OLQs on a scale of 1-5 (1=Poor, 2=Below Average, 3=Average, 4=Good, 5=Excellent). Be a harsh grader. Average performance is not good enough.
        - "final_verdict": A single, direct sentence stating whether this performance raises significant concerns about the candidate's suitability for a commission. Do not equivocate.
        """
        
        ai_response = model.generate_content(prompt)
        
        try:
            cleaned_json_string = ai_response.text.strip().replace("```json", "").replace("```", "")
            analysis_json = json.loads(cleaned_json_string)
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"Error parsing AI response: {e}")
            print(f"Raw AI response was: {ai_response.text}")
            raise HTTPException(status_code=500, detail="The AI returned an invalid response format. Please try analyzing again.")

        update_res = supabase.table('test_sessions').update({
            'analysis': analysis_json,
            'responses': responses
        }).eq('id', session_id).execute()

        if not update_res.data:
             raise HTTPException(status_code=500, detail="Failed to save analysis.")

        return {"message": "Analysis complete", "analysis": update_res.data[0]['analysis']}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"A major error occurred during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))