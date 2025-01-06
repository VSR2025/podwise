# Podwise: Podcast Content Extractor

Podwise automates the extraction of key insights, book recommendations, and product mentions from podcast transcripts. It helps podcasters and content enthusiasts analyze podcasts quickly and effectively without manual effort.

## Features
- Scrapes the latest episodes from a YouTube channel and saves details to your local machine.
- Transcribes episodes using the YouTube Transcript API for analysis.
- Extracts:
  - **Books** mentioned in the episode.
  - **Products** recommended during discussions.
  - A concise **summary** of key insights.
- Outputs data into a CSV file and individual summary `.txt` files for easy review.

## Requirements
- **Python 3.8 or higher**: Required for running the script.
  - [Download Python here](https://www.python.org/downloads/).
- **OpenAI API key**: Needed to extract insights from transcripts.
  - [Get your OpenAI API key here](https://platform.openai.com/account/api-keys).
- **Selenium and ChromeDriver**: Used for scraping YouTube episodes.

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/podwise.git
cd podwise
```

### 2. Set up a virtual environment (optional but recommended)
```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

> **Why a virtual environment?**
> Virtual environments help isolate project dependencies to avoid conflicts with other Python projects on your system.

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
> **What is `requirements.txt`?**
> This file lists all the Python libraries needed for the project. The command installs them for you automatically.

### 4. Set up the `.env` file
Create a `.env` file in the root directory and add the following:
```env
OPENAI_API_KEY=your_openai_api_key_here
CHANNEL_URL=https://www.youtube.com/channel/<your_channel_id>
BASE_OUTPUT_DIR=./output
DEFAULT_NUM_VIDEOS=5
```
Replace `your_openai_api_key_here` with your OpenAI API key and `<your_channel_id>` with the desired YouTube channel ID.

#### How to create a `.env` file:
1. Open a text editor.
2. Paste the above content into the editor.
3. Save the file as `.env` in the root folder of the project.

> **Keep your `.env` file secure!**
> Do not share this file publicly, as it contains sensitive information like your API key.

### 5. Run the script
```bash
python podwise.py
```
> **What happens next?**
> The script will scrape, transcribe, and extract insights from podcast episodes. Outputs will be saved to the `output` directory.

## Usage
- The script will scrape the latest episodes from the specified YouTube channel, transcribe them, and extract:
  - **Books** mentioned in the episode.
  - **Products** recommended during the discussion.
  - A concise **summary** of the key points.

- All extracted data will be saved in:
  - **`episodes.csv`**: A structured file with details of all episodes.
  - **Individual `.txt` files**: Each file contains the summary for a specific episode.

> **Why is this useful?**
> This extracted data can help podcasters or researchers analyze trends, identify popular content, and discover opportunities for sponsorships or collaborations.

## Example Output
### Console Output
```plaintext
Episode: Inside Gong: How teams work with design partners
Books: - Ideal Executive by Unknown Author
Products: - Vanta - Security platform for compliance
Summary File: Inside_Gong_summary.txt
----------------------------------------------------
```

### CSV Output (`output/episodes.csv`)
| Title                                         | Books                              | Products                          | Summary File                  |
|-----------------------------------------------|------------------------------------|-----------------------------------|-------------------------------|
| Inside Gong: How teams work...               | Ideal Executive by Unknown Author | Vanta - Security platform...     | Inside_Gong_summary.txt       |

> **How to open `episodes.csv`?**
> You can open it in Excel, Google Sheets, or any text editor to view the extracted data.

## Additional Notes
- **Environment variables**: Ensure the `.env` file contains accurate details.
- **Dependencies**: Ensure you have the correct versions of the required libraries by using `requirements.txt`.
- **Browser setup**:
  - Make sure Google Chrome is installed, as Selenium relies on ChromeDriver.
    - If Chrome is not installed, [download and install it here](https://www.google.com/chrome/).
  - If ChromeDriver is missing, Selenium's `webdriver-manager` will automatically download it, but ensure you have the appropriate permissions for installation.
  - For troubleshooting ChromeDriver, refer to [official Selenium documentation](https://www.selenium.dev/documentation/).
- **Output location**: All results, including the `episodes.csv` file and summary files, will be saved in the `output/` folder in your project directory.

## License
This project is licensed under the MIT License.

