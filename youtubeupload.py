import os
import random
import json
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request  # Added this import

# Configuration
VIDEOS_FOLDER = 'videos'
UPLOAD_LOG_FILE = 'uploaded_videos.log'
CLIENT_SECRETS_FILE = 'client_secrets.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Upload times (HHMM format)
UPLOAD_TIMES = ['0759', '1559', '2359']
RANDOM_MINUTE_VARIATION = 30  # +/- minutes variation

def get_authenticated_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, 
                SCOPES
            )
            creds = flow.run_local_server(port=8080)  # Fixed port
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('youtube', 'v3', credentials=creds)
    
def get_uploadable_videos():
    """Get list of videos that haven't been uploaded yet"""
    uploaded_videos = set()
    if os.path.exists(UPLOAD_LOG_FILE):
        with open(UPLOAD_LOG_FILE, 'r') as f:
            uploaded_videos = set(line.strip() for line in f.readlines())
    
    all_videos = [f for f in os.listdir(VIDEOS_FOLDER) if f.endswith('_short.mp4')]
    return [v for v in all_videos if v not in uploaded_videos]

def log_uploaded_video(video_name):
    """Mark a video as uploaded in the log file"""
    with open(UPLOAD_LOG_FILE, 'a') as f:
        f.write(f"{video_name}\n")

def extract_title(video_name):
    """Extract title from filename (remove date and _short.mp4)"""
    # Remove date prefix (first 9 characters: YYYYMMDD_)
    no_date = video_name[9:] if video_name[:8].isdigit() and video_name[8] == '_' else video_name
    # Remove _short.mp4 suffix
    return no_date.replace('_short.mp4', '')
    
def upload_video(youtube, video_path, title):
    """Upload video to YouTube with custom description"""
    # Navier-Stokes equations in convective form
    navier_stokes_eq = """
Navier-Stokes Momentum Equation (Convective Form):

∂u/∂t + (u·∇)u = -1/ρ ∇p + ν∇²u + f

Where:
- u = velocity vector field
- t = time
- ρ = fluid density
- p = pressure field
- ν = kinematic viscosity
- f = external body forces
- ∇ = gradient operator
- ∇² = Laplacian operator
"""
    
    description = f"""Pedro

{navier_stokes_eq}
"""
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['Mathematics', 'Physics', 'Fluid Dynamics', 'SliceOfLife', 'PeopleBlog', 'Youtubeshorts', 'viral', 'subscribe', 'shorts' , 'trending', 'reels'],
            'categoryId': '22'  # Education category
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    
    try:
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        print(f"Video uploaded! ID: {response['id']}")
        
        # Only delete if upload was successful
        os.remove(video_path)
        print(f"Deleted local file: {video_path}")
        
        return response
    
    except Exception as e:
        print(f"Error during upload or file deletion: {str(e)}")
        raise  # Re-raise the exception to handle it in the calling function

def get_next_upload_time():
    """Calculate next upload time with random variation"""
    now = datetime.now()
    
    # Find the next upload time today
    for upload_time in UPLOAD_TIMES:
        target = datetime.strptime(f"{now.strftime('%Y%m%d')} {upload_time}", '%Y%m%d %H%M')
        variation = random.randint(-RANDOM_MINUTE_VARIATION, RANDOM_MINUTE_VARIATION)
        target += timedelta(minutes=variation)
        
        if target > now:
            return target
    
    # If all today's upload times have passed, use first time tomorrow
    tomorrow = now + timedelta(days=1)
    target = datetime.strptime(f"{tomorrow.strftime('%Y%m%d')} {UPLOAD_TIMES[0]}", '%Y%m%d %H%M')
    variation = random.randint(-RANDOM_MINUTE_VARIATION, RANDOM_MINUTE_VARIATION)
    return target + timedelta(minutes=variation)

def main():
    youtube = get_authenticated_service()
    
    # Initial upload
    uploadable_videos = get_uploadable_videos()
    if uploadable_videos:
        video_to_upload = random.choice(uploadable_videos)
        video_path = os.path.join(VIDEOS_FOLDER, video_to_upload)
        title = extract_title(video_to_upload)
        print(f"Uploading {video_to_upload} with title: {title}")
        try:
            upload_video(youtube, video_path, title)
            log_uploaded_video(video_to_upload)
        except Exception as e:
            print(f"Failed to upload {video_to_upload}: {str(e)}")
    
    # Scheduled uploads
    while True:
        next_upload = get_next_upload_time()
        print(f"Next upload scheduled for: {next_upload}")
        
        # Sleep until next upload time
        sleep_seconds = (next_upload - datetime.now()).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        
        # Perform upload
        uploadable_videos = get_uploadable_videos()
        if uploadable_videos:
            video_to_upload = random.choice(uploadable_videos)
            video_path = os.path.join(VIDEOS_FOLDER, video_to_upload)
            title = extract_title(video_to_upload)
            print(f"Uploading {video_to_upload} with title: {title}")
            try:
                upload_video(youtube, video_path, title)
                log_uploaded_video(video_to_upload)
            except Exception as e:
                print(f"Failed to upload {video_to_upload}: {str(e)}")
        else:
            print("No videos left to upload!")
            
if __name__ == '__main__':
    main()
