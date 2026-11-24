import os
import re
import unicodedata
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
cache_reputacao = {}

LOJAS_CONHECIDAS = {
    "amazon": {"nota": "8.4 / 10", "selo": "Ótimo (Verificada)", "confiavel": True},
    "magazine luiza": {"nota": "8.2 / 10", "selo": "RA1000 / Ótimo", "confiavel": True},
    "magalu": {"nota": "8.2 / 10", "selo": "RA1000 / Ótimo", "confiavel": True},
    "mercado livre": {"nota": "8.0 / 10", "selo": "Ótimo (Verificada)", "confiavel": True},
    "casas bahia": {"nota": "7.8 / 10", "selo": "Bom (Verificada)", "confiavel": True},
    "ponto": {"nota": "7.7 / 10", "selo": "Bom (Verificada)", "confiavel": True},
    "extra": {"nota": "7.6 / 10", "selo": "Bom (Verificada)", "confiavel": True},
    "kabum": {"nota": "8.6 / 10", "selo": "RA1000", "confiavel": True},
    "fast shop": {"nota": "8.5 / 10", "selo": "RA1000", "confiavel": True},
    "carrefour": {"nota": "7.4 / 10", "selo": "Bom (Verificada)", "confiavel": True},
    "electrolux": {"nota": "8.3 / 10", "selo": "Loja Oficial", "confiavel": True},
    "brastemp": {"nota": "8.1 / 10", "selo": "Loja Oficial", "confiavel": True},
    "consul": {"nota": "8.1 / 10", "selo": "Loja Oficial", "confiavel": True},
    "samsung": {"nota": "8.0 / 10", "selo": "Loja Oficial", "confiavel": True},
    "lg": {"nota": "8.2 / 10", "selo": "Loja Oficial", "confiavel": True},
}

PALAVRAS_BLOQUEADAS = [
    "ima ", "imas ", "ímã", "ímãs", "adesivo", "envelopamento", "capa ",
    "suporte", "borracha", "gaxeta", "prateleira", "gaveta", "termostato",
    "sensor", "placa ", "motor ", "compressor", "puxador", "dobradica",
    "dobradiça", "peca ", "peça ", "filtro ", "lampada", "lâmpada", "mini "
]

def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', texto.lower())
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def consultar_reclame_aqui(nome_loja: str):
    chave = nome_loja.lower().strip()
    if chave in cache_reputacao:
        return cache_reputacao[chave]

    for conhecida, dados in LOJAS_CONHECIDAS.items():
        if conhecida in chave:
            res = {**dados, "link_ra": f"https://www.reclameaqui.com.br/busca/?q={requests.utils.quote(nome_loja)}"}
            cache_reputacao[chave] = res
            return res

    try:
        params = {
            "engine": "google",
            "q": f'site:reclameaqui.com.br/empresa "{nome_loja}"',
            "gl": "br",
            "hl": "pt",
            "num": 2,
            "api_key": SERPAPI_KEY
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
        data = r.json()
        resultados = data.get("organic_results", [])

        if resultados:
            snippet = resultados[0].get("snippet", "") + " " + resultados[0].get("title", "")
            link_ra = resultados[0].get("link", f"https://www.reclameaqui.com.br/busca/?q={requests.utils.quote(nome_loja)}")

            match_nota = re.search(r'(\d+[.,]\d+)\s*/\s*10', snippet)
            nota = f"{match_nota.group(1).replace(',', '.')} / 10" if match_nota else "Sem nota definida"

            selo = "Regular / Verificar"
            confiavel = False
            snippet_lower = snippet.lower()
            if "ra1000" in snippet_lower:
                selo = "RA1000 (Excelente)"
                confiavel = True
            elif "ótimo" in snippet_lower or "otimo" in snippet_lower:
                selo = "Ótimo"
                confiavel = True
            elif "bom" in snippet_lower:
                selo = "Bom"
                confiavel = True
            elif "não recomendada" in snippet_lower or "nao recomendada" in snippet_lower:
                selo = "Não Recomendada"
                confiavel = False
            elif "ruim" in snippet_lower:
                selo = "Ruim"
                confiavel = False

            res = {"nota": nota, "selo": selo, "confiavel": confiavel, "link_ra": link_ra}
            cache_reputacao[chave] = res
            return res
    except Exception:
        pass

    res_fallback = {
        "nota": "Não encontrada",
        "selo": "Verificar manualmente",
        "confiavel": False,
        "link_ra": f"https://www.reclameaqui.com.br/busca/?q={requests.utils.quote(nome_loja)}"
    }
    cache_reputacao[chave] = res_fallback
    return res_fallback

def limpar_preco(preco_str):
    if not preco_str:
        return 999999.0
    numeros = re.sub(r'[^\d,]', '', preco_str).replace(',', '.')
    try:
        return float(numeros)
    except ValueError:
        return 999999.0

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/buscar")
def buscar_ofertas(
    produto: str = Query(...),
    marca: str = Query(""),
    modelo: str = Query(""),
    detalhes: str = Query(""),
    preco_min: float = Query(0.0)
):
    if not SERPAPI_KEY:
        return {"erro": "Chave SERPAPI_KEY não configurada no servidor."}

    # Monta a busca reforçando o produto principal entre aspas para evitar itens aleatórios
    partes = [f'"{produto.strip()}"']
    if marca.strip():
        partes.append(marca.strip())
    if modelo.strip():
        partes.append(modelo.strip())
    if detalhes.strip():
        partes.append(detalhes.strip())

    termo_busca = " ".join(partes)

    params = {
        "engine": "google_shopping",
        "q": termo_busca,
        "gl": "br",
        "hl": "pt",
        "currency": "BRL",
        "num": 40,
        "api_key": SERPAPI_KEY
    }

    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
        dados = resp.json()
    except Exception as e:
        return {"erro": f"Falha ao conectar na busca: {str(e)}"}

    itens_brutos = dados.get("shopping_results", [])
    ofertas = []

    palavra_chave_norm = normalizar(produto.strip().split()[0])
    marca_norm = normalizar(marca.strip()) if marca.strip() else ""

    for item in itens_brutos:
        titulo = item.get("title", "")
        titulo_norm = " " + normalizar(titulo) + " "

        # 1. Ignora resultados que não tenham a palavra principal do eletrodoméstico no título
        if palavra_chave_norm not in titulo_norm:
            continue

        # 2. Se o usuário informou marca, exige que a marca esteja no título
        if marca_norm and marca_norm not in titulo_norm:
            continue

        # 3. Ignora acessórios e peças (ímãs, adesivos, borrachas, etc.)
        if any(normalizar(bloq) in titulo_norm for bloq in PALAVRAS_BLOQUEADAS):
            continue

        preco_texto = item.get("price", "")
        valor_num = item.get("extracted_price") or limpar_preco(preco_texto)

        # 4. Aplica filtro de preço mínimo para eliminar acessórios baratos
        if not valor_num or valor_num >= 999999 or valor_num < preco_min:
            continue

        loja = item.get("source", "Loja desconhecida")
        link = item.get("link") or item.get("product_link", "#")
        imagem = item.get("thumbnail", "")

        ofertas.append({
            "titulo": titulo,
            "loja": loja,
            "preco_texto": preco_texto if preco_texto else f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "valor_num": float(valor_num),
            "link": link,
            "imagem": imagem
        })

    ofertas.sort(key=lambda x: x["valor_num"])

    top_ofertas = ofertas[:10]
    for oferta in top_ofertas:
        oferta["reputacao"] = consultar_reclame_aqui(oferta["loja"])

    return {"termo": termo_busca, "resultados": top_ofertas}
