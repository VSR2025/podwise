from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import warnings
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
import openai
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Suppress warnings and unnecessary logging
warnings.filterwarnings('ignore', category=FutureWarning)
logging.getLogger('WDM').setLevel(logging.ERROR)

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
channel_name = os.getenv("CHANNEL_URL", "<name>").split('/')[-1]
default_num = os.getenv("DEFAULT_NUM_VIDEOS", "#")

print(f"Welcome! Podwise will now download the last {default_num} episodes of the {channel_name} podcast, "
      f"transcribe and discern the book and product recommendations from each guest.")

# Custom exceptions
class PodwiseError(Exception):
    pass

class ConfigurationError(PodwiseError):
    pass

class ScrapingError(PodwiseError):
    pass

class TranscriptionError(PodwiseError):
    pass

@dataclass
class ProcessingResult:
    books: List[Tuple[str, str]]
    products: List[Tuple[str, str]]
    summary: str

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def validate_environment():
    load_dotenv()
    required_vars = ['OPENAI_API_KEY', 'CHANNEL_URL', 'BASE_OUTPUT_DIR', 'DEFAULT_NUM_VIDEOS']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ConfigurationError(f"Missing environment variables: {', '.join(missing)}")
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ConfigurationError("The OpenAI API key is missing or invalid. Please set it as an environment variable.")

class PodcastProcessor:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir if base_dir else os.getenv("BASE_OUTPUT_DIR"))
        self.base_dir.mkdir(exist_ok=True)
        self.csv_file = self.base_dir / "episodes.csv"

        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--log-level=3')
        self.chrome_options.add_argument('--silent')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    def _init_chrome_driver(self) -> webdriver.Chrome:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=self.chrome_options)

    def format_filename(self, title: str) -> str:
        """Generate a safe filename from the title."""
        safe_title = "".join(c if c.isalnum() or c in " -" else "_" for c in title).strip()
        return safe_title.replace(" ", "_") + ".txt"

    def scrape_episodes(self, num_videos: Optional[int] = None) -> List[dict]:
        try:
            num_videos = num_videos if num_videos else int(os.getenv("DEFAULT_NUM_VIDEOS", "5"))
            driver = self._init_chrome_driver()

            try:
                driver.get(os.getenv("CHANNEL_URL"))
                time.sleep(5)

                wait = WebDriverWait(driver, 30)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "ytd-rich-grid-renderer")))

                video_items = driver.find_elements(By.CSS_SELECTOR, "ytd-rich-grid-media>#content>ytd-rich-grid-media")
                if not video_items:
                    video_items = driver.find_elements(By.CSS_SELECTOR, "ytd-rich-item-renderer")

                videos = []
                logger.info("Step 1/3: Scraping Episodes")

                for i, item in enumerate(video_items[:num_videos], 1):
                    try:
                        link_element = item.find_element(By.CSS_SELECTOR, "a#video-title-link")
                        href = link_element.get_attribute("href")
                        title = link_element.get_attribute("title")

                        if href and "watch?v=" in href:
                            video_id = href.split("watch?v=")[1].split("&")[0]
                            videos.append({"title": title, "video_id": video_id})
                            logger.info(f"Episode {i} identified: {title}")
                    except Exception as e:
                        logger.error(f"Error processing video {i}: {str(e)}")
                        continue

                df = pd.DataFrame(videos)
                df = df.astype({
                    'title': 'string',
                    'video_id': 'string'
                })
                df['book_titles'] = ''
                df['book_authors'] = ''
                df['product_recommendations'] = ''
                df['summary_file'] = ''
                df['has_transcript'] = False
                df.to_csv(self.csv_file, index=False)

                return videos

            finally:
                driver.quit()

        except Exception as e:
            raise ScrapingError(f"Failed to scrape episodes: {str(e)}")

    def get_transcripts(self):
        try:
            df = pd.read_csv(self.csv_file)
            logger.info("\n----------------------------------------------------")
            logger.info("Step 2/3: Transcripting # episodes")

            for index, row in df.iterrows():
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(row['video_id'])

                    transcript_text = ""
                    for entry in transcript_list:
                        seconds = int(entry['start'])
                        timestamp = f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"
                        transcript_text += f"{timestamp} {entry['text']}\n"

                    filename = self.format_filename(row['title'])
                    filepath = self.base_dir / filename

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(transcript_text)

                    df.at[index, 'has_transcript'] = True
                    logger.info(f"Episode {index + 1} transcript saved: {row['title']}")
                    time.sleep(2)

                except TranscriptsDisabled:
                    logger.info(f"Episode {index + 1} no transcript available: {row['title']}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing transcript for episode {index + 1}: {str(e)}")
                    continue

            df.to_csv(self.csv_file, index=False)

        except Exception as e:
            raise TranscriptionError(f"Failed to process transcripts: {str(e)}")

    def extract_content(self, transcript_text: str) -> ProcessingResult:
        """Extract books, products, and summary from transcript text."""
        all_books = []
        all_products = []
        summary_chunks = []
        chunk_size = 8000
        chunks = [transcript_text[i:i + chunk_size] for i in range(0, len(transcript_text), chunk_size)]

        for chunk in chunks:
            try:
                prompt = (
                    "Analyze this podcast transcript section:\n"
                    "1. Extract published books (Format: Title by Author)\n"
                    "2. Extract specific product recommendations (Format: Product - Description)\n"
                    "3. Extract key Q&A points for summary\n\n"
                    "If none found for books/products, return \"None\" for that section.\n\n"
                    "Format response as:\n"
                    "BOOKS:\n"
                    "[books list]\n\n"
                    "PRODUCTS:\n"
                    "[products list]\n\n"
                    "SUMMARY:\n"
                    "[key points]"
                )

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You analyze podcast transcripts for specific content."},
                        {"role": "user", "content": f"{prompt}\n\nTranscript section:\n{chunk}"}
                    ],
                    temperature=0.3
                )

                content = response.choices[0].message['content'].strip().split('\n\n')

                for section in content:
                    if section.startswith('BOOKS:'):
                        books = section[6:].strip()
                        if books.lower() != 'none':
                            for line in books.split('\n'):
                                if " by " in line:
                                    title, author = line.split(" by ", 1)
                                    all_books.append((title.strip(), author.strip()))

                    elif section.startswith('PRODUCTS:'):
                        products = section[9:].strip()
                        if products.lower() != 'none':
                            for line in products.split('\n'):
                                if " - " in line:
                                    product, desc = line.split(" - ", 1)
                                    all_products.append((product.strip(), desc.strip()))

                    elif section.startswith('SUMMARY:'):
                        summary_chunks.append(section[8:].strip())

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                continue

        try:
            summary_prompt = (
                "Create a concise Q&A style summary from these discussion points.\n"
                "Format as 3-5 key Q&A pairs focused on main insights."
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You create clear Q&A summaries from podcast discussions."},
                    {"role": "user", "content": f"{summary_prompt}\n\n{''.join(summary_chunks)}"}
                ],
                temperature=0.3
            )

            final_summary = response.choices[0].message['content'].strip()

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            final_summary = ""

        return ProcessingResult(
            books=list({(title.lower(), author.lower()): (title, author) for title, author in all_books}.values()),
            products=list({(product.lower(), desc.lower()): (product, desc) for product, desc in all_products}.values()),
            summary=final_summary
        )

    def process_all(self, num_videos: Optional[int] = None):
        try:
            self.scrape_episodes(num_videos)
            self.get_transcripts()

            logger.info("Step 3/3: Content Analysis")
            df = pd.read_csv(self.csv_file)

            results = []  # Collect results for tabulation

            for index, row in df.iterrows():
                if not row['has_transcript']:
                    logger.info(f"Episode {index + 1}: No content (transcript unavailable)")
                    continue

                filename = self.format_filename(row['title'])
                transcript_path = self.base_dir / filename

                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript_text = f.read()

                    content = self.extract_content(transcript_text)

                    # Log books and products
                    books = "; ".join([f"{title} by {author}" for title, author in content.books]) if content.books else "None"
                    products = "; ".join([f"{product} - {desc}" for product, desc in content.products]) if content.products else "None"

                    if content.books:
                        df.at[index, 'book_titles'] = "; ".join([title for title, _ in content.books])
                        df.at[index, 'book_authors'] = "; ".join([author for _, author in content.books])

                    if content.products:
                        df.at[index, 'product_recommendations'] = "; ".join(
                            [f"{product} - {desc}" for product, desc in content.products]
                        )

                    # Save summary to file and update the CSV
                    summary_file_name = ""
                    if content.summary:
                        summary_filename = f"{filename.replace('.txt', '_summary.txt')}"
                        summary_path = self.base_dir / summary_filename
                        with open(summary_path, 'w', encoding='utf-8') as summary_file:
                            summary_file.write(content.summary)
                        df.at[index, 'summary_file'] = summary_filename
                        summary_file_name = summary_filename

                    # Add a line break after each episode result
                    results.append({
                        "Episode": row['title'],
                        "Books": books,
                        "Products": products,
                        "Summary File": summary_file_name if summary_file_name else "None"
                    })

                except Exception as e:
                    logger.error(f"Error processing episode {index + 1}: {str(e)}")
                    continue

            # Save the updated CSV
            df.to_csv(self.csv_file, index=False)

            # Display results
            for result in results:
                print(f"Episode: {result['Episode']}")
                print(f"Books: {result['Books']}")
                print(f"Products: {result['Products']}")
                print(f"Summary File: {result['Summary File']}\n")
                print("----------------------------------------------------")

            logger.info(f"You can access all the necessary details here: {self.csv_file}\n")

        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            raise

def main():
    try:
        validate_environment()
        processor = PodcastProcessor()
        processor.process_all()
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
