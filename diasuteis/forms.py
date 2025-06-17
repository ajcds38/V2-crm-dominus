from django import forms
from .models import DiasUteis

class DiasUteisForm(forms.ModelForm):
    class Meta:
        model = DiasUteis
        fields = ['data_inicio', 'data_fim', 'ignorar_domingos', 'incluir_feriados', 'feriados']
        widgets = {
            'feriados': forms.Textarea(attrs={'rows': 2}),
        }
