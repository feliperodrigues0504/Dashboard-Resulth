# MÓDULO ALERTAS — Especificação e Implementação

> Fase 5 do roadmap. Painel transversal que consolida sinais de todos os módulos
> em uma única tela de gestão por exceção.
> **Data de implementação:** 2026-06-12

---

## Objetivo

Dar ao gestor uma visão de "semáforo" em tempo real dos pontos críticos do negócio,
sem precisar navegar por todos os módulos. Os alertas são prioridades, não relatórios.

---

## Requisitos atendidos

| Requisito | Status | Observação |
|-----------|--------|------------|
| Consolida sinais de todos os módulos | ✅ | Financeiro + Comercial + Estoque + Compras |
| Classificação por severidade | ✅ | Crítico / Urgente / Atenção |
| Filtro por módulo e nível | ✅ | Aba "Todos" com multiselect |
| Cards visuais com cor por severidade | ✅ | Borda esquerda colorida + ícone |
| Valor monetário associado ao alerta | ✅ | Exibido à direita do card quando aplicável |
| Gráfico de distribuição por módulo | ✅ | Pizza + barras empilhadas por nível |
| Abas por módulo com link direto | ✅ | Aba por módulo + `st.page_link` |
| Parâmetros configuráveis (thresholds) | ✅ | Aba Configurações com tabela + arquivo `CFG` |
| Impressão | ✅ | Botão no cabeçalho |
| Atualização automática (cache 5min) | ✅ | `@st.cache_data(ttl=300)` |

---

## Fontes de dados

O módulo Alertas não acessa o Firebird diretamente — ele **delega** para as funções dos outros módulos:

| Módulo | Funções utilizadas |
|--------|--------------------|
| `core/domain/financeiro.py` | `get_contas_receber`, `get_contas_pagar`, `get_saldo_bancario`, `get_kpis`, `get_estoque_custo`, `get_pmr_pmp`, `get_projecao_acumulada` |
| `core/domain/comercial.py` | `get_faturamento`, `get_ultima_compra_clientes`, `get_clientes_sem_comprar`, `get_clientes_queda_compras`, `get_concentracao_clientes` |
| `core/domain/estoque.py` | `get_estoque_geral`, `get_ultima_venda`, `get_estoque_parado`, `get_controle_operacional`, `get_produtos_sem_venda` |
| `core/domain/compras.py` | `get_compras_por_fornecedor`, `get_produtos_sem_giro`, `get_estoque_parado_por_fornecedor` |

---

## Alertas implementados

### Financeiro

| Alerta | Nível | Threshold |
|--------|-------|-----------|
| Caixa projetado negativo em 7 dias | Crítico | Saldo mínimo < 0 |
| Caixa abaixo do piso mínimo em 7 dias | Urgente | Saldo mínimo < R$50k |
| AP já vencidos e em aberto | Crítico | Qualquer AP com DT_VENCIMENTO < hoje |
| AP vencendo nas próximas 48h | Urgente | AP com vencimento hoje/amanhã |
| Clientes AR com atraso >90 dias | Crítico | count > 0 |
| % AR vencido elevado | Urgente | >80% do total AR está vencido |
| Capital operacional negativo | Crítico | capital < 0 |
| Capital operacional abaixo do mínimo | Atenção | capital < R$100k |
| Saldo bancário desatualizado | Atenção | Último MOVIBAN > 3 dias atrás |
| PMR elevado | Urgente/Atenção | PMR > 30d (urgente: >45d) |

### Comercial

| Alerta | Nível | Threshold |
|--------|-------|-----------|
| Clientes sem comprar há >60 dias | Urgente (se >10) / Atenção | count ≥ 1 |
| Clientes com queda ≥40% nas compras | Atenção | Queda_% ≥ 40 |
| Concentração top 3 clientes ≥60% | Urgente (≥75%) / Atenção | top3_pct ≥ 60 |

### Estoque

| Alerta | Nível | Threshold |
|--------|-------|-----------|
| SKUs parados >90d com alto valor | Urgente (>R$200k) / Atenção | valor ≥ R$20k |
| Ruptura crítica (poucos SKUs com estoque) | Urgente | SKUs com estoque < 300 |
| Produtos abaixo do estoque mínimo | Atenção | count > 0 e EST_MINIMO cadastrado |
| Produtos com estoque sem nenhuma venda | Atenção | valor ≥ R$10k |

### Compras

| Alerta | Nível | Threshold |
|--------|-------|-----------|
| Dependência alta — top 1 fornecedor | Urgente (≥40%) / Atenção | participação ≥ 30% |
| Concentração top 3 fornecedores | Atenção | top3_pct ≥ 60% |
| Produtos comprados sem giro | Atenção | valor ≥ R$50k |
| Estoque parado por fornecedor (>90d) | Atenção | valor ≥ R$20k |

---

## Estrutura de arquivos

```
core/domain/alertas.py         — motor de alertas (função get_todos_alertas + parciais por módulo)
pages/05_Alertas.py     — página Streamlit (6 abas)
docs/MODULO_ALERTAS.md  — este arquivo
```

### Funções em `core/domain/alertas.py`

| Função | Retorno |
|--------|---------|
| `alertas_financeiro()` | `list[dict]` — alertas do módulo Financeiro |
| `alertas_comercial()` | `list[dict]` — alertas do módulo Comercial |
| `alertas_estoque()` | `list[dict]` — alertas do módulo Estoque |
| `alertas_compras(ini, fim)` | `list[dict]` — alertas do módulo Compras |
| `get_todos_alertas(ini, fim)` | `list[dict]` — todos unidos e ordenados por severidade |
| `resumo_alertas(alertas)` | `dict` — contagens por nível e por módulo |

### Formato padrão de alerta

```python
{
    'nivel':   'critico' | 'urgente' | 'atencao',
    'modulo':  'Financeiro' | 'Comercial' | 'Estoque' | 'Compras',
    'icone':   str,          # Bootstrap Icons key
    'titulo':  str,          # frase curta
    'detalhe': str,          # frase explicativa
    'valor':   float | None, # valor monetário (R$) se aplicável
    'pagina':  str,          # nome da página destino para navegação
}
```

---

## Abas do módulo

| Aba | Conteúdo |
|-----|----------|
| 🔔 Todos (N) | Lista todos os alertas + filtros por nível e módulo + gráficos de distribuição |
| 💰 Financeiro (N) | Alertas do módulo financeiro + link direto para a página |
| 📈 Comercial (N) | Alertas do módulo comercial + link direto |
| 📦 Estoque (N) | Alertas do módulo estoque + link direto |
| 🛒 Compras (N) | Alertas do módulo compras + link direto |
| ⚙️ Configurações | Tabela de todos os thresholds + descrição dos níveis |

---

## Thresholds (CFG) e como ajustar

O dicionário `CFG` em `core/domain/alertas.py` centraliza todos os thresholds:

```python
CFG = {
    "piso_caixa":               50_000,   # R$ mínimo de caixa projetado 7d
    "capital_minimo":           100_000,  # R$ capital operacional mínimo
    "ap_horas_urgente":         48,       # horas para AP urgente
    "ar_dias_critico":          90,       # dias de atraso crítico (AR)
    "ar_vencido_pct":           80,       # % vencido do AR para urgente
    "pmr_atencao":              30,       # dias PMR para atenção
    "saldo_defasagem_dias":     3,        # dias sem atualizar saldo bancário
    "clientes_sem_comprar_dias": 60,      # inatividade de cliente
    "clientes_queda_pct":       40,       # % queda de compras do cliente
    "concentracao_top3_pct":    60,       # % concentração top 3 clientes
    "parado_dias":              90,       # dias para estoque parado
    "parado_valor_min":         20_000,   # valor mínimo para alertar parado
    "sem_venda_dias":           90,       # dias sem venda para alertar
    "sem_venda_valor_min":      10_000,   # valor mínimo sem venda
    "dep_fornec_top1_pct":      30,       # % top 1 fornecedor
    "dep_fornec_top3_pct":      60,       # % top 3 fornecedores
    "sem_giro_valor_min":       50_000,   # valor comprado sem venda
    "parado_forn_valor_min":    20_000,   # valor parado por fornecedor
}
```

Para adicionar novo alerta: criar uma entrada na função do módulo correspondente e seguir o padrão `_a(nivel, modulo, icone, titulo, detalhe, valor, pagina)`.

---

## Dados reais (2026-06-12)

| Módulo | Alertas | Destaques |
|--------|---------|-----------|
| Financeiro | 3 | 467 AP vencidos em aberto, 45 clientes AR críticos >90d |
| Comercial | 2 | 135 clientes sem comprar >60d, 20 em queda ≥40% |
| Estoque | 2 | 432 SKUs parados R$140k, 419 produtos sem venda registrada |
| Compras | 2 | 877 comprados sem giro, R$245k parado em 51 fornecedores |

---

## Decisões técnicas

### Tratamento de exceções por módulo

Cada função `alertas_X()` tem try/except no nível externo. Se um módulo falhar completamente
(ex.: banco indisponível), os alertas desse módulo são omitidos sem travar os demais.
Cada sub-alerta também tem seu try/except para isolamento granular.

### Cache de 5 minutos

`@st.cache_data(ttl=300)` na função `_carregar_alertas`. O TTL é mais curto que os demais
módulos (900-1800s) porque alertas têm natureza urgente — dados muito velhos podem levar
a ações tardias ou desnecessárias.

### Escopo do período

- **Financeiro, Estoque:** usam dados atuais (sem filtro de período) — refletem o estado agora
- **Compras:** usa o período filtrado na sidebar — comprados sem giro depende do contexto temporal

---

## Observações para próximas sessões

1. **Notificações push:** implementar envio de email/WhatsApp quando alertas críticos surgem.
   Candidato para Fase 7 (polimento).

2. **Histórico de alertas:** salvar em DuckDB os alertas gerados por data para ver evolução.
   Permite responder "o alerta de caixa negativo acontece com frequência?".

3. **Silenciar alertas:** permitir que o usuário "snooze" um alerta específico por N dias,
   salvando em DuckDB. Útil para alertas conhecidos e em tratamento.

4. **Próximo módulo:** Fase 6 — Tela Inicial (home personalizável com favoritos).
