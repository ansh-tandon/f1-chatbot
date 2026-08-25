import os
from app.config import get_settings

settings = get_settings()

GEMINI_MODEL = "gemini-3.6-flash"
OPENAI_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are an expert F1 Data Analyst AI specializing in the 2024 Monaco Grand Prix, with deep knowledge of Charles Leclerc (Ferrari) and Lando Norris (McLaren).

Your goal is to provide THOROUGH, IN-DEPTH analysis that a serious F1 fan or engineer would appreciate.

RULES:
1. Depth: Give comprehensive, detailed answers. Explain the WHY behind the data — don't just state facts, analyze them. Compare strategies, explain trade-offs, reference specific lap numbers, sector times, and tyre compounds when available.
2. Grounding: Answer using ONLY the provided structured context (FastF1 telemetry, Neo4j graph data, PostgreSQL tables, and Qdrant documents). Cite specific data points (lap times, deltas, stint lengths) to back up your analysis.
3. Accuracy: Do not invent lap times, sector deltas, or team quotes. If data is missing or insufficient, state it clearly.
4. Format: Write in flowing, analytical paragraphs. Use bullet points for comparisons and key metrics. Bold important numbers and driver names for scannability. Do NOT use rigid labels like "Answer:", "Evidence:", or "Sources:".
5. Length: Aim for 3-5 detailed paragraphs minimum. Short one-liner responses are not acceptable — always provide context, analysis, and insight.
6. Scope: Monaco 2024 Qualifying and Race sessions for Leclerc (LEC, Ferrari SF-24) and Norris (NOR, McLaren MCL38).
"""


def ask_llm(question: str, context: str) -> str:
    """
    Send question + structured context to Gemini (or OpenAI fallback).
    Returns the LLM's grounded answer.
    """
    user_message = f"""Question: {question}

--- STRUCTURED CONTEXT ---
{context}
--- END CONTEXT ---

Please answer the question using ONLY the data in the context above. Follow the answer format exactly."""

    gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gemini_key:
        try:
            try:
                import google.genai as genai
                from google.genai import types
                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=1500,
                    ),
                )
                return response.text or "No response generated."
            except (ImportError, ModuleNotFoundError):
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=SYSTEM_PROMPT,
                )
                response = model.generate_content(
                    user_message,
                    generation_config={"temperature": 0.2, "max_output_tokens": 1500},
                )
                return response.text or "No response generated."
        except Exception as e:
            return f"Gemini LLM error: {str(e)}. Please check your GEMINI_API_KEY in .env."

    elif settings.openai_api_key:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.openai_api_key)
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=1500,
            )
            return response.choices[0].message.content or "No response generated."
        except Exception as e:
            return f"OpenAI LLM error: {str(e)}. Please check your OPENAI_API_KEY in .env."

    else:
        return "Error: No API key provided. Please configure GEMINI_API_KEY or OPENAI_API_KEY in backend/.env."
