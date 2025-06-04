import os
import random
import subprocess
import re
from pydub import AudioSegment
from dotenv import load_dotenv
import textwrap
from datetime import datetime, timedelta

# --- Load OpenAI API Key Securely ---
load_dotenv()

# Config
CLEANED_STORIES_DIR = "./cleaned_stories"
PROCESSED_VIDEOS_DIR = "./processed_videos"
OUTPUT_DIR = "./videos"
FONTS_DIR = "./fonts"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# Style Configuration
STYLE_CONFIG = {
    "font_primary": "Impact",
    "font_fallback": ["BebasNeue-Regular", "Helvetica-Bold", "Verdana-Bold"],
    "font_size": 20,
    "font_color": "white",
    "outline_color": "black",
    "outline_width": 2,
    "background_opacity": 0.9,
    "background_color": "black",
    "text_align": "center",
    "word_wrap": 24,
    "margin_v": 300,
    "margin_h": 50,
    "blur_strength": 0.1,
    "glow_effect": True,
    "glow_color": "0xFFFF00",
    "glow_strength": 0.5,
    "text_shadow": True,
    "shadow_color": "black",
    "shadow_strength": 0.6,
    "subtitles_duration_buffer": 0.2,
    "video_effects": {
        "blur": True,
        "saturation": 1.2,
        "contrast": 1.05,
        "vignette": True
    }
}

def get_base_filename(filename):
    """Extract base filename without extension and suffix"""
    # Remove known suffixes and extension
    for suffix in ['_tts', '_cleaned', '_subs', '.mp3', '.txt', '.srt']:
        filename = filename.replace(suffix, '')
    return filename

def get_available_fonts():
    """Check which fonts are available on the system with better verification"""
    available_fonts = []
    font_candidates = [STYLE_CONFIG["font_primary"]] + STYLE_CONFIG["font_fallback"]
    
    for font in font_candidates:
        try:
            # Check system fonts
            result = subprocess.run(
                ["fc-match", "-f", "%{file}\n", font],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(result.stdout.strip()):
                available_fonts.append(font)
                continue
                
            # Check local fonts directory
            local_font = os.path.join(FONTS_DIR, f"{font}.ttf")
            if os.path.exists(local_font):
                available_fonts.append(f"'{local_font}'")  # Quoted path
                
        except Exception:
            continue
            
    return available_fonts if available_fonts else ["Arial"]

def preprocess_srt(srt_path):
    """
    Process SRT file to show one word at a time with proper timing
    Returns path to processed SRT file
    """
    if not os.path.exists(srt_path):
        raise ValueError(f"SRT file not found: {srt_path}")

    temp_dir = os.path.join(OUTPUT_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    base_name = os.path.basename(srt_path)
    temp_srt_path = os.path.join(temp_dir, f"word_by_word_{base_name}")

    try:
        with open(srt_path, 'r', encoding='utf-8') as infile, \
             open(temp_srt_path, 'w', encoding='utf-8') as outfile:
            
            current_block = []
            block_number = 1
            word_index = 0
            
            for line in infile:
                line = line.strip()
                
                if line.isdigit():
                    if current_block:
                        _write_word_by_word_block(current_block, block_number, outfile)
                        block_number += len(current_block[2][1].split())  # Increment by word count
                        current_block = []
                    current_block.append(line)
                    
                elif '-->' in line:
                    current_block.append(line)
                    
                elif line:
                    current_block.append(line)
                    
                else:
                    if current_block:
                        _write_word_by_word_block(current_block, block_number, outfile)
                        block_number += len(current_block[2].split())  # Increment by word count
                        current_block = []
                    outfile.write('\n')
            
            if current_block:
                _write_word_by_word_block(current_block, block_number, outfile)

        os.replace(temp_srt_path, srt_path)
        return srt_path

    except Exception as e:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)
        raise RuntimeError(f"Failed to process SRT file: {e}")

def _write_word_by_word_block(block, start_block_number, outfile):
    """Write a subtitle block as individual words with precise timing"""
    if len(block) < 3:
        return

    # Parse original timecodes
    timecode_line = block[1]
    start, end = timecode_line.split(' --> ')
    start_time = datetime.strptime(start.strip(), "%H:%M:%S,%f")
    end_time = datetime.strptime(end.strip(), "%H:%M:%S,%f")
    
    total_duration = (end_time - start_time).total_seconds()
    words = block[2].split()
    word_count = len(words)
    
    if word_count == 0:
        return
    
    word_duration = total_duration / word_count
    
    # Write each word as separate subtitle
    for i, word in enumerate(words):
        word_start = start_time + timedelta(seconds=i * word_duration)
        word_end = start_time + timedelta(seconds=(i + 1) * word_duration)
        
        outfile.write(f"{start_block_number + i}\n")
        outfile.write(
            f"{word_start.strftime('%H:%M:%S,%f')[:-3]} --> "
            f"{word_end.strftime('%H:%M:%S,%f')[:-3]}\n"
        )
        outfile.write(f"{word}\n\n")

def _write_block(block, buffer, outfile):
    """Helper function to write a single subtitle block"""
    # Block structure: [ (line_num, content), ... ]
    if len(block) < 3:
        return  # Incomplete block
    
    # Write block number
    outfile.write(f"{block[0][1]}\n")
    
    # Process and write timecodes
    if isinstance(block[1][1], tuple):
        start_time, end_time = block[1][1]
        # Convert to timedelta for arithmetic operations
        start_td = timedelta(
            hours=start_time.hour,
            minutes=start_time.minute,
            seconds=start_time.second,
            microseconds=start_time.microsecond
        )
        end_td = timedelta(
            hours=end_time.hour,
            minutes=end_time.minute,
            seconds=end_time.second,
            microseconds=end_time.microsecond
        )
        
        # Apply buffer (ensuring we don't go negative)
        buffered_start = max(timedelta(), start_td - buffer)
        buffered_end = end_td + buffer
        
        # Convert back to datetime for formatting
        buffered_start_dt = datetime.min + buffered_start
        buffered_end_dt = datetime.min + buffered_end
        
        outfile.write(
            f"{buffered_start_dt.strftime('%H:%M:%S,%f')[:-3]} --> "
            f"{buffered_end_dt.strftime('%H:%M:%S,%f')[:-3]}\n"
        )
    
    # Write wrapped text lines
    for line in block[2:]:
        if isinstance(line[1], str):
            outfile.write(f"{line[1]}\n")
    
    outfile.write("\n")

def apply_video_effects(input_video, output_video, effects_config):
    """Apply visual effects to make background more engaging"""
    try:
        effect_filters = []
        
        if effects_config.get("blur", False):
            effect_filters.append("boxblur=2:1")
        
        if effects_config.get("saturation", 1.0) != 1.0 or effects_config.get("contrast", 1.0) != 1.0:
            effect_filters.append(f"eq=saturation={effects_config.get('saturation', 1.0)}:contrast={effects_config.get('contrast', 1.0)}")
        
        if effects_config.get("vignette", False):
            effect_filters.append("vignette=PI/4")
        
        if effect_filters:
            filter_chain = ','.join(effect_filters)
            subprocess.run(
                f"ffmpeg -y -i {input_video} -vf \"{filter_chain}\" -c:a copy {output_video}",
                shell=True,
                check=True
            )
            return output_video
        
        return input_video
    except Exception as e:
        print(f"Video effects failed, using original: {e}")
        return input_video

def create_short_video(tts_audio_path, srt_path, video_pool):
    """Create engaging YouTube short using existing subtitles"""
    base_name = get_base_filename(os.path.basename(tts_audio_path))
    output_path = os.path.join(OUTPUT_DIR, f"{base_name}_short.mp4")
    final_output_path = os.path.join(OUTPUT_DIR, f"{base_name}_final.mp4")
    temp_dir = os.path.join(OUTPUT_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        audio = AudioSegment.from_mp3(tts_audio_path)
        audio_duration = len(audio) / 1000.0
    except Exception as e:
        raise RuntimeError(f"Failed to load audio: {e}")

    video_path = random.choice(video_pool)
    
    # Process SRT file
    processed_srt_path = os.path.join(temp_dir, f"{base_name}_processed.srt")
    subprocess.run(["cp", srt_path, processed_srt_path], check=True)
    preprocess_srt(processed_srt_path)

    available_fonts = get_available_fonts()
    font_choice = available_fonts[0] if available_fonts else "Arial"
    print(f"Using font: {font_choice}")

    # Enhanced subtitle style with proper centering and visibility
    subtitle_style = (
        f"FontName={font_choice},"
        f"FontSize={STYLE_CONFIG['font_size']},"
        f"PrimaryColour=&H00FFFFFF,"  # White text
        f"Bold=1,"
        f"OutlineColour=&H00000000,"  # Black outline
        f"Outline={STYLE_CONFIG['outline_width']},"
        f"Alignment=2,"  # 2 = center alignment
        f"MarginV=100,"  # Small margin from bottom
        f"MarginH=20,"  # Small horizontal margin
        f"BorderStyle=3,"  # Opaque box
        f"BackColour=&H80000000"  # Semi-transparent black background
    )

    # Build the filter chain with proper subtitle rendering
    escaped_srt_path = processed_srt_path.replace("'", "'\\''")  # Proper escaping for shell

    filter_complex = (
        f"[0:v]scale=w=-2:h=1080,setsar=1[scaled];"
        f"[scaled]subtitles='{escaped_srt_path}':force_style='{subtitle_style}'[subtitles];"
        f"[subtitles]fps=30,format=yuv420p[outv]"
    )

    try:
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-i", tts_audio_path,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "1:a",
            "-t", str(audio_duration),
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-profile:v", "high", "-level", "4.0",
            "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", output_path
        ]
        
        print("Executing:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        
        if os.path.exists(output_path):
            # Apply subtle quality enhancements
            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", output_path,
                    "-vf", "eq=saturation=1.05:contrast=1.02",
                    "-c:a", "copy",
                    final_output_path
                ]
                print("Executing final enhancement:", " ".join(cmd))
                subprocess.run(cmd, check=True)
                
                if os.path.exists(final_output_path):
                    # Replace original with enhanced version
                    os.remove(output_path)
                    os.rename(final_output_path, output_path)
            except Exception as e:
                print(f"Video enhancement failed, using original: {e}")
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
        else:
            raise RuntimeError("Initial video creation failed")
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video composition failed: {e}")
    finally:
        if os.path.exists(processed_srt_path):
            os.remove(processed_srt_path)

    print(f"Successfully created: {output_path}")
    return output_path


def apply_video_effects(input_video, output_video, effects_config):
    """Apply visual effects to make background more engaging"""
    try:
        effect_filters = []
        
        if effects_config.get("blur", False):
            effect_filters.append("boxblur=2:1")
        
        if effects_config.get("saturation", 1.0) != 1.0 or effects_config.get("contrast", 1.0) != 1.0:
            effect_filters.append(f"eq=saturation={effects_config.get('saturation', 1.0)}:contrast={effects_config.get('contrast', 1.0)}")
        
        if effects_config.get("vignette", False):
            effect_filters.append("vignette=PI/4")
        
        if effect_filters:
            filter_chain = ','.join(effect_filters)
            cmd = [
                "ffmpeg", "-y",
                "-i", input_video,
                "-vf", filter_chain,
                "-c:a", "copy",
                output_video
            ]
            print("Executing effects:", " ".join(cmd))
            subprocess.run(cmd, check=True)
            return output_video
        
        return input_video
    except Exception as e:
        raise RuntimeError(f"Video effects processing failed: {e}")

def find_matching_files():
    """Find all matching TTS, SRT, and text files"""
    files = os.listdir(CLEANED_STORIES_DIR)
    file_groups = {}
    
    for filename in files:
        base_name = get_base_filename(filename)
        if base_name not in file_groups:
            file_groups[base_name] = {}
        
        if filename.endswith('_tts.mp3'):
            file_groups[base_name]['tts'] = filename
        elif filename.endswith('_subs.srt'):
            file_groups[base_name]['srt'] = filename
        elif filename.endswith('_cleaned.txt'):
            file_groups[base_name]['text'] = filename
    
    # Only return groups that have both TTS and SRT
    return {k: v for k, v in file_groups.items() if 'tts' in v and 'srt' in v}

def main():
    try:
        video_pool = [os.path.join(PROCESSED_VIDEOS_DIR, f) 
                     for f in os.listdir(PROCESSED_VIDEOS_DIR) if f.endswith(".mp4")]

        if not video_pool:
            print("No video files found in processed_videos directory")
            return

        file_groups = find_matching_files()
        if not file_groups:
            print("No matching TTS and SRT file pairs found in cleaned_stories directory")
            return

        print(f"Found {len(file_groups)} file groups and {len(video_pool)} background videos")

        for base_name, files in file_groups.items():
            print(f"\nProcessing {base_name}...")
            try:
                tts_path = os.path.join(CLEANED_STORIES_DIR, files['tts'])
                srt_path = os.path.join(CLEANED_STORIES_DIR, files['srt'])
                create_short_video(tts_path, srt_path, video_pool)
            except Exception as e:
                print(f"Error processing {base_name}: {e}")
                continue

    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
