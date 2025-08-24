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
    """Health check endpoint for Render."""
    return {"status": "ok", "message": "PsychePrep API is healthy"}

@app.get("/api/new-wat-test")
def get_new_wat_test():
    """Fetches a randomized set of words for a new WAT session."""
    try:
        words_res = supabase.table('wat_words').select('word_text').execute()
        words = [item['word_text'] for item in words_res.data]
        random.shuffle(words)
        return {"words": words[:60]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch words: {e}")

@app.get("/api/new-srt-test")
def get_new_srt_test():
    """Fetches a random set of situations for a new SRT session."""
    try:
        situations_res = supabase.table('srt_situations').select('situation_text').execute()
        situations = [item['situation_text'] for item in situations_res.data]
        random.shuffle(situations)
        return {"situations": situations[:60]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch situations: {e}")

@app.post("/api/save-wat-session")
async def save_wat_session(session_data: WatSessionData, current_user = Depends(get_current_user)):
    """Saves the results of a completed WAT session to the database."""
    try:
        responses_list = [response.dict() for response in session_data.responses]
        data_to_insert = {"user_id": current_user.id, "test_type": "WAT", "responses": responses_list}
        res = supabase.table('test_sessions').insert(data_to_insert).execute()
        return {"message": "Session saved successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/api/save-srt-session")
async def save_srt_session(session_data: SrtSessionData, current_user = Depends(get_current_user)):
    """Saves the results of a completed SRT session to the database."""
    try:
        responses_list = [response.dict() for response in session_data.responses]
        data_to_insert = {"user_id": current_user.id, "test_type": "SRT", "responses": responses_list}
        res = supabase.table('test_sessions').insert(data_to_insert).execute()
        return {"message": "Session saved successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/api/analyze-session/{session_id}")
async def analyze_session(session_id: int, current_user = Depends(get_current_user)):
    """Fetches a saved session, sends it to the Gemini API for analysis, and saves the result."""
    try:
        session_res = supabase.table('test_sessions').select('responses, test_type').eq('id', session_id).eq('user_id', current_user.id).single().execute()
        if not session_res.data:
            raise HTTPException(status_code=404, detail="Session not found or access denied.")
        
        responses = session_res.data['responses']
        test_type = session_res.data['test_type']
        
        if test_type == 'WAT':
            formatted_responses = "\n".join([f"- {item['word']}: {item['response']}" for item in responses if item['response']])
            prompt_template = "You are an expert defense psychologist evaluating a candidate for an officer role based on their Word Association Test (WAT) responses."
        elif test_type == 'SRT':
            formatted_responses = "\n".join([f"- Situation: {item['situation']}\n  - Response: {item['response']}" for item in responses if item['response']])
            prompt_template = "You are an expert defense psychologist evaluating a candidate for an officer role based on their Situation Reaction Test (SRT) responses. Analyze the candidate's reactions for problem-solving skills, responsibility, and calmness under pressure."
        else:
            raise HTTPException(status_code=400, detail=f"Analysis for test type '{test_type}' not supported.")

        prompt = f"""
        {prompt_template}

        **Candidate's Responses:**
        {formatted_responses}

        **Your Task:**
        Provide a deep and insightful psychological analysis.

        **Output Format:**
        Return your analysis as a single, valid JSON object with the following keys:
        - "overall_summary": A brief, 2-3 sentence summary of the candidate's psychological profile.
        - "positive_traits": A bulleted list of 3-4 key positive qualities observed.
        - "areas_for_improvement": A bulleted list of 2-3 potential areas for the candidate to reflect upon.
        - "olq_rating": An object rating a comprehensive set of OLQs on a scale of 1-5 (1=Low, 5=High). The keys must be exactly: "effective_intelligence", "reasoning_ability", "organizing_ability", "power_of_expression", "social_adaptability", "cooperation", "sense_of_responsibility", "initiative", "self_confidence", "speed_of_decision", "determination", "courage".
        - "selection_potential_analysis": A candid, 2-4 sentence analysis of the candidate's selection potential based ONLY on these responses. DO NOT give a definitive 'recommended' or 'not recommended' verdict. Instead, frame it as a coach would, highlighting which thought patterns strongly align with selection standards and which patterns might be considered red flags or require immediate attention. The tone should be realistic but encouraging.
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
        print(f"A major error occurred during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred during analysis: {e}")