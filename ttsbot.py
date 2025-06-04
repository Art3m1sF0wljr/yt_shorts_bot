import os
import csv
import re
import edge_tts
import asyncio
from pathlib import Path
from openai import OpenAI  # New import style
from dotenv import load_dotenv

# --- Load OpenAI API Key Securely ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # New client initialization

# --- CONFIG ---
INPUT_DIR = "stories"
OUTPUT_DIR = "cleaned_stories"
INDEX_FILE = "stories/index.csv"
CLEANED_INDEX = os.path.join(OUTPUT_DIR, "index_clean.csv")

# TTS Settings
VOICE = "en-US-AriaNeural"
TTS_RATE = "+50%"

# Swear word replacement (fallback if OpenAI fails)
SWEAR_REPLACEMENTS = {
    "fuck": "mess up",
    "shit": "stuff",
    "damn": "darn",
    "asshole": "jerk",
    "bitch": "person",
    "hell": "heck",
    "fucking": "messing up",
}

def censor_text(text):
    """Replace swear words with YouTube-friendly synonyms, with improved fallback."""
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Make this YouTube-friendly by replacing swear words with natural synonyms. "
                        f"Keep the tone and meaning intact. Return ONLY the cleaned text:\n\n{text}"
                    )
                }],
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"GPT-3.5 API failed: {e}")
            raise  # Re-raise to trigger the fallback
            
    except Exception:
        print("Using enhanced regex fallback for swear words")
        # Enhanced replacements with context awareness
        replacements = {
            r'\bfuck(ing)?\b': 'mess(ing) up',
            r'\bshit\b': 'stuff',
            r'\bdamn\b': 'darn',
            r'\basshole\b': 'jerk',
            r'\bbitch\b': 'person',
            r'\bhell\b': 'heck',
            r'\bcunt\b': 'rude person',
            r'\bwhore\b': 'unprofessional',
            r'\bslut\b': 'promiscuous person',
            r'\bretard\b': 'foolish',
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Additional basic grammar fixes
        text = re.sub(r"\bi\b", "I", text)
        text = re.sub(r"\bi'm\b", "I'm", text, flags=re.IGNORECASE)
        return text
        
def clean_text(text):
    """Fix grammar and shorten text with improved fallback."""
    # Basic cleanup first
    text = re.sub(r"\*\*|__|~~|```|^>.*$", "", text)
    text = re.sub(r"\n+", "\n", text.strip())
    
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Clean this for a YouTube Short (fix grammar, make concise, keep engaging). "
                        f"Return ONLY the cleaned text:\n\n{text}"
                    )
                }],
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"GPT-3.5 API failed: {e}")
            raise
            
    except Exception:
        print("Using enhanced regex fallback for text cleaning")
        # Improved regex-based cleaning
        text = re.sub(r"(\w)'s\b", r"\1's", text)  # Fix possessives
        text = re.sub(r"(\w)n't\b", r"\1n't", text)  # Fix contractions
        text = re.sub(r"\b(u|ur)\b", "you", text, flags=re.IGNORECASE)  # Fix text speak
        text = re.sub(r"\b(plz|pls)\b", "please", text, flags=re.IGNORECASE)
        
        # Capitalize sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [sentence[0].upper() + sentence[1:] if sentence else sentence 
                    for sentence in sentences]
        text = ' '.join(sentences)
        
        return text
async def generate_tts_and_subs(text, output_path):
    """Generate TTS audio and synchronized subtitles using Edge."""
    communicate = edge_tts.Communicate(text, VOICE, rate=TTS_RATE)
    
    subs = []
    
    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Convert from 100-nanosecond units to seconds
                start = chunk["offset"] / 10_000_000
                end = (chunk["offset"] + chunk["duration"]) / 10_000_000
                
                subs.append({
                    "start": start,
                    "end": end,
                    "text": chunk["text"]
                })
    
    srt_content = ""
    for i, sub in enumerate(subs, start=1):
        start_time = format_time(sub["start"])
        end_time = format_time(sub["end"])
        srt_content += f"{i}\n{start_time} --> {end_time}\n{sub['text']}\n\n"
    
    return srt_content

def format_time(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

def save_srt(subs, output_path):
    """Save subtitles in SRT format."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(subs)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(INDEX_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|")
        rows = list(reader)

    cleaned_rows = [rows[0] + ["cleaned_text_path", "tts_path", "subtitle_path"]]

    for row in rows[1:]:
        filename, title, upvotes, comments, subreddit, _, _, _, _, url, _, _, _ = row
        input_path = os.path.join(INPUT_DIR, filename)

        base_name = Path(filename).stem
        cleaned_text_path = os.path.join(OUTPUT_DIR, f"{base_name}_cleaned.txt")
        tts_path = os.path.join(OUTPUT_DIR, f"{base_name}_tts.mp3")
        subtitle_path = os.path.join(OUTPUT_DIR, f"{base_name}_subs.srt")

        if all(os.path.exists(p) for p in [cleaned_text_path, tts_path, subtitle_path]):
            print(f"Skipping {filename} (already processed)")
            cleaned_rows.append(row + [cleaned_text_path, tts_path, subtitle_path])
            continue

        with open(input_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_text(raw_text)

        with open(cleaned_text_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        print(f"Generating TTS and subtitles for {filename}...")
        subs = asyncio.run(generate_tts_and_subs(cleaned_text, tts_path))
        save_srt(subs, subtitle_path)

        cleaned_rows.append(row + [cleaned_text_path, tts_path, subtitle_path])

    with open(CLEANED_INDEX, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerows(cleaned_rows)

if __name__ == "__main__":
    main()
