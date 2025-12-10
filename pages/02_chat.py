"""
Streamlit page wrapper to run the existing chatbot.
"""
import runpy
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    chat_path = root / "app_chat.py"
    # Execute the chatbot script in this page's context.
    runpy.run_path(str(chat_path), run_name="__main__")


if __name__ == "__main__":
    main()
