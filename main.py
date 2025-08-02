import os
import logging
import json
import google.generativeai as genai
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from code_executor import run_code_in_sandbox

# --- Setup Section ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except TypeError:
    logger.error("GOOGLE_API_KEY not found. Please check your .env file.")
    exit()

# --- FastAPI App Initialization ---
app = FastAPI()

def create_code_generation_prompt(task_description, context=""):
    """Generates a prompt for the LLM to write file-based code."""
    return f"""
You are an expert Python data scientist. Your task is to write a Python script to perform a specific task.
All file operations must use the '/app/workspace/' directory.

Context from previous steps:
{context}

Your current task:
'{task_description}'

Write only the Python code for this task. Do not use markdown.
Your script's final output to stdout should be a single-line JSON string describing the result.
"""

# --- API Endpoint ---
@app.post("/api/")
async def create_analysis(question: UploadFile = File(...)):
    question_content = (await question.read()).decode("utf-8")
    
    url = "https://en.wikipedia.org/wiki/List_of_highest-grossing_films"
    workspace_dir = "workspace"
    sampler_output_file = os.path.join(workspace_dir, "scraped_table.html")
    final_csv_file = os.path.join(workspace_dir, "films.csv")
    
    # Clean workspace
    if os.path.exists(sampler_output_file):
        os.remove(sampler_output_file)
    if os.path.exists(final_csv_file):
        os.remove(final_csv_file)

    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    # --- Stage 1: HTML Sampling & Saving ---
    logger.info("--- Starting Stage 1: HTML Sampling & Saving ---")
    sampler_task = (
        f"Download the page at '{url}' using requests with a 'User-Agent' header. "
        "Find the main data table (the one with 'Rank' and 'Title' in its headers). "
        f"Save the full outer HTML of this table to '/app/workspace/scraped_table.html'."
    )
    sampler_prompt = create_code_generation_prompt(sampler_task)
    sampler_response = model.generate_content(sampler_prompt)
    sampler_code = sampler_response.text.replace("```python", "").replace("```", "").strip()
    sampler_result = run_code_in_sandbox(sampler_code)

    if sampler_result.get("stderr") or not os.path.exists(sampler_output_file):
        return JSONResponse(status_code=500, content={"error": "Stage 1 (sampler) failed to create the output file."})

    # --- Stage 2: Parsing and CLEANING Data to CSV ---
    logger.info("--- Starting Stage 2: Parsing and Cleaning to CSV ---")
    
    # vv --- THIS IS THE KEY CHANGE --- vv
    scraper_task = (
        "Read the HTML from '/app/workspace/scraped_table.html'. Parse it to a pandas DataFrame. "
        "CRITICAL: Before saving, you must aggressively clean the 'Worldwide gross' column. "
        "First, remove specific leading footnote characters that are sometimes attached to the numbers (e.g., 'T', 'F', 'SM', 'F8'). "
        "After removing those, then remove all other non-numeric characters like '$', ',', '#', '[', ']', and extra spaces. "
        "Finally, save the fully cleaned DataFrame (Rank, Peak, Title, Worldwide gross, Year) to a CSV file at '/app/workspace/films.csv'."
    )
    # ^^ --- END KEY CHANGE --- ^^
    
    scraper_prompt = create_code_generation_prompt(scraper_task)
    scraper_response = model.generate_content(scraper_prompt)
    scraper_code = scraper_response.text.replace("```python", "").replace("```", "").strip()
    scraper_result = run_code_in_sandbox(scraper_code)

    if scraper_result.get("stderr") or not os.path.exists(final_csv_file):
        logger.error(f"Stage 2 (scraper) failed. Details: {scraper_result}")
        return JSONResponse(status_code=500, content={"error": "Stage 2 (scraper) failed to create the final CSV file."})

    # --- Stage 3: Final Analysis ---
    logger.info("--- Starting Stage 3: Final Analysis ---")
    analysis_task = (
        f"The film data is at '/app/workspace/films.csv'. Load it into a pandas DataFrame. "
        "The columns should already be clean, but as a safeguard, ensure 'Worldwide gross', 'Year', and 'Peak' are numeric types (`pd.to_numeric` with `errors='coerce'`). Drop any rows with NaN values. "
        "The column with the film names is 'Title'. "
        "Now, write a single script to produce the final answers for the user's request.\n\n"
        f"User Request:\n---\n{question_content}\n---\n"
        "The script's final output to stdout MUST be a single line containing a valid JSON array with exactly 4 elements matching the user's questions. "
        "The 4th element must be a base64-encoded PNG image as a data URI string."
    )
    analysis_prompt = create_code_generation_prompt(analysis_task)
    analysis_response = model.generate_content(analysis_prompt)
    analysis_code = analysis_response.text.replace("```python", "").replace("```", "").strip()
    analysis_result = run_code_in_sandbox(analysis_code)

    if analysis_result.get("stderr"):
        logger.error(f"Stage 3 (analysis) failed. Details: {analysis_result}")
        return JSONResponse(status_code=500, content={"error": "Stage 3 (analysis) failed."})

    # --- Return the Final Answer ---
    try:
        final_answer = json.loads(analysis_result["stdout"])
        logger.info("Agent successfully completed all stages and generated the final answer.")
        return JSONResponse(content=final_answer)
    except (json.JSONDecodeError, IndexError):
        logger.error(f"Failed to parse final answer from script stdout. Raw output: {analysis_result['stdout']}")
        return JSONResponse(status_code=500, content={"error": "Failed to parse the final JSON array from the analysis script."})