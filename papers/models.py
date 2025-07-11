from django.db import models
from django.utils.translation import gettext_lazy as _

class PaperSummary(models.Model):
    """
    Модель для хранения информации и извлеченного текста статьи с Arxiv.
    """
    file_name = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("Оригинальное имя файла загруженного PDF.")
    )
    text_content = models.TextField(
        help_text=_("Извлеченный текст из PDF.")
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Временная метка загрузки статьи.")
    )
    title = models.TextField(
        blank=True,
        null=True,
        help_text=_("Название, извлеченное из метаданных PDF.")
    )
    authors = models.TextField(
        blank=True,
        null=True,
        help_text=_("Авторы, извлеченные из метаданных PDF.")
    )
    url = models.URLField(
        blank=True,
        null=True,
        help_text=_("URL оригинальной статьи (например, ссылка на ArXiv).")
    )

    def __str__(self):
        return self.file_name

    class Meta:
        verbose_name = _("Summary статьи")
        verbose_name_plural = _("Summaries статей")
        ordering = ['-uploaded_at']

class LocalizedPaperSummary(models.Model):
    """
    Модель для хранения summaries статей на разных языках и типах.
    """
    paper_summary = models.ForeignKey(
        PaperSummary,
        on_delete=models.CASCADE,
        related_name='localized_summaries',
        help_text=_("Статья, к которой относится этот summary.")
    )
    language = models.CharField(
        max_length=10,
        help_text=_("Код языка summary (например, 'ru', 'en', 'uz').")
    )
    summary_text = models.TextField(
        help_text=_("Текст сгенерированного summary.")
    )
    summary_type = models.CharField(
        max_length=20,
        choices=[
            ('short', _('Короткий')),
            ('ordinary', _('Стандартный')),
            ('detailed', _('Подробный')),
        ],
        default='ordinary',
        help_text=_("Тип summary (короткий, стандартный или подробный).")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Временная метка создания summary.")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Временная метка последнего обновления summary.")
    )

    class Meta:
        unique_together = ('paper_summary', 'language', 'summary_type')
        verbose_name = _("Локализованный summary статьи")
        verbose_name_plural = _("Локализованные summaries статей")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_summary_type_display()} summary для {self.paper_summary.file_name} на {self.language}"

class QuestionAnswer(models.Model):
    """
    Модель для хранения вопросов и ответов, связанных со статьей.
    """
    paper_summary = models.ForeignKey(
        PaperSummary,
        on_delete=models.CASCADE,
        related_name='questions_answers',
        help_text=_("Статья, к которой относятся вопрос и ответ.")
    )
    question = models.CharField(
        max_length=500,
        help_text=_("Вопрос пользователя о статье.")
    )
    answer = models.TextField(
        blank=True,
        null=True,
        help_text=_("Ответ, сгенерированный Gemini на вопрос.")
    )
    answer_language = models.CharField(
        max_length=10,
        default='ru',
        help_text=_("Код языка ответа (например, 'ru', 'uz', 'en').")
    )
    answered_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Временная метка ответа на вопрос.")
    )

    class Meta:
        unique_together = ('paper_summary', 'question', 'answer_language')
        verbose_name = _("Вопрос и ответ")
        verbose_name_plural = _("Вопросы и ответы")
        ordering = ['answered_at']

    def __str__(self):
        return f"В: {self.question[:70]}... (для {self.paper_summary.file_name})"