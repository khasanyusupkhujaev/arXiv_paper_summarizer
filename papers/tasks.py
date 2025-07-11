from celery import shared_task
from django.conf import settings
from .views import fetch_paper_data, download_preprint_pdf, extract_text_and_metadata_from_pdf, summarize_text_gemini, preprocess_text
from .models import PaperSummary, LocalizedPaperSummary
import os
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_new_paper(repository, paper_id, file_name_for_db, summary_type, language):
    """Process a new paper in the background."""
    # Fetch metadata
    data = fetch_paper_data(repository, paper_id)
    if not data:
        logger.error(f"Не удалось найти статью с ID {paper_id} на {repository}")
        return {"error": f"Не удалось найти статью с ID {paper_id} на {repository}."}
    
    # Download PDF
    pdf_save_path = download_preprint_pdf(repository, paper_id, settings.MEDIA_ROOT)
    if not pdf_save_path:
        logger.error(f"Не удалось загрузить PDF с {repository} ID: {paper_id}")
        return {"error": f"Не удалось загрузить PDF с {repository} ID: {paper_id}."}
    
    try:
        # Extract text (use metadata from API, not PDF)
        extracted_text, _, _ = extract_text_and_metadata_from_pdf(pdf_save_path)
        if not extracted_text:
            logger.warning(f"Извлечено ноль текста из PDF {paper_id}")
            return {"error": "Не удалось извлечь текст из PDF."}
        logger.info(f"Извлечен текст из PDF: {len(extracted_text)} символов")
        
        # Preprocess text for summarization
        preprocessed_text = preprocess_text(extracted_text)
        
        # Create PaperSummary
        paper_summary_obj = PaperSummary.objects.create(
            file_name=file_name_for_db,
            text_content=extracted_text,
            title=data.get('title', ''),
            authors=data.get('authors', ''),
            url=data.get('abs_url', '')
        )
        logger.info(f"Объект PaperSummary создан с ID: {paper_summary_obj.pk}")
        
        # Precompute summaries for common languages and types
        for lang in ['en', 'ru']:  # Add more languages as needed
            for sum_type in ['ordinary', 'short']:  # Add 'detailed' if needed
                summary_content = summarize_text_gemini(
                    preprocessed_text,
                    target_language=lang,
                    summary_type=sum_type
                )
                LocalizedPaperSummary.objects.create(
                    paper_summary=paper_summary_obj,
                    language=lang,
                    summary_text=summary_content,
                    summary_type=sum_type
                )
                logger.info(f"LocalizedPaperSummary создан для '{paper_id}' на {lang}, тип '{sum_type}'")
        
        return {"pk": paper_summary_obj.pk, "summary_type": summary_type}
    except Exception as e:
        logger.error(f"Ошибка обработки статьи {paper_id}: {e}")
        return {"error": f"Ошибка обработки статьи: {e}"}
    finally:
        try:
            os.remove(pdf_save_path)
            logger.info(f"Временный PDF удален: {pdf_save_path}")
        except OSError as e:
            logger.error(f"Ошибка удаления PDF {pdf_save_path}: {e}")