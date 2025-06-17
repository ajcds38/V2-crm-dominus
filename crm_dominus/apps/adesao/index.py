{% extends "base.html" %}
{% block content %}
<h2>Resultados por Cidade - Adesão</h2>

<p>Período: {{ data_inicio }} até {{ data_fim }}</p>

<table border="1" cellpadding="5" cellspacing="0">
    <thead>
        <tr>
            <th>Cidade</th>
            <th>Meta</th>
            <th>Realizado</th>
            <th>Projeção</th>
            <th>% Projeção</th>
            <th>Ticket Médio</th>
            <th>Produtividade</th>
        </tr>
    </thead>
    <tbody>
        {% for item in dados %}
        <tr>
            <td>{{ item.cidade }}</td>
            <td>{{ item.meta|floatformat:0 }}</td>
            <td>{{ item.volume|floatformat:0 }}</td>
            <td>{{ item.projecao|floatformat:0 }}</td>
            <td>{{ item.proj_percentual|floatformat:2 }}</td>
            <td>{{ item.ticket_medio|floatformat:2 }}</td>
            <td>{{ item.produtividade|floatformat:2 }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<hr>
<h3>Totais:</h3>
<ul>
    <li>Meta Total: {{ totais.meta }}</li>
    <li>Realizado Total: {{ totais.realizado }}</li>
    <li>Projeção Total: {{ totais.projecao }}</li>
    <li>Projeção % Total: {{ totais.proj_percentual|floatformat:2 }}</li>
    <li>Ticket Médio Geral: {{ totais.ticket_medio|floatformat:2 }}</li>
    <li>Produtividade Média: {{ totais.produtividade|floatformat:2 }}</li>
</ul>
{% endblock %}
