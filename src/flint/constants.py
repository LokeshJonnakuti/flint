import os

KHOJ_WHATSAPP_PROD = "whatsapp:+18488004242"
KHOJ_WHATSAPP_DEBUG = "whatsapp:+14155238886"
KHOJ_INTRO_MESSAGE = """
Nice to meet you! I am Khoj, your dedicated personal AI 👋🏽. I can help you with:
- 🧠 Answering general knowledge questions
- 💡 Ideating over new ideas
- 🖊️ Being a scratchpad for your thoughts, links, concepts that you want to remember
- 🌄 Making images from your own words (try typing `/dream`)
- 📝 Retrieving information from your own knowledge base shared with Khoj on the cloud. See https://khoj.dev for more info

You can also send me voice messages in your native language 🎙️.

I'm constantly learning and improving, so please report any issues to my creators on GitHub: https://github.com/khoj-ai/flint/issues
""".strip()

KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE = """
Sorry, I wasn't able to understand your voice message this time. Could you please try typing out your message or send a shorter message? If you'd like to help me improve, email my creators at team@khoj.dev.
""".strip()

KHOJ_FAILED_DOCUMENT_UPLOAD_MESSAGE = """
Sorry, I wasn't able to process your document this time. Could you please try sending a different document? If you'd like to help me improve, email my creators at team@khoj.dev.
""".strip()

KHOJ_MEDIA_NOT_IMPLEMENTED_MESSAGE = """
Sorry, I'm not yet able to process this type of media. Could you please try sending a different type of media? If you'd like to help me improve, email my creators at team@khoj.dev.
""".strip()

KHOJ_API_URL = os.getenv("KHOJ_API_URL", "https://app.khoj.dev")
KHOJ_API_CLIENT_ID = os.getenv("KHOJ_API_CLIENT_ID")
KHOJ_API_CLIENT_SECRET = os.getenv("KHOJ_API_CLIENT_SECRET")
