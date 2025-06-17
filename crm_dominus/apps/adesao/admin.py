from django.contrib import admin
from .models import DiasUteis

@admin.register(DiasUteis)
class DiasUteisAdmin(admin.ModelAdmin):
    list_display = ('mes_referencia', 'quantidade')
    search_fields = ('mes_referencia',)
