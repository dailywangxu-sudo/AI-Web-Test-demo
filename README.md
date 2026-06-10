# AI web 测试助手 Demo

A Streamlit + Playwright + OpenAI API demo for testing psychology websites from a supplied URL.

## Workflow

1. Enter a test page URL.
2. Playwright opens the page in multiple device profiles.
3. Screenshots are saved to `screenshots/`.
4. Streamlit displays the screenshots.
5. OpenAI analyzes the screenshots.
6. The app generates a test report and a bug report.

## Supported Devices

- Desktop Chrome
- iPhone SE
- iPhone 15
- Pixel 7

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file from `.env.example`:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

## Run

```powershell
streamlit run streamlit_app.py
```

## Output

Screenshots are saved under:

```text
screenshots/<run-timestamp>/
```

The generated Markdown report can be downloaded from the Streamlit UI.
