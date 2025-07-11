import os
import requests
import spacy
import PyPDF2
import google.generativeai as genai
import logging
import arxiv
from bs4 import BeautifulSoup
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language, activate
from .forms import PaperUploadForm, QuestionForm
from .models import PaperSummary, QuestionAnswer, LocalizedPaperSummary
from django.conf import settings
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse

logger = logging.getLogger(__name__)

# Font registration
try:
    font_dir = os.path.join(settings.BASE_DIR, 'papers', 'fonts')
    noto_sans_regular_path = os.path.join(font_dir, 'NotoSans-Regular.ttf')
    if os.path.exists(noto_sans_regular_path):
        pdfmetrics.registerFont(TTFont('NotoSans', noto_sans_regular_path))
        logger.info("Успешно зарегистрирован шрифт NotoSans (Regular).")
    else:
        logger.warning(f"NotoSans-Regular.ttf не найден по пути {noto_sans_regular_path}.")
    noto_sans_bold_path = os.path.join(font_dir, 'NotoSans-Bold.ttf')
    if os.path.exists(noto_sans_bold_path):
        pdfmetrics.registerFont(TTFont('NotoSans-Bold', noto_sans_bold_path))
        logger.info("Успешно зарегистрирован шрифт NotoSans-Bold.")
        pdfmetrics.registerFontFamily('NotoSans',
                                     normal='NotoSans',
                                     bold='NotoSans-Bold',
                                     italic='NotoSans',
                                     boldItalic='NotoSans-Bold')
    else:
        logger.warning(f"NotoSans-Bold.ttf не найден по пути {noto_sans_bold_path}.")
        pdfmetrics.registerFontFamily('NotoSans',
                                     normal='NotoSans',
                                     bold='NotoSans',
                                     italic='NotoSans',
                                     boldItalic='NotoSans')
except Exception as e:
    logger.error(f"Ошибка при регистрации шрифтов NotoSans: {e}")

def fetch_paper_data(repository, paper_id):
    """Fetch PDF URL and metadata for a paper from the specified repository."""
    if repository == 'arxiv':
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        abs_url = f"https://arxiv.org/abs/{paper_id}"
        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=[paper_id])
            result = next(client.results(search), None)
            if result:
                return {
                    'pdf_url': pdf_url,
                    'abs_url': abs_url,
                    'title': result.title,
                    'authors': ", ".join(author.name for author in result.authors),
                    'abstract': result.summary
                }
        except Exception as e:
            logger.error(f"arXiv API error for ID {paper_id}: {e}")
    elif repository in ['medrxiv', 'biorxiv']:
        base_url = 'https://www.medrxiv.org' if repository == 'medrxiv' else 'https://www.biorxiv.org'
        pdf_url = f"{base_url}/content/10.1101/{paper_id}v1.full.pdf"
        abs_url = f"{base_url}/content/10.1101/{paper_id}v1"
        try:
            response = requests.get(abs_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract title
            title_tag = soup.find('h1', class_=['highwire-cite-title', 'article-title'])
            title = title_tag.text.strip() if title_tag else ''
            # Extract authors
            authors = []
            author_tags = soup.select('div.highwire-cite-authors span.author-name, div.authors-list a.author-name')
            for author in author_tags:
                author_name = author.text.strip()
                if author_name:
                    authors.append(author_name)
            authors_str = ", ".join(authors) if authors else ''
            # Extract abstract
            abstract_tag = soup.find('div', class_=['section abstract', 'abstract-content'])
            abstract = abstract_tag.text.strip() if abstract_tag else ''
            # Print to console for debugging
            print(f"Scraped {repository} metadata for ID {paper_id}:")
            print(f"Title: {title}")
            print(f"Authors: {authors_str}")
            logger.debug(f"Scraped {repository} metadata for ID {paper_id}: Title='{title}', Authors='{authors_str}', Abstract='{abstract[:50]}...'")
            return {
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'title': title,
                'authors': authors_str,
                'abstract': abstract
            }
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {repository} metadata for ID {paper_id}")
            return None
        except Exception as e:
            logger.error(f"{repository.capitalize()} fetch error for ID {paper_id}: {e}")
            return None
    elif repository == 'chemrxiv':
        abs_url = f"https://chemrxiv.org/engage/chemrxiv/article-details/{paper_id}"
        try:
            response = requests.get(abs_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('h1', class_='article-title')
            title = title_tag.text.strip() if title_tag else ''
            authors_tag = soup.find('div', class_='article-authors')
            authors = authors_tag.text.strip() if authors_tag else ''
            abstract_tag = soup.find('div', class_='abstract-content')
            abstract = abstract_tag.text.strip() if abstract_tag else ''
            pdf_link = soup.find('a', href=lambda href: href and '.pdf' in href)
            pdf_url = pdf_link['href'] if pdf_link else abs_url
            print(f"Scraped ChemRxiv metadata for ID {paper_id}:")
            print(f"Title: {title}")
            print(f"Authors: {authors}")
            logger.debug(f"Scraped ChemRxiv metadata for ID {paper_id}: Title='{title}', Authors='{authors}', Abstract='{abstract[:50]}...'")
            return {
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'title': title,
                'authors': authors,
                'abstract': abstract
            }
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching ChemRxiv metadata for ID {paper_id}")
            return None
        except Exception as e:
            logger.error(f"ChemRxiv fetch error for ID {paper_id}: {e}")
            return None
    return None

def download_preprint_pdf(repository, paper_id, save_dir):
    """Download PDF from the specified repository."""
    data = fetch_paper_data(repository, paper_id)
    if not data or not data.get('pdf_url'):
        return None
    file_path = os.path.join(save_dir, f"{paper_id}.pdf")
    os.makedirs(save_dir, exist_ok=True)
    try:
        response = requests.get(data['pdf_url'], stream=True, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Успешно загружен PDF для {repository} ID {paper_id} в {file_path}")
        return file_path
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading PDF for {repository} ID {paper_id}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при загрузке PDF с {repository} для ID {paper_id}: {e}")
        return None
    except IOError as e:
        logger.error(f"Ошибка при сохранении PDF для {repository} ID {paper_id}: {e}")
        return None

def extract_text_and_metadata_from_pdf(file_path):
    text = ""
    title = ""
    authors = ""
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            if reader.metadata:
                title = reader.metadata.get('/Title', '').strip()
                authors = reader.metadata.get('/Author', '').strip()
                if title.startswith('(\ufeff') or title.startswith('( '):
                    title = title[1:]
                if title.endswith(')'):
                    title = title[:-1]
                if authors.startswith('(\ufeff') or authors.startswith('( '):
                    authors = authors[1:]
                if authors.endswith(')'):
                    authors = authors[:-1]
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            logger.info(f"Успешно извлечены текст, название и авторы из {file_path}")
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста/метаданных из PDF {file_path}: {e}")
        raise
    return text, title, authors

def get_gemini_model(model_name='gemini-2.0-flash'):
    try:
        return genai.GenerativeModel(model_name=model_name)
    except Exception as e:
        logger.error(f"Не удалось получить модель Gemini '{model_name}': {e}")
        return None
    
def answer_question_gemini(text, question, target_language="ru"):
    logger.debug(f"answer_question_gemini: Attempting to answer question '{question[:50]}...' in language '{target_language}'")
    model = get_gemini_model()
    if not model:
        return _("Error: Could not connect to Gemini API for answering.")
    
    gemini_target_language = target_language
    if target_language == 'uz':
        gemini_target_language = "Uzbek (Latin script)"
    elif target_language == 'ru':
        gemini_target_language = "Russian (Cyrillic script)"
    elif target_language == 'en':
        gemini_target_language = "English"
    
    prompt = (
        f"Answer the following question about the provided scientific paper text in {gemini_target_language}. "
        f"Ensure the answer is concise, accurate, and relevant to the question and."
        f"Prioratize answering questions based on the scientific paper text provided. If the question is not answerable based on the text, then you can answer the question based on your knowledge, but you should always try to answer based on your knowledge\n\n"
        f"Use readable text without bold formatting.\n\n"
        f"Question: {question}\n\n"
        f"Paper Text:\n{text[:2000]}" 
        f"Answer the questions based on the language '{gemini_target_language}'\n\n"
    )
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.7)
        )
        return response.text
    except Exception as e:
        logger.error(f"Error answering question with Gemini: {e}")
        return f"Error answering question: {e}"

def summarize_text_gemini(text, target_language="ru", summary_type="ordinary"):
    logger.debug(f"summarize_text_gemini: Попытка суммирования на языке '{target_language}', тип '{summary_type}'")
    model = get_gemini_model()
    if not model:
        return _("Ошибка: Не удалось подключиться к Gemini API для суммирования.")
    gemini_target_language = target_language
    if target_language == 'uz':
        gemini_target_language = "Uzbek (Latin script)"
    elif target_language == 'ru':
        gemini_target_language = "Russian (Cyrillic script)"
    if summary_type == 'short':
        prompt = (
            f"Составьте очень краткий summary следующего текста научной статьи на {gemini_target_language}. "
            f"Сосредоточьтесь только на основном вкладе и ключевом результате, представив текст в одном абзаце из 2-3 предложений. "
            f"Убедитесь, что текст читаемый и не использует жирный шрифт.\n\n{text}"
        )
    elif summary_type == 'detailed':
        prompt = (
            f"Составьте подробный summary следующего текста научной статьи на {gemini_target_language} в структурированном формате с разделами:\n"
            f"1. Проблема/Пробел\n2. Методология\n3. Ключевые результаты\n4. Вклад/Значение\n5. Ограничения\n6. Будущая работа\n"
            f"Представьте каждый раздел в отдельном абзаце, начиная с номера и заголовка, без жирного шрифта. "
            f"Убедитесь, что текст читаемый.\n\n{text}"
        )
    else:  # ordinary
        prompt = (
            f"Составьте стандартный summary следующего текста научной статьи на {gemini_target_language}. "
            f"Представьте текст в 1-3 абзацах, разделяя аспекты: \n"
            f"1. Основная проблема\n2. Методы\n3. Результаты и выводы\n"
            f"Убедитесь, что текст читаемый и без жирного шрифта.\n\n{text}"
        )
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.7)
        )
        return response.text
    except Exception as e:
        logger.error(f"Ошибка суммирования Gemini: {e}")
        return f"Ошибка при суммировании текста: {e}"

def upload_paper(request):
    if request.method == 'POST':
        form = PaperUploadForm(request.POST)
        if form.is_valid():
            repository = form.cleaned_data['repository']
            paper_id = form.cleaned_data['arxiv_id'].strip()
            summary_type = form.cleaned_data['summary_type']
            file_name_for_db = f"{repository}:{paper_id}"
            data = fetch_paper_data(repository, paper_id)
            if not data:
                return render(request, 'papers/upload.html', {
                    'form': form,
                    'error_message': _(f"Не удалось найти статью с ID {paper_id} на {repository}.")
                })
            try:
                existing_paper = PaperSummary.objects.get(file_name=file_name_for_db)
                logger.info(f"Статья с {repository} ID '{paper_id}' уже существует.")
                success_url = reverse('upload_success', kwargs={'pk': existing_paper.pk})
                success_url += f'?cached_status=true&summary_type={summary_type}'
                return redirect(success_url)
            except PaperSummary.DoesNotExist:
                logger.info(f"Статья с {repository} ID '{paper_id}' не существует. Продолжаем обработку.")
            pdf_save_path = download_preprint_pdf(repository, paper_id, settings.MEDIA_ROOT)
            if not pdf_save_path:
                return render(request, 'papers/upload.html', {
                    'form': form,
                    'error_message': _(f"Не удалось загрузить PDF с {repository} ID: {paper_id}.")
                })
            try:
                extracted_text, extracted_title, extracted_authors = extract_text_and_metadata_from_pdf(pdf_save_path)
                if not extracted_text:
                    logger.warning(f"Извлечено ноль текста из PDF {paper_id}.")
                    return render(request, 'papers/upload.html', {
                        'form': form,
                        'error_message': _("Не удалось извлечь текст из PDF.")
                    })
                logger.info(f"Извлечен текст из PDF: {len(extracted_text)} символов.")
                logger.info(f"Извлеченное название: {extracted_title}, Авторы: {extracted_authors}")
            except Exception as e:
                logger.error(f"Ошибка извлечения текста/метаданных из PDF {paper_id}: {e}")
                return render(request, 'papers/upload.html', {
                    'form': form,
                    'error_message': _("Ошибка извлечения текста из PDF: {error}").format(error=e)
                })
            finally:
                try:
                    os.remove(pdf_save_path)
                    logger.info(f"Временный PDF удален: {pdf_save_path}")
                except OSError as e:
                    logger.error(f"Ошибка удаления временного PDF {pdf_save_path}: {e}")
            current_active_language = get_language()
            paper_summary_obj = PaperSummary.objects.create(
                file_name=file_name_for_db,
                text_content=extracted_text,
                title=data.get('title', extracted_title),  # Prefer scraped title
                authors=data.get('authors', extracted_authors),  # Prefer scraped authors
                url=data.get('abs_url', '')
            )
            logger.info(f"Объект PaperSummary создан с ID: {paper_summary_obj.pk}")
            summary_content = summarize_text_gemini(extracted_text, target_language=current_active_language, summary_type=summary_type)
            LocalizedPaperSummary.objects.create(
                paper_summary=paper_summary_obj,
                language=current_active_language,
                summary_text=summary_content,
                summary_type=summary_type
            )
            logger.info(f"LocalizedPaperSummary создан для '{paper_id}' на {current_active_language}, тип '{summary_type}'.")
            success_url = reverse('upload_success', kwargs={'pk': paper_summary_obj.pk})
            success_url += f'?cached_status=false&summary_type={summary_type}'
            return redirect(success_url)
    else:
        form = PaperUploadForm()
    return render(request, 'papers/upload.html', {'form': form})

def upload_success(request, pk):
    paper_summary_obj = get_object_or_404(PaperSummary, pk=pk)
    extracted_text = paper_summary_obj.text_content
    paper_filename = paper_summary_obj.file_name
    article_title = paper_summary_obj.title
    article_authors = paper_summary_obj.authors
    article_url = paper_summary_obj.url
    question_form = QuestionForm()
    answer_content = ""
    is_cached_paper = request.GET.get('cached_status', 'false') == 'true'
    summary_type = request.GET.get('summary_type', 'ordinary')
    current_active_language = get_language()
    if request.method == 'POST':
        if 'language' in request.POST:
            selected_language = request.POST['language']
            activate(selected_language)
            current_active_language = selected_language
            logger.info(f"Язык изменен на: {current_active_language}")
        if 'summary_type' in request.POST:
            summary_type = request.POST['summary_type']
        if 'summarize' in request.POST:
            summary_type = request.POST.get('summary_type', 'ordinary')
            logger.info(f"PaperSummary {pk}: Запрошено повторное суммирование для языка '{current_active_language}', тип '{summary_type}'.")
            summary_content = summarize_text_gemini(extracted_text, target_language=current_active_language, summary_type=summary_type)
            LocalizedPaperSummary.objects.update_or_create(
                paper_summary=paper_summary_obj,
                language=current_active_language,
                summary_type=summary_type,
                defaults={'summary_text': summary_content}
            )
            is_cached_paper = False
        elif 'ask_question' in request.POST:
            question_form = QuestionForm(request.POST)
            if question_form.is_valid():
                user_question = question_form.cleaned_data['question'].strip().lower()
                obj, created = QuestionAnswer.objects.get_or_create(
                    paper_summary=paper_summary_obj,
                    question=user_question,
                    answer_language=current_active_language,
                    defaults={
                        'answer': answer_question_gemini(paper_summary_obj.text_content, user_question, target_language=current_active_language)
                    }
                )
                answer_content = obj.answer
                logger.info(f"PaperSummary {pk}: {'Сгенерирован новый' if created else 'Использован кэшированный'} ответ для вопроса '{user_question[:50]}...'.")
            else:
                logger.warning(f"PaperSummary {pk}: Форма вопроса недействительна: {question_form.errors}")
        elif 'highlighted_question' in request.POST:
            user_question = request.POST.get('highlighted_question', '').strip().lower()
            highlighted_text = request.POST.get('highlighted_text', '').strip()
            if user_question and highlighted_text:
                full_question = f"Regarding the highlighted text: '{highlighted_text}'\n{user_question}"
                obj, created = QuestionAnswer.objects.get_or_create(
                    paper_summary=paper_summary_obj,
                    question=full_question,
                    answer_language=current_active_language,
                    defaults={
                        'answer': answer_question_gemini(paper_summary_obj.text_content, full_question, target_language=current_active_language)
                    }
                )
                answer_content = obj.answer
    summary_content = ""
    try:
        localized_summary = LocalizedPaperSummary.objects.get(
            paper_summary=paper_summary_obj,
            language=current_active_language,
            summary_type=summary_type
        )
        summary_content = localized_summary.summary_text
    except LocalizedPaperSummary.DoesNotExist:
        logger.info(f"PaperSummary {pk}: Кэшированный summary не найден для языка '{current_active_language}', тип '{summary_type}'.")
        summary_content = summarize_text_gemini(extracted_text, target_language=current_active_language, summary_type=summary_type)
        LocalizedPaperSummary.objects.create(
            paper_summary=paper_summary_obj,
            language=current_active_language,
            summary_text=summary_content,
            summary_type=summary_type
        )
        is_cached_paper = False
    return render(request, 'papers/upload_success.html', {
        'summary': summary_content,
        'extracted_text': extracted_text,
        'question_form': question_form,
        'answer': answer_content,
        'paper_filename': paper_filename,
        'current_language': current_active_language,
        'paper_pk': paper_summary_obj.pk,
        'is_cached_paper': is_cached_paper,
        'article_title': article_title,
        'article_authors': article_authors,
        'article_url': article_url,
        'summary_type': summary_type,
        'summary_types': [('short', _('Короткий')), ('ordinary', _('Стандартный')), ('detailed', _('Подробный'))],
        'related_papers': []
    })

def download_summary_pdf(request, pk):
    paper_summary_obj = get_object_or_404(PaperSummary, pk=pk)
    current_active_language = get_language()
    summary_type = request.GET.get('summary_type', 'ordinary')
    try:
        localized_summary = LocalizedPaperSummary.objects.get(
            paper_summary=paper_summary_obj,
            language=current_active_language,
            summary_type=summary_type
        )
        summary_content = localized_summary.summary_text
    except LocalizedPaperSummary.DoesNotExist:
        summary_content = _("Summary не доступен на этом языке.")
        logger.warning(f"Summary не найден для статьи {pk} на языке {current_active_language}, тип {summary_type}")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    unicode_font = 'NotoSans'
    unicode_font_bold = 'NotoSans-Bold' if 'NotoSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'NotoSans'
    title_style = ParagraphStyle(
        name='TitleStyle',
        fontName='Times-Bold',
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    author_style = ParagraphStyle(
        name='AuthorStyle',
        fontName=unicode_font,
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor='#666666',
    )
    heading_style = ParagraphStyle(
        name='HeadingStyle',
        fontName=unicode_font_bold,
        fontSize=14,
        spaceAfter=10,
        alignment=TA_LEFT,
    )
    normal_style = ParagraphStyle(
        name='NormalStyle',
        fontName=unicode_font,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
    )
    elements = []
    title_text = paper_summary_obj.title or _("Название недоступно")
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.2 * inch))
    authors_text = (_("Авторы: ") + paper_summary_obj.authors) if paper_summary_obj.authors else _("Авторы недоступны")
    elements.append(Paragraph(authors_text, author_style))
    elements.append(Spacer(1, 0.2 * inch))
    if paper_summary_obj.url:
        url_text = _("Оригинальный URL статьи: ") + paper_summary_obj.url
        elements.append(Paragraph(url_text, normal_style))
        elements.append(Spacer(1, 0.2 * inch))
    summary_heading = _("Сгенерированное резюме") + f" ({_(current_active_language).upper()}, {summary_type.capitalize()}):"
    elements.append(Paragraph(summary_heading, heading_style))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(summary_content, normal_style))
    doc.build(elements)
    pdf_content = buffer.getvalue()
    buffer.close()
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{paper_summary_obj.file_name}_summary_{current_active_language}_{summary_type}.pdf"'
    return response

def download_original_pdf(request, arxiv_id):
    repository, paper_id = arxiv_id.split(':', 1) if ':' in arxiv_id else ('arxiv', arxiv_id)
    data = fetch_paper_data(repository, paper_id)
    if not data or not data.get('pdf_url'):
        logger.error(f"Не удалось найти PDF для {repository} ID {paper_id}")
        return HttpResponse(_("Не удалось загрузить оригинальный PDF."), status=404)
    try:
        response = requests.get(data['pdf_url'], stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        django_response = HttpResponse(response.iter_content(chunk_size=8192), content_type='application/pdf')
        django_response['Content-Disposition'] = f'attachment; filename="{paper_id}.pdf"'
        return django_response
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при загрузке PDF для {repository} ID {paper_id}: {e}")
        return HttpResponse(_("Не удалось загрузить оригинальный PDF: {error}").format(error=e), status=404)

def search_articles(request):
    model = get_gemini_model()
    if not model:
        return render(request, "papers/search_results.html", {
            "error": _("Не удалось подключиться к Gemini API."),
            "query": ""
        })
    if request.method == "POST":
        query = request.POST.get("search_query", "").strip()
        original_language = request.POST.get("original_language", "en")  # Get the original language from the form

        if not query:
            return render(request, "papers/search_results.html", {
                "error": _("Пожалуйста, введите запрос для поиска."),
                "query": query
            })

        try:
            # Use Gemini to translate the query to English acronym if not already in English
            if original_language != "en":
                prompt = f"Translate the following text to english. Be specific about the terms. Return only translated version '{query}'. If the text is already in English or an acronym, return it as is."
                response = model.generate_content(prompt)
                translated_query = response.text.strip()
                logger.info(f"'{translated_query}'")
                query = translated_query
            else:
                logger.info(f"Query already in English or acronym: '{query}'")

            topic = query
            logger.info(f"Query: {query}, Using Topic: {topic}")
            client = arxiv.Client()
            search = arxiv.Search(
                query=f"ti:\"{topic}\" OR all:{topic} cat:cs.*",
                max_results=200,
                sort_by=arxiv.SortCriterion.Relevance
            )
            title_results = []
            abstract_results = []
            topic_terms = topic.lower().split()
            seen_arxiv_ids = set()
            for result in client.results(search):
                if len(title_results) + len(abstract_results) >= 30:
                    break
                arxiv_id = result.entry_id.split('/')[-1]
                if arxiv_id in seen_arxiv_ids:
                    continue
                title_lower = result.title.lower()
                abstract_lower = result.summary.lower()
                result_data = {
                    "arxiv_id": arxiv_id,
                    "title": result.title,
                    "authors": ", ".join(author.name for author in result.authors),
                    "url": result.entry_id,
                    "abstract": result.summary
                }
                if topic.lower() == title_lower:
                    title_results.insert(0, result_data)
                elif any(term in title_lower for term in topic_terms):
                    title_results.append(result_data)
                elif any(term in abstract_lower for term in topic_terms):
                    abstract_results.append(result_data)
                seen_arxiv_ids.add(arxiv_id)
            results = title_results + abstract_results
            logger.info(f"Found {len(results)} results for topic: {topic}")
            if not results:
                return render(request, "papers/search_results.html", {
                    "error": _(f"Статьи по теме '{topic}' не найдены."),
                    "query": query
                })
            return render(request, "papers/search_results.html", {
                "results": results[:30],
                "query": query,
                "original_query": request.POST.get("search_query"),  # For display/debugging
                "original_language": original_language
            })
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return render(request, "papers/search_results.html", {
                "error": _(f"Ошибка поиска: {e}"),
                "query": query
            })
    return render(request, "papers/search_results.html", {})

def fetch_paper_data(repository, paper_id):
    """Fetch PDF URL and metadata for a paper from the specified repository."""
    if repository == 'arxiv':
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        abs_url = f"https://arxiv.org/abs/{paper_id}"
        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=[paper_id])
            result = next(client.results(search), None)
            if result:
                return {
                    'pdf_url': pdf_url,
                    'abs_url': abs_url,
                    'title': result.title,
                    'authors': ", ".join(author.name for author in result.authors),
                    'abstract': result.summary
                }
        except Exception as e:
            logger.error(f"arXiv API error for ID {paper_id}: {e}")
    elif repository in ['medrxiv', 'biorxiv']:
        base_url = 'https://www.medrxiv.org' if repository == 'medrxiv' else 'https://www.biorxiv.org'
        pdf_url = f"{base_url}/content/10.1101/{paper_id}v1.full.pdf"
        abs_url = f"{base_url}/content/10.1101/{paper_id}v1"
        try:
            response = requests.get(abs_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract title
            title_tag = soup.find('h1', class_=['article-title', 'highwire-cite-title'])
            title = title_tag.text.strip() if title_tag else ''
            # Extract authors
            authors = []
            author_tags = soup.select('div.highwire-cite-authors span.author-name')
            for author in author_tags:
                author_name = author.text.strip()
                if author_name:
                    authors.append(author_name)
            authors_str = ", ".join(authors) if authors else ''
            # Extract abstract
            abstract_tag = soup.find('div', class_=['abstract-content', 'section abstract'])
            abstract = abstract_tag.text.strip() if abstract_tag else ''
            # Print to console for debugging
            print(f"Scraped {repository} metadata for ID {paper_id}:")
            print(f"Title: {title}")
            print(f"Authors: {authors_str}")
            logger.debug(f"Scraped {repository} metadata for ID {paper_id}: Title='{title}', Authors='{authors_str}', Abstract='{abstract[:50]}...'")
            return {
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'title': title,
                'authors': authors_str,
                'abstract': abstract
            }
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {repository} metadata for ID {paper_id}")
            return None
        except Exception as e:
            logger.error(f"{repository.capitalize()} fetch error for ID {paper_id}: {e}")
            return None
    elif repository == 'chemrxiv':
        abs_url = f"https://chemrxiv.org/engage/chemrxiv/article-details/{paper_id}"
        try:
            response = requests.get(abs_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('h1', class_='article-title')
            title = title_tag.text.strip() if title_tag else ''
            authors_tag = soup.find('div', class_='article-authors')
            authors = authors_tag.text.strip() if authors_tag else ''
            abstract_tag = soup.find('div', class_='abstract-content')
            abstract = abstract_tag.text.strip() if abstract_tag else ''
            pdf_link = soup.find('a', href=lambda href: href and '.pdf' in href)
            pdf_url = pdf_link['href'] if pdf_link else abs_url
            logger.debug(f"Scraped ChemRxiv metadata for ID {paper_id}: Title='{title}', Authors='{authors}', Abstract='{abstract[:50]}...'")
            return {
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'title': title,
                'authors': authors,
                'abstract': abstract
            }
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching ChemRxiv metadata for ID {paper_id}")
            return None
        except Exception as e:
            logger.error(f"ChemRxiv fetch error for ID {paper_id}: {e}")
            return None
    return None

def paper_summary(request, arxiv_id):
    logger.debug(f"Starting paper_summary for ID {arxiv_id}")
    repository, paper_id = arxiv_id.split(':', 1) if ':' in arxiv_id else ('arxiv', arxiv_id)
    file_name = f"{repository}:{paper_id}"
    try:
        paper_summary = PaperSummary.objects.get(file_name=file_name)
        is_cached_paper = True
    except PaperSummary.DoesNotExist:
        data = fetch_paper_data(repository, paper_id)
        if not data:
            logger.error(f"ID {paper_id} not found in {repository}.")
            return render(request, 'papers/upload_success.html', {
                'error_message': _(f"Статья с ID {paper_id} не найдена на {repository}.")
            })
        pdf_save_path = download_preprint_pdf(repository, paper_id, settings.MEDIA_ROOT)
        if not pdf_save_path:
            logger.error(f"Failed to download PDF for {repository} ID {paper_id}.")
            return render(request, 'papers/upload_success.html', {
                'error_message': _(f"Не удалось загрузить PDF с {repository} ID {paper_id}.")
            })
        try:
            extracted_text, extracted_title, extracted_authors = extract_text_and_metadata_from_pdf(pdf_save_path)
            if not extracted_text:
                logger.warning(f"No text extracted from PDF for {repository} ID {paper_id}.")
                return render(request, 'papers/upload_success.html', {
                    'error_message': _("Не удалось извлечь текст из PDF.")
                })
            # Always prefer scraped metadata for medRxiv/bioRxiv, fallback to PDF only for arXiv if scraped fails
            final_title = data.get('title', extracted_title) if repository != 'arxiv' or not data.get('title') else data.get('title', '')
            final_authors = data.get('authors', extracted_authors) if repository != 'arxiv' or not data.get('authors') else data.get('authors', '')
        except Exception as e:
            logger.error(f"Error extracting text/metadata from PDF {paper_id}: {e}")
            return render(request, 'papers/upload_success.html', {
                'error_message': _(f"Ошибка извлечения текста из PDF: {e}")
            })
        finally:
            try:
                os.remove(pdf_save_path)
            except OSError as e:
                logger.error(f"Error deleting PDF {pdf_save_path}: {e}")
        paper_summary = PaperSummary.objects.create(
            file_name=file_name,
            text_content=extracted_text,
            title=final_title,
            authors=final_authors,
            url=data.get('abs_url', '')
        )
        is_cached_paper = False
    current_language = get_language()
    summary_type = request.POST.get('summary_type', request.GET.get('summary_type', 'ordinary'))
    question_form = QuestionForm()
    answer_content = ""
    if request.method == 'POST':
        if 'language' in request.POST:
            selected_language = request.POST['language']
            activate(selected_language)
            current_language = selected_language
        if 'summarize' in request.POST:
            summary_type = request.POST.get('summary_type', 'ordinary')
        if 'ask_question' in request.POST:
            question_form = QuestionForm(request.POST)
            if question_form.is_valid():
                user_question = question_form.cleaned_data['question'].strip().lower()
                obj, created = QuestionAnswer.objects.get_or_create(
                    paper_summary=paper_summary,
                    question=user_question,
                    answer_language=current_language,
                    defaults={
                        'answer': answer_question_gemini(paper_summary.text_content, user_question, target_language=current_language)
                    }
                )
                answer_content = obj.answer
        elif 'highlighted_question' in request.POST:
            user_question = request.POST.get('highlighted_question', '').strip().lower()
            highlighted_text = request.POST.get('highlighted_text', '').strip()
            if user_question and highlighted_text:
                full_question = f"Regarding the highlighted text: '{highlighted_text}'\n{user_question}"
                obj, created = QuestionAnswer.objects.get_or_create(
                    paper_summary=paper_summary,
                    question=full_question,
                    answer_language=current_language,
                    defaults={
                        'answer': answer_question_gemini(paper_summary.text_content, full_question, target_language=current_language)
                    }
                )
                answer_content = obj.answer
    try:
        localized_summary = LocalizedPaperSummary.objects.get(
            paper_summary=paper_summary,
            language=current_language,
            summary_type=summary_type
        )
        summary_content = localized_summary.summary_text
    except LocalizedPaperSummary.DoesNotExist:
        summary_content = summarize_text_gemini(paper_summary.text_content, target_language=current_language, summary_type=summary_type)
        LocalizedPaperSummary.objects.create(
            paper_summary=paper_summary,
            language=current_language,
            summary_text=summary_content,
            summary_type=summary_type
        )
        is_cached_paper = False
    return render(request, 'papers/upload_success.html', {
        'summary': summary_content,
        'extracted_text': paper_summary.text_content,
        'question_form': question_form,
        'answer': answer_content,
        'paper_filename': paper_summary.file_name,
        'current_language': current_language,
        'paper_pk': paper_summary.pk,
        'is_cached_paper': is_cached_paper,
        'article_title': paper_summary.title,
        'article_authors': paper_summary.authors,
        'article_url': paper_summary.url,
        'summary_type': summary_type,
        'summary_types': [('short', _('Короткий')), ('ordinary', _('Стандартный')), ('detailed', _('Подробный'))],
        'related_papers': []
    })

try:
    gemini_api_key = settings.GEMINI_API_KEY
    if not gemini_api_key or gemini_api_key == 'your_dev_api_key_if_needed':
        logger.warning("GEMINI_API_KEY не установлен.")
    else:
        genai.configure(api_key=gemini_api_key)
        logger.info("Gemini API успешно настроен.")
except Exception as e:
    logger.error(f"Ошибка конфигурации Gemini API: {e}")