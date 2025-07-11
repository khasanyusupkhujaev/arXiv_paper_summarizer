import google.generativeai as genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

try:
    gemini_api_key = settings.GEMINI_API_KEY
    if not gemini_api_key or gemini_api_key == 'your_dev_api_key_if_needed':
        logger.warning("GEMINI_API_KEY is not set in Django settings or is using a placeholder.")
    else:
        genai.configure(api_key=gemini_api_key)
        logger.info("Gemini API configured successfully at module load.")
except Exception as e:
    logger.error(f"An unexpected error occurred during initial Gemini API configuration: {e}")

def get_gemini_model(model_name='gemini-2.0-flash'):
    """
    Helper function to get a configured Gemini GenerativeModel.
    Assumes the API key has been configured globally (at module load).
    """
    try:
        return genai.GenerativeModel(model_name=model_name)
    except Exception as e:
        logger.error(f"Failed to get Gemini model '{model_name}': {e}. Ensure API key is correctly configured.")
        return None

def summarize_text_gemini(text, target_language="Uzbek (Latin)", max_length_tokens=1000):
    """
    Summarizes the given text using the Gemini API.
    The summary will be in the specified target language.
    """
    logger.debug(f"summarize_text_gemini: Attempting to summarize in target_language='{target_language}'") # DEBUG LOG

    model = get_gemini_model()
    if not model:
        return "Ошибка: Не удалось подключиться к Gemini API для суммирования. Проверьте ваш API ключ."

    prompt = (
        f"Summarize the following scientific paper text in {target_language}. "
        f"Keep the summary concise and highlight the main contributions and findings. "
        f"Ensure the summary is no longer than {max_length_tokens} tokens:\n\n{text}"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_length_tokens,
                temperature=0.7
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini summarization failed: {e}")
        return f"Ошибка при суммировании текста: {e}. Пожалуйста, проверьте консоль сервера для получения подробной информации."

def answer_question_gemini(context_text, question, target_language="Uzbek (Latin)", max_length_tokens=500):
    """
    Answers a question based on the provided context text using the Gemini API.
    The answer will be in the specified target language.
    """
    logger.debug(f"answer_question_gemini: Attempting to answer question in target_language='{target_language}'") # DEBUG LOG

    model = get_gemini_model()
    if not model:
        return "Ошибка: Не удалось подключиться к Gemini API для ответа на вопрос. Проверьте ваш API ключ."

    prompt = (
        f"Based on the following text from a scientific paper, answer the question in {target_language}. "
        f"If the answer is not explicitly available in the text, state that. "
        f"Keep the answer concise, no longer than {max_length_tokens} tokens.\n\n"
        f"Paper Text:\n{context_text}\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_length_tokens,
                temperature=0.2
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini question answering failed: {e}")
        return f"Ошибка при ответе на вопрос: {e}. Пожалуйста, проверьте консоль сервера для получения подробной информации."