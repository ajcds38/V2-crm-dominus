from django.db import models

class DiasUteis(models.Model):
    mes_referencia = models.CharField(max_length=7)  # Ex: "2025-05"
    quantidade = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.mes_referencia} - {self.quantidade} dias úteis"
