from django.db import models
from datetime import datetime, timedelta, date

class DiasUteis(models.Model):
    data_inicio = models.DateField()
    data_fim = models.DateField()
    ignorar_domingos = models.BooleanField(default=True)
    incluir_feriados = models.BooleanField(default=False)
    feriados = models.TextField(blank=True, help_text="Insira as datas dos feriados separadas por vírgula (ex: 01/05/2025, 20/06/2025)")

    total_dias_uteis = models.IntegerField(default=0)
    dias_uteis_passados = models.IntegerField(default=0)
    dias_uteis_restantes = models.IntegerField(default=0)
    dias_uteis_lista = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f'Dias úteis de {self.data_inicio} até {self.data_fim}'

    def calcular_dias_uteis(self):
        feriados = []
        if self.feriados:
            try:
                feriados = [datetime.strptime(d.strip(), "%d/%m/%Y").date() for d in self.feriados.split(',') if d.strip()]
            except ValueError:
                feriados = []

        dias_uteis = []
        dias_passados = 0
        hoje = date.today()
        data = self.data_inicio

        while data <= self.data_fim:
            if self.ignorar_domingos and data.weekday() == 6:
                data += timedelta(days=1)
                continue
            if self.incluir_feriados and data in feriados:  # 👈 Aqui está o ajuste
                data += timedelta(days=1)
                continue
            dias_uteis.append(data.strftime('%Y-%m-%d'))
            if data < hoje:
                dias_passados += 1
            data += timedelta(days=1)

        self.total_dias_uteis = len(dias_uteis)
        self.dias_uteis_passados = dias_passados
        self.dias_uteis_restantes = len(dias_uteis) - dias_passados
        self.dias_uteis_lista = dias_uteis

    def save(self, *args, **kwargs):
        self.calcular_dias_uteis()
        super().save(*args, **kwargs)
