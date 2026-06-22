"""
Script de investigação histórico (não faz parte do app em execução).
A lógica final e validada de decodificação de NUMDOCORIG está em
core/domain/financeiro.py (_numdocorig_to_numnf, get_itens_nf, get_itens_av).
Rodar a partir da raiz do projeto: python scripts/dev/inspecionar.py
"""
import sys
sys.path.insert(0, '.')
from core.data.firebird import fb_query

# Hipotese: NUMDOCORIG = 'VP' + NUMNF(8 digitos) + '01'
# Ex: VP0001047201 = VP + 00010472 + 01  -> NF 10472

print("=== Verificando padrao NUMDOCORIG -> NUMNF ===")
df = fb_query("""
SELECT FIRST 10
    TRIM(d.CODDOCTO)   AS CODDOCTO,
    TRIM(d.NUMDOCORIG) AS NUMDOCORIG,
    CAST(SUBSTRING(d.NUMDOCORIG FROM 3 FOR 8) AS INTEGER) AS NUMNF_EXTRAIDO,
    n.NUMNF,
    n.TOTALNF,
    n.CODPEDIDO
FROM DOCUREC d
LEFT JOIN NFSAIDC n ON TRIM(n.CODEMPRESA) = TRIM(d.CODEMPRESA)
                   AND CAST(n.NUMNF AS INTEGER) = CAST(SUBSTRING(d.NUMDOCORIG FROM 3 FOR 8) AS INTEGER)
WHERE TRIM(d.TIPODOCTO) = 'NF' AND d.SITUACAO = '1'
""")
print(df.to_string())

print("\n=== Produtos via NUMDOCORIG -> NFSAIDC -> NFSAIDI ===")
df2 = fb_query("""
SELECT FIRST 20
    TRIM(d.CODDOCTO)    AS TITULO,
    n.NUMNF,
    TRIM(i.CODPROD)     AS CODPROD,
    TRIM(p.DESCRICAO)   AS PRODUTO,
    i.QUANTIDADE,
    i.PRECOUNIT,
    COALESCE(i.DESCONTOVLR,0) AS DESCONTO,
    i.TOTALRATEADO      AS TOTAL
FROM DOCUREC d
JOIN NFSAIDC n ON TRIM(n.CODEMPRESA) = TRIM(d.CODEMPRESA)
              AND CAST(n.NUMNF AS INTEGER) = CAST(SUBSTRING(d.NUMDOCORIG FROM 3 FOR 8) AS INTEGER)
JOIN NFSAIDI i ON i.NUMNF = n.NUMNF
              AND TRIM(i.CODEMPRESA) = TRIM(n.CODEMPRESA)
LEFT JOIN PRODUTO p ON TRIM(p.CODPROD) = TRIM(i.CODPROD)
WHERE TRIM(d.TIPODOCTO) = 'NF' AND d.SITUACAO = '1'
ORDER BY d.CODDOCTO, i.CODPROD
""")
print(df2.to_string())

# Checar titulos AV - link diferente?
print("\n=== AV - tentativa via NUMORD -> ENCEFAT -> PEDIDOC ===")
df3 = fb_query("""
SELECT FIRST 5
    TRIM(d.TIPODOCTO) AS TIPO,
    TRIM(d.CODDOCTO)  AS DOCTO,
    TRIM(d.NUMDOCORIG) AS ORIG,
    d.NUMORD,
    e.CODPEDIDO, e.TIPOPEDIDO
FROM DOCUREC d
LEFT JOIN ENCEFAT e ON e.NUMORD = d.NUMORD
                   AND TRIM(e.CODEMPRESA) = TRIM(d.CODEMPRESA)
WHERE TRIM(d.TIPODOCTO) = 'AV' AND d.SITUACAO = '1'
""")
print(df3.to_string())
