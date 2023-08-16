# Standard Packages
import asyncio
import logging
import os
from typing import Optional

# External Packages
from asgiref.sync import sync_to_async
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.params import Form
from langchain import LLMChain
from twilio.request_validator import RequestValidator
from twilio.rest import Client

# Internal Packages
from flint import state
from flint.configure import configure_chat_prompt, save_conversation
from flint.helpers import transcribe_audio_message
from flint.prompt import previous_conversations_prompt
from flint.state import embeddings_manager
from flint.constants import KHOJ_INTRO_MESSAGE

# Keep Django module import here to avoid import ordering errors
from django.contrib.auth.models import User


# Initialize Router
api = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Twilio Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twillio_client = Client(account_sid, auth_token)

MAX_CHARACTERS_TWILIO = 1600
MAX_CHARACTERS_PROMPT = 1000

DEBUG = os.getenv("DEBUG", False)

@api.get("/health")
async def health() -> Response:
    return Response(status_code=200)

# Setup API Endpoints
@api.post("/chat")
async def chat(
    request: Request,
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    To: str = Form(...),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
) -> Response:
    # Authenticate Request from Twilio
    validator = RequestValidator(auth_token)
    form_ = await request.form()
    logger.debug(f"Request Headers: {request.headers}")
    if not validator.validate(str(request.url), form_, request.headers.get("X-Twilio-Signature", "")):
        logger.error("Error in Twilio Signature")
        raise HTTPException(status_code=401, detail="Unauthorized signature")

    # Get the user object
    user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(khojuser__phone_number=From)
    user_exists = await sync_to_async(user.exists)()
    intro_message = False
    if not user_exists:
        user_phone_number = From.split(":")[1]
        user = await sync_to_async(User.objects.create)(username=user_phone_number)
        user.khojuser.phone_number = user_phone_number
        await sync_to_async(user.save)()
        intro_message = True
    else:
        user = await sync_to_async(user.get)()

    asyncio.create_task(respond_to_user(Body, user, MediaUrl0, MediaContentType0, From, To, intro_message))


if DEBUG:
    # Setup API Endpoints
    @api.post("/dev/chat")
    async def chat_dev(
        request: Request,
        Body: str,
    ) -> Response:
        # Get the user object
        target_username = "dev"
        user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(username=target_username)
        user_exists = await sync_to_async(user.exists)()
        if user_exists:
            user = await sync_to_async(user.get)()
        else:
            user = await sync_to_async(User.objects.create)(username=target_username)
            await sync_to_async(user.save)()
        uuid = user.khojuser.uuid

        # Get Conversation History
        chat_history = state.conversation_sessions[uuid]

        # Get Response from Agent
        chat_response = LLMChain(llm=state.llm, prompt=configure_chat_prompt(), memory=chat_history)({"question": Body})
        chat_response_text = chat_response["text"]

        asyncio.create_task(save_conversation(user, Body, chat_response_text))

        return chat_response_text
    
    @api.post("/dev/search")
    async def search_dev(
        request: Request,
        query: str,
    ) -> Response:
        # Get the user object
        target_username = "dev"
        user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(username=target_username)
        user_exists = await sync_to_async(user.exists)()
        if user_exists:
            user = await sync_to_async(user.get)()
        else:
            user = await sync_to_async(User.objects.create)(username=target_username)
            await sync_to_async(user.save)()

        relevant_previous_conversations = await embeddings_manager.search(query, user, debug=True)
        relevant_previous_conversations = await sync_to_async(list)(relevant_previous_conversations.all())

        conversation_history = ""
        for c in relevant_previous_conversations:
            conversation_history += f"Human: {c.user_message}\nKhoj:{c.bot_message}\n\n"

        conversation_history = 'none' if conversation_history == '' else conversation_history

        return Response(content=conversation_history, media_type="text/plain")


async def respond_to_user(message: str, user: User, MediaUrl0, MediaContentType0, From, To, intro_message=False):
    # Initialize user message to the body of the request
    uuid = user.khojuser.uuid
    user_message = message
    user_message_type = "text"

    # Check if message is an audio message
    if MediaUrl0 is not None and MediaContentType0 is not None and MediaContentType0.startswith("audio/"):
        audio_url = MediaUrl0
        audio_type = MediaContentType0.split("/")[1]
        user_message_type = "voice_message"
        logger.info(f"Received audio message from {From} with url {audio_url} and type {audio_type}")
        user_message = transcribe_audio_message(audio_url, uuid, logger)

    # Get Conversation History
    chat_history = state.conversation_sessions[uuid]
    previous_conversations = ''

    formatted_message = user_message

    relevant_previous_conversations = await embeddings_manager.search(user_message, user)
    relevant_previous_conversations = await sync_to_async(list)(relevant_previous_conversations.all())
    for c in relevant_previous_conversations:
        next_message = f"Human:{c.user_message}\nKhoj:{c.bot_message}\n\n"
        
        if len(previous_conversations) + len(next_message) + len(user_message) > MAX_CHARACTERS_PROMPT:
            human_message = f"Human:{c.user_message}\n"
            if len(previous_conversations) + len(human_message) + len(user_message) > MAX_CHARACTERS_PROMPT:
                break
            else:
                next_message = human_message

        previous_conversations += next_message
    
    if previous_conversations != '':
        formatted_message = previous_conversations_prompt.format(query=user_message, conversation_history=previous_conversations)

    # Get Response from Agent
    chat_response = LLMChain(llm=state.llm, prompt=configure_chat_prompt(), memory=chat_history)({"question": formatted_message})
    chat_response_text = chat_response["text"]

    asyncio.create_task(save_conversation(user, user_message, chat_response_text, user_message_type))

    # Split response into 1600 character chunks
    chunks = [chat_response_text[i : i + MAX_CHARACTERS_TWILIO] for i in range(0, len(chat_response_text), MAX_CHARACTERS_TWILIO)]
    for chunk in chunks:
        message = twillio_client.messages.create(body=chunk, from_=To, to=From)

    # Send Intro Message
    if intro_message:
        message = twillio_client.messages.create(
            body=KHOJ_INTRO_MESSAGE,
            from_=To,
            to=From,
        )
        asyncio.create_task(save_conversation(user, '', KHOJ_INTRO_MESSAGE, 'system'))

    return message.sid