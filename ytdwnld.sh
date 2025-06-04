#!/bin/bash
#python3 -m venv myenv
source /home/art3m1sf0wl/program/botyt/myenv/bin/activate
# Activate the virtual environment
#source myenv/bin/activate
pip install yt-dlp
# Install librosa in the virtual environment

# Configuration
INPUT_FILE="ytvideos.txt"
OUTPUT_DIR="processed_videos"
TEMP_DIR="temp_downloads"
SPEED_FACTOR="1.5"
SHORTS_HEIGHT=1920
SHORTS_WIDTH=1080

# Create directories if they don't exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TEMP_DIR"

# Check if required tools are installed
if ! command -v yt-dlp &> /dev/null; then
    echo "Error: yt-dlp is not installed. Please install it first."
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed. Please install it first."
    exit 1
fi

# Process each video
while IFS= read -r url || [[ -n "$url" ]]; do
    # Clean the URL (remove CR characters if present)
    url=$(echo "$url" | tr -d '\r')
    
    # Skip empty lines and comments
    if [[ -z "$url" || "$url" == \#* ]]; then
        continue
    fi
    
    echo "Processing: $url"
    
    # Download the video with yt-dlp
    echo "Downloading..."
    yt-dlp -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' \
           -o "$TEMP_DIR/%(title)s.%(ext)s" \
           --no-playlist \
           "$url"
    
    # Get the downloaded filename
    ORIGINAL_FILE=$(ls -t "$TEMP_DIR"/*.mp4 | head -n 1)
    if [ -z "$ORIGINAL_FILE" ]; then
        echo "Error: Failed to download $url"
        continue
    fi
    
    # Get video dimensions and duration
    VIDEO_INFO=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of csv=s=x:p=0 "$ORIGINAL_FILE")
    ORIG_WIDTH=$(echo "$VIDEO_INFO" | cut -d 'x' -f 1)
    ORIG_HEIGHT=$(echo "$VIDEO_INFO" | cut -d 'x' -f 2)
    DURATION=$(echo "$VIDEO_INFO" | cut -d 'x' -f 3)
    
    # Calculate new duration after trimming (original duration - 40 seconds)
    NEW_DURATION=$(echo "$DURATION - 40" | bc)
    
    # Calculate scaling and cropping for Shorts format (9:16)
    # First we scale to make height 1920, then crop width to 1080 if needed
    SCALE_FILTER="scale=-1:$SHORTS_HEIGHT"
    CROP_FILTER="crop=$SHORTS_WIDTH:$SHORTS_HEIGHT"
    
    # If original is portrait, we might need to scale width instead
    if [ "$ORIG_HEIGHT" -gt "$ORIG_WIDTH" ]; then
        SCALE_FILTER="scale=$SHORTS_WIDTH:-1"
        CROP_FILTER="crop=$SHORTS_WIDTH:$SHORTS_HEIGHT"
    fi
    
    # Process with ffmpeg
    echo "Processing video..."
    OUTPUT_FILE="$OUTPUT_DIR/$(basename "${ORIGINAL_FILE%.*}")_shorts.mp4"
    
    ffmpeg -i "$ORIGINAL_FILE" \
           -filter_complex \
           "[0:v]${SCALE_FILTER},${CROP_FILTER},setpts=PTS/$SPEED_FACTOR[v];[0:a]atempo=$SPEED_FACTOR[a]" \
           -map "[v]" -map "[a]" \
           -ss 20 \
           -t "$NEW_DURATION" \
           -c:v libx264 -crf 18 -preset fast \
           -c:a aac -b:a 192000 \
           "$OUTPUT_FILE"
    
    # Remove the original downloaded file
    rm "$ORIGINAL_FILE"
    
    echo "Finished processing: $OUTPUT_FILE"
    echo "----------------------------------"
done < <(grep -v '^[[:space:]]*$' "$INPUT_FILE")

echo "All videos processed!"
