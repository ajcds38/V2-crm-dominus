from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import DiasUteis
from .forms import DiasUteisForm

@login_required
def configurar_dias_uteis(request):
    if request.method == 'POST':
        dias_uteis = DiasUteis.objects.last()
        form = DiasUteisForm(request.POST, instance=dias_uteis)
        if form.is_valid():
            form.save()
            return redirect('dias_uteis_configurar')
    else:
        dias_uteis = DiasUteis.objects.last()
        form = DiasUteisForm(instance=dias_uteis)

    # Recarrega o objeto atualizado após salvar
    dias_uteis_atualizado = DiasUteis.objects.last()

    context = {
        'form': form,
        'total_dias': dias_uteis_atualizado.total_dias_uteis if dias_uteis_atualizado else None,
        'dias_passados': dias_uteis_atualizado.dias_uteis_passados if dias_uteis_atualizado else None,
        'dias_restantes': dias_uteis_atualizado.dias_uteis_restantes if dias_uteis_atualizado else None,
    }

    return render(request, 'diasuteis/configurar.html', context)

def calcular_dias_uteis_ajax(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    ignorar_domingos = request.GET.get('ignorar_domingos') == 'true'
    incluir_feriados = request.GET.get('incluir_feriados') == 'true'
    feriados_raw = request.GET.get('feriados', '')

    try:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    except:
        return JsonResponse({'erro': 'Datas inválidas'})

    feriados = []
    for f in feriados_raw.split(','):
        try:
            feriados.append(datetime.strptime(f.strip(), '%d/%m/%Y').date())
        except:
            pass

    total = 0
    dias_passados = 0
    dias_restantes = 0
    hoje = datetime.today().date()

    dia_atual = data_inicio
    while dia_atual <= data_fim:
        if ignorar_domingos and dia_atual.weekday() == 6:
            dia_atual += timedelta(days=1)
            continue
        if not incluir_feriados and dia_atual in feriados:
            dia_atual += timedelta(days=1)
            continue
        total += 1
        if dia_atual < hoje:
            dias_passados += 1
        else:
            dias_restantes += 1
        dia_atual += timedelta(days=1)

    return JsonResponse({
        'total': total,
        'passados': dias_passados,
        'restantes': dias_restantes
    })
