"""Fix truncated clipai_db.json by closing the incomplete JSON structure."""
import json
import shutil

# Backup first
shutil.copy2('data/clipai_db.json', 'data/clipai_db_backup.json')
print("Backup saved to data/clipai_db_backup.json")

with open('data/clipai_db.json', 'r', encoding='utf-8') as f:
    content = f.read()

# The file is truncated after "source_url": "..." inside a review_clips entry.
# We need to close: the current object }, the review_clips array ], and the root object }
content = content.rstrip()
if not content.endswith('}'):
    # Close the truncated review_clips entry + array + root
    content += '\n    }\n  ]\n}'

# Verify it parses correctly
try:
    data = json.loads(content)
    print(f"JSON fixed! Keys: {list(data.keys())}")
    print(f"  queue: {len(data.get('queue', []))} items")
    print(f"  channels: {len(data.get('channels', []))} items")
    print(f"  review_clips: {len(data.get('review_clips', []))} items")
    print(f"  posted_videos: {len(data.get('posted_videos', []))} items")
    
    # Save the fixed file (re-serialize to ensure valid JSON)
    with open('data/clipai_db.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print("Fixed DB saved!")
except json.JSONDecodeError as e:
    print(f"Still invalid: {e}")
    print("Restoring backup...")
    shutil.copy2('data/clipai_db_backup.json', 'data/clipai_db.json')
