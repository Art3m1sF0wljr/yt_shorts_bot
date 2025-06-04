import os
import praw
from datetime import datetime

# Reddit API Setup (replace with your keys)
reddit = praw.Reddit(
    client_id="4Id68y9aRCnG2V96nUzXbw",      # e.g., "xYz123..."
    client_secret="FinWwJNa49PLJa2RI8QN07M786wEnQ",  # e.g., "aBc456..."
    user_agent="YT_Shorts_Bot/v1.0"  # Any name
)
# Config
SUBREDDITS = ["MilitaryStories", "TrueOffMyChest", "EntitledPeople", "GlitchInTheMatrix", "TalesFromRetail", "AskReddit"]  # Target subreddits
MIN_UPVOTES = 1500  # Minimum upvotes to consider
MIN_WORDS = 200     # ~50s TTS length (fast-paced)
MAX_WORDS = 10000     # Avoid too-long stories
OUTPUT_DIR = "stories"
MIN_COMMENTS = 150
min_tts = 100
max_tts = 1000
TIME_FILTER = "all"  # "hour", "day", "week", "month", "year", "all"
MAX_FILENAME_LENGTH = 100  # Limit filename length to prevent errors

# Create output dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

def estimate_tts_time(text):
    return len(text.split()) / 2.5

def sanitize_filename(title):
    sanitized = "".join(c for c in title if c.isalnum() or c in " _-").rstrip()
    return sanitized[:MAX_FILENAME_LENGTH]

def get_word_count(text):
    return len(text.split())

def fetch_and_save_stories():
    try:
        print(f"Reddit authorized as: {reddit.user.me()}\n")
        
        index = []
        index_header = (
            "filename|title|upvotes|comments|subreddit|source|word_count|"
            "tts_time|created_utc|url|author|flair|saved_date\n"
        )
        
        for subreddit_name in SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                print(f"🔍 Scanning r/{subreddit_name} (top/{TIME_FILTER})...")
                
                for post in subreddit.top(time_filter=TIME_FILTER, limit=500000):
                    try:
                        if post.stickied:
                            continue
                            
                        print(f"\n📄 Post: {post.title[:50]}...")
                        print(f"⬆️ {post.score} upvotes | 💬 {post.num_comments} comments")
                        
                        story_text = post.selftext
                        source = "post"
                        word_count = get_word_count(story_text)
                        
                        # Handle AskReddit special case
                        if not story_text and subreddit_name == "AskReddit":
                            try:
                                post.comments.replace_more(limit=0)
                                if post.comments:
                                    story_text = post.comments[0].body
                                    source = "top_comment"
                                    word_count = get_word_count(story_text)
                                    print(f"Using {source} (post text was empty)")
                            except Exception as e:
                                print(f"⚠️ Error processing comments: {str(e)}")
                                continue
                        
                        if not story_text:
                            print("🚫 Skipped: No story text found")
                            continue
                        
                        meets_criteria = (
                            post.score >= MIN_UPVOTES and
                            post.num_comments >= MIN_COMMENTS and
                            MIN_WORDS <= word_count <= MAX_WORDS
                        )
                        
                        if meets_criteria:
                            tts_time = estimate_tts_time(story_text)
                            print(f"📏 {word_count} words (~{tts_time:.1f}s TTS)")
                            print(f"🔊 Source: {source}")
                            
                            if 20 <= tts_time <= 360:
                                try:
                                    # Prepare metadata
                                    created_utc = datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S')
                                    saved_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    author_name = str(post.author) if post.author else "[deleted]"
                                    flair = str(post.link_flair_text) if post.link_flair_text else ""
                                    
                                    # Save story file
                                    filename = f"{datetime.now().strftime('%Y%m%d')}_{sanitize_filename(post.title)}.txt"
                                    filepath = os.path.join(OUTPUT_DIR, filename)
                                    
                                    if len(filepath) > 255:
                                        filename = f"{datetime.now().strftime('%Y%m%d')}_{hash(post.title)}.txt"
                                        filepath = os.path.join(OUTPUT_DIR, filename)
                                    
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        f.write(f"{post.title.upper()}\n\n{story_text}")
                                    
                                    # Add to index with all metadata
                                    index_entry = (
                                        f"{filename}|{post.title}|{post.score}|{post.num_comments}|"
                                        f"{subreddit_name}|{source}|{word_count}|{tts_time:.1f}|"
                                        f"{created_utc}|{post.url}|{author_name}|{flair}|{saved_date}\n"
                                    )
                                    index.append(index_entry)
                                    print(f"✅ SAVED: {filename}")
                                except Exception as e:
                                    print(f"⚠️ Error saving file: {str(e)}")
                                    continue
                            else:
                                print(f"⏱️ TTS time out of range ({tts_time:.1f}s)")
                        else:
                            print("❌ Doesn't meet criteria")
                            if post.score < MIN_UPVOTES:
                                print(f"- Needs {MIN_UPVOTES} upvotes (has {post.score})")
                            if post.num_comments < MIN_COMMENTS:
                                print(f"- Needs {MIN_COMMENTS} comments (has {post.num_comments})")
                            if word_count < MIN_WORDS:
                                print(f"- Needs {MIN_WORDS}-{MAX_WORDS} words (has {word_count})")
                    
                    except praw.exceptions.PRAWException as e:
                        print(f"⚠️ PRAW error processing post: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"⚠️ Error processing post: {str(e)}")
                        continue
            except Exception as e:
                print(f"⚠️ Error accessing subreddit: {str(e)}")
                continue
        
        # Save index file with all metadata
        try:
            with open(os.path.join(OUTPUT_DIR, "index.csv"), "w", encoding="utf-8") as f:
                f.write(index_header)
                f.writelines(index)
            print("\n📊 Index file saved with complete metadata")
        except Exception as e:
            print(f"⚠️ Error saving index file: {str(e)}")
    
    except Exception as e:
        print(f"🔥 Critical error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    fetch_and_save_stories()
    print("\nScraping complete. Check the 'stories' folder!")
