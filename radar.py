import os
import re
import json
import html
import requests
from datetime import datetime, timezone
from urllib.parse import quote
from bs4 import BeautifulSoup

TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

SEARCHES = [
    "apartamento venda Armação Penha SC",
    "casa venda Armação Penha SC",
    "terreno venda Armação Penha SC",
]

HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

HEADERS_SUPABASE = {
    "apikey": SUPABASE_SECRET_KEY,
    "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    "Content-Type": "application/json"
}


# =========================================================
# TAVILY
# =========================================================

def pesquisar_tavily(query):

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 10,
            "include_answer": False
        },
        timeout=60
    )

    response.raise_for_status()

    return response.json().get("results", [])


# =========================================================
# LIMPEZA
# =========================================================

def limpar_texto(texto):

    if not texto:
        return ""

    texto = html.unescape(str(texto))
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def numero(valor):

    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor)

    texto = texto.replace("R$", "")
    texto = texto.replace("m²", "")
    texto = texto.replace("m2", "")
    texto = texto.strip()

    # Ex.: 650.000
    if "." in texto and "," not in texto:
        partes = texto.split(".")

        if len(partes[-1]) == 3:
            texto = texto.replace(".", "")

    # Ex.: 650.000,50
    if "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


# =========================================================
# JSON-LD
# =========================================================

def extrair_json_ld(soup):

    dados = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        try:

            conteudo = script.string or script.get_text()

            if not conteudo:
                continue

            obj = json.loads(conteudo)

            if isinstance(obj, list):
                dados.extend(obj)

            elif isinstance(obj, dict):

                if "@graph" in obj:
                    dados.extend(obj["@graph"])

                else:
                    dados.append(obj)

        except Exception:
            continue

    return dados


def procurar_json_ld(dados):

    melhor = None

    for item in dados:

        if not isinstance(item, dict):
            continue

        tipo = item.get("@type", "")

        if isinstance(tipo, list):
            tipo = " ".join(tipo)

        tipo = str(tipo).lower()

        if any(
            palavra in tipo
            for palavra in [
                "product",
                "offer",
                "realestate",
                "residence",
                "house",
                "apartment",
                "singlefamilyresidence"
            ]
        ):
            melhor = item
            break

    return melhor


# =========================================================
# PREÇO
# =========================================================

def extrair_preco_json(item):

    if not item:
        return None

    offers = item.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if isinstance(offers, dict):

        valor = offers.get("price")

        valor = numero(valor)

        if valor and valor >= 30000:
            return valor

    valor = item.get("price")

    valor = numero(valor)

    if valor and valor >= 30000:
        return valor

    return None


def extrair_preco_texto(texto):

    padroes = [
        r"R\$\s*([\d\.]+(?:,\d{2})?)",
        r"R\$\s*([\d]+(?:[.,]\d+)?)\s*(?:mil)"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if not resultado:
            continue

        valor = resultado.group(1)

        if "mil" in resultado.group(0).lower():
            valor = numero(valor)

            if valor:
                valor *= 1000

        else:
            valor = numero(valor)

        if valor and 30000 <= valor <= 50000000:
            return valor

    return None


# =========================================================
# ÁREA
# =========================================================

def extrair_area_json(item):

    if not item:
        return None

    campos = [
        "floorSize",
        "size",
        "area",
        "floorArea"
    ]

    for campo in campos:

        valor = item.get(campo)

        if isinstance(valor, dict):
            valor = (
                valor.get("value")
                or valor.get("maxValue")
            )

        valor = numero(valor)

        if valor and 15 <= valor <= 5000:
            return valor

    return None


def extrair_area_texto(texto):

    padroes = [
        r"(\d+(?:[.,]\d+)?)\s*m²",
        r"(\d+(?:[.,]\d+)?)\s*m2",
        r"área[^0-9]{0,30}"
        r"(\d+(?:[.,]\d+)?)\s*m"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            valor = numero(
                resultado.group(1)
            )

            if valor and 15 <= valor <= 5000:
                return valor

    return None


# =========================================================
# QUARTOS
# =========================================================

def extrair_quartos_json(item):

    if not item:
        return None

    for campo in [
        "numberOfBedrooms",
        "numberOfRooms",
        "bedrooms"
    ]:

        valor = numero(item.get(campo))

        if valor and 1 <= valor <= 20:
            return int(valor)

    return None


def extrair_quartos_texto(texto):

    padroes = [
        r"(\d+)\s+quartos?",
        r"(\d+)\s+dormitórios?",
        r"(\d+)\s+dorms?"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            valor = int(resultado.group(1))

            if 1 <= valor <= 20:
                return valor

    return None


# =========================================================
# BANHEIROS
# =========================================================

def extrair_banheiros_json(item):

    if not item:
        return None

    for campo in [
        "numberOfBathrooms",
        "numberOfFullBathrooms",
        "bathrooms"
    ]:

        valor = numero(item.get(campo))

        if valor and 1 <= valor <= 20:
            return int(valor)

    return None


def extrair_banheiros_texto(texto):

    padroes = [
        r"(\d+)\s+banheiros?",
        r"(\d+)\s+bwc",
        r"(\d+)\s+wc"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            valor = int(resultado.group(1))

            if 1 <= valor <= 20:
                return valor

    return None


# =========================================================
# GARAGEM
# =========================================================

def extrair_garagens_json(item):

    if not item:
        return None

    for campo in [
        "numberOfParkingSpaces",
        "parkingSpaces",
        "numberOfParkingSpaces"
    ]:

        valor = item.get(campo)

        if isinstance(valor, dict):
            valor = (
                valor.get("value")
                or valor.get("number")
            )

        valor = numero(valor)

        if valor and 1 <= valor <= 20:
            return int(valor)

    return None


def extrair_garagens_texto(texto):

    padroes = [
        r"(\d+)\s+vagas?",
        r"(\d+)\s+garagens?",
        r"(\d+)\s+vaga de garagem"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            valor = int(resultado.group(1))

            if 1 <= valor <= 20:
                return valor

    return None


# =========================================================
# TIPO
# =========================================================

def extrair_tipo(titulo, texto):

    texto_completo = (
        f"{titulo} {texto}"
    ).lower()

    if "apartamento" in texto_completo:
        return "Apartamento"

    if "sobrado" in texto_completo:
        return "Sobrado"

    if "casa" in texto_completo:
        return "Casa"

    if (
        "terreno" in texto_completo
        or "lote" in texto_completo
    ):
        return "Terreno"

    return None


# =========================================================
# PÁGINAS GENÉRICAS
# =========================================================

def pagina_generica(titulo):

    if not titulo:
        return True

    titulo = titulo.lower()

    padroes = [
        r"^\d+\s+imóveis?",
        r"^\d+\s+casas?",
        r"^\d+\s+apartamentos?",
        r"^\d+\s+terrenos?",
        r"^\d+\s+lotes?",
        r"imóveis para venda",
        r"imóveis à venda",
        r"casas à venda",
        r"apartamentos à venda",
        r"terrenos à venda",
        r"lotes à venda",
        r"página\s+\d+"
    ]

    return any(
        re.search(p, titulo)
        for p in padroes
    )


# =========================================================
# ABRIR PÁGINA
# =========================================================

def abrir_pagina(url):

    try:

        resposta = requests.get(
            url,
            headers=HEADERS_WEB,
            timeout=20
        )

        if resposta.status_code != 200:
            return None

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        texto = limpar_texto(
            soup.get_text(" ")
        )

        return soup, texto

    except Exception as erro:

        print(
            f"    Não abriu página: {erro}"
        )

        return None


# =========================================================
# EXISTENTE
# =========================================================

def buscar_existente(url):

    filtro = quote(
        url,
        safe=""
    )

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/imoveis"
        f"?url=eq.{filtro}&select=id"
    )

    resposta = requests.get(
        endpoint,
        headers=HEADERS_SUPABASE,
        timeout=30
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if dados:
        return dados[0]["id"]

    return None


# =========================================================
# SALVAR
# =========================================================

def salvar_imovel(imovel):

    existente = buscar_existente(
        imovel["url"]
    )

    if existente:

        endpoint = (
            f"{SUPABASE_URL}/rest/v1/imoveis"
            f"?id=eq.{existente}"
        )

        resposta = requests.patch(
            endpoint,
            json=imovel,
            headers=HEADERS_SUPABASE,
            timeout=30
        )

    else:

        endpoint = (
            f"{SUPABASE_URL}/rest/v1/imoveis"
        )

        resposta = requests.post(
            endpoint,
            json=imovel,
            headers={
                **HEADERS_SUPABASE,
                "Prefer": "return=minimal"
            },
            timeout=30
        )

    resposta.raise_for_status()


# =========================================================
# PROCESSAR
# =========================================================

def processar_resultado(resultado):

    url = resultado.get("url")
    titulo = resultado.get("title") or ""
    resumo = resultado.get("content") or ""

    if not url:
        return None

    if pagina_generica(titulo):

        print(
            f"    IGNORADA — página genérica: {titulo}"
        )

        return None

    print(
        f"\n  Analisando: {titulo}"
    )

    pagina = abrir_pagina(url)

    soup = None
    texto_pagina = ""

    if pagina:

        soup, texto_pagina = pagina

    texto = limpar_texto(
        f"{titulo} {resumo} {texto_pagina}"
    )

    # -------------------------
    # JSON-LD
    # -------------------------

    json_item = None

    if soup:

        dados_ld = extrair_json_ld(
            soup
        )

        json_item = procurar_json_ld(
            dados_ld
        )

    # -------------------------
    # EXTRAÇÃO
    # -------------------------

    preco = (
        extrair_preco_json(json_item)
        or extrair_preco_texto(texto)
    )

    area = (
        extrair_area_json(json_item)
        or extrair_area_texto(texto)
    )

    quartos = (
        extrair_quartos_json(json_item)
        or extrair_quartos_texto(texto)
    )

    banheiros = (
        extrair_banheiros_json(json_item)
        or extrair_banheiros_texto(texto)
    )

    garagens = (
        extrair_garagens_json(json_item)
        or extrair_garagens_texto(texto)
    )

    tipo = extrair_tipo(
        titulo,
        texto
    )

    # =====================================================
    # VALIDAÇÕES
    # =====================================================

    if tipo == "Terreno":

        quartos = None
        banheiros = None
        garagens = None

    if tipo in [
        "Apartamento",
        "Casa",
        "Sobrado"
    ]:

        if area and area > 2000:
            area = None

    # Evita valores absurdos
    if preco and (
        preco < 30000
        or preco > 50000000
    ):
        preco = None

    agora = datetime.now(
        timezone.utc
    ).isoformat()

    imovel = {

        "url": url,

        "fonte": "Tavily",

        "titulo": titulo[:500],

        "tipo": tipo,

        "preco": preco,

        "area_m2": area,

        "quartos": quartos,

        "banheiros": banheiros,

        "garagens": garagens,

        "bairro": "Armação",

        "descricao": (
            resumo[:5000]
            if resumo
            else texto[:5000]
        ),

        "atualizado_em": agora
    }

    print(
        f"    Tipo: {tipo}"
    )

    print(
        f"    Preço: {preco}"
    )

    print(
        f"    Área: {area}"
    )

    print(
        f"    Quartos: {quartos}"
    )

    print(
        f"    Banheiros: {banheiros}"
    )

    print(
        f"    Garagens: {garagens}"
    )

    return imovel


# =========================================================
# MAIN
# =========================================================

def main():

    encontrados = 0
    processados = 0
    ignorados = 0

    urls_processadas = set()

    for busca in SEARCHES:

        print("\n" + "=" * 70)

        print(
            f"PESQUISANDO: {busca}"
        )

        print("=" * 70)

        try:

            resultados = pesquisar_tavily(
                busca
            )

        except Exception as erro:

            print(
                f"Erro Tavily: {erro}"
            )

            continue

        print(
            f"Resultados: {len(resultados)}"
        )

        for resultado in resultados:

            encontrados += 1

            url = resultado.get("url")

            if not url:
                continue

            if url in urls_processadas:
                continue

            urls_processadas.add(url)

            try:

                imovel = processar_resultado(
                    resultado
                )

                if not imovel:

                    ignorados += 1
                    continue

                salvar_imovel(
                    imovel
                )

                processados += 1

                print(
                    "    ✓ Salvo/atualizado"
                )

            except Exception as erro:

                print(
                    f"    ✗ ERRO: {erro}"
                )

    print("\n" + "=" * 70)

    print("RADAR FINALIZADO")

    print(
        f"Resultados encontrados: {encontrados}"
    )

    print(
        f"Imóveis processados: {processados}"
    )

    print(
        f"Páginas ignoradas: {ignorados}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
