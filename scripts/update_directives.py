# Update task file automatically to match new directives
import re

file_path = "C:/Users/pedro/.gemini/antigravity/infoRoutine/.directives/task.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the Research method section
new_strategy = """### 3.1 DATA ACQUISITION STRATEGY
* **Primary method:** RSS feeds where available (~50% of sources), parsed with `feedparser` (0 API calls).
* **Fallback method:** HTML parsing with `httpx` and `BeautifulSoup` to extract headlines and links (0 API calls).
* **AI-assisted processing:** Use **Google Gemini API** (`gemini-2.5-flash`) in a single bulk prompt. We feed the raw scraped data to the LLM to filter, translate, generate elevator pitches, and write the Executive Summary in 1 combined API call."""

content = re.sub(
    r"### 3\.1 DATA ACQUISITION STRATEGY.*?## 4\. PROCESSING LOGIC", 
    new_strategy + "\n\n## 4. PROCESSING LOGIC", 
    content, 
    flags=re.DOTALL
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated .directives/task.md")
