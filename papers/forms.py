from django import forms
from django.utils.translation import gettext_lazy as _

SUMMARY_TYPE_CHOICES = [
    ('short', _('Короткий')),
    ('ordinary', _('Стандартный')),
    ('detailed', _('Подробный')),
]

REPOSITORY_CHOICES = [
    ('arxiv', 'arXiv'),
    ('medrxiv', 'medRxiv'),
    ('biorxiv', 'bioRxiv'),
    ('chemrxiv', 'ChemRxiv'),
]

class PaperUploadForm(forms.Form):
    arxiv_id = forms.CharField(
        label=_("Введите ID статьи Arxiv"),
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': _('Например, 2506.08872')})
    )
    summary_type = forms.ChoiceField(
        label=_("Тип summary"),
        choices=SUMMARY_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    repository = forms.ChoiceField(
        choices=REPOSITORY_CHOICES,
        label=_("Repository"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class QuestionForm(forms.Form):
    question = forms.CharField(
        label=_(""),
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': _('Введите ваш вопрос здесь...')}),
        max_length=500,
        required=True
    )