import os
import re
import html
import requests
from datetime import datetime, timezone
from urllib.parse import quote

TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

SEARCHES = [
    'apartamento venda Armação Penha SC R$',
    'casa venda Armação Penha SC R$',
    'terreno venda Armação Penha SC R$',
    'apartamento Armação Penha SC quartos m²',
    'casa Armação Penha SC quartos m²',
    'terreno Armação Penha SC m²'
]

HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}

HEADERS_SUPABASE = {
    "apikey": SUPABASE_SECRET_KEY,
    "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    "Content-Type": "application/json"
}


# ---------------------------------------------------------
# TAVILY
# ---------------------------------------------------------

def pesquisar_tavily(query):

    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 10,
        "include_answer": False
    }

    response = requests.post(
        url,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    return response.json().get("results", [])


# ---------------------------------------------------------
# LIMPEZA DO HTML
# ---------------------------------------------------------

def limpar_html(texto):

    if not texto:
        return ""

    texto = re.sub(
        r"<script.*?</script>",
        " ",
        texto,
        flags=re.I | re.S
    )

    texto = re.sub(
        r"<style.*?</style>",
        " ",
        texto,
        flags=re.I | re.S
    )

    texto = re.sub(
        r"<[^>]+>",
        " ",
        texto
    )

    texto = html.unescape(texto)

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ---------------------------------------------------------
# ABRIR PÁGINA DO ANÚNCIO
# ---------------------------------------------------------

def obter_conteudo_pagina(url):

    try:

        resposta = requests.get(
            url,
            headers=HEADERS_WEB,
            timeout=20
        )

        if resposta.status_code != 200:
            return ""

        return limpar_html(resposta.text)

    except Exception as erro:

        print(f"Não foi possível abrir página: {erro}")

        return ""


# ---------------------------------------------------------
# PREÇO
# ---------------------------------------------------------

def extrair_preco(texto):

    padroes = [
        r"R\$\s*([\d\.\,]+)\s*(mil|k)?",
        r"R\$\s*([\d\.\,]+)"
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

        multiplicador = 1

        if len(resultado.groups()) >= 2:
            unidade = resultado.group(2)

            if unidade:
                multiplicador = 1000

        try:

            if "," in valor:

                valor = valor.replace(".", "")
                valor = valor.replace(",", ".")

            else:

                valor = valor.replace(".", "")

            numero = float(valor) * multiplicador

            if numero >= 50000:

                return numero

        except Exception:
            pass

    return None


# ---------------------------------------------------------
# ÁREA
# ---------------------------------------------------------

def extrair_area(texto):

    padroes = [
        r"(\d+(?:[\.,]\d+)?)\s*m²",
        r"(\d+(?:[\.,]\d+)?)\s*m2",
        r"área(?:\s+(?:privativa|total|útil))?[^0-9]{0,20}"
        r"(\d+(?:[\.,]\d+)?)\s*m"
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            try:

                valor = resultado.group(1)
                valor = valor.replace(",", ".")

                area = float(valor)

                if 15 <= area <= 5000:
                    return area

            except Exception:
                pass

    return None


# ---------------------------------------------------------
# QUARTOS
# ---------------------------------------------------------

def extrair_quartos(texto):

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

            try:
                valor = int(resultado.group(1))

                if 1 <= valor <= 20:
                    return valor

            except Exception:
                pass

    return None


# ---------------------------------------------------------
# BANHEIROS
# ---------------------------------------------------------

def extrair_banheiros(texto):

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

            try:
                valor = int(resultado.group(1))

                if 1 <= valor <= 20:
                    return valor

            except Exception:
                pass

    return None


# ---------------------------------------------------------
# GARAGENS
# ---------------------------------------------------------

def extrair_garagens(texto):

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

            try:
                valor = int(resultado.group(1))

                if 1 <= valor <= 20:
                    return valor

            except Exception:
                pass

    return None


# ---------------------------------------------------------
# TIPO DO IMÓVEL
# ---------------------------------------------------------

def extrair_tipo(texto):

    texto_lower = texto.lower()

    if "apartamento" in texto_lower:
        return "Apartamento"

    if "casa" in texto_lower:
        return "Casa"

    if "sobrado" in texto_lower:
        return "Sobrado"

    if "terreno" in texto_lower or "lote" in texto_lower:
        return "Terreno"

    return None


# ---------------------------------------------------------
# IDENTIFICAR PÁGINA GENÉRICA
# ---------------------------------------------------------

def pagina_generica(titulo):

    if not titulo:
        return False

    titulo = titulo.lower()

    padroes = [
        r"^\d+\s+imóveis?\s",
        r"^\d+\s+casas?\s",
        r"^\d+\s+apartamentos?\s",
        r"^\d+\s+terrenos?\s",
        r"^\d+\s+lotes?\s",
        r"imóveis para venda",
        r"imóveis à venda",
        r"casas à venda",
        r"apartamentos à venda",
        r"terrenos à venda",
        r"lotes à venda"
    ]

    for padrao in padroes:

        if re.search(padrao, titulo):
            return True

    return False


# ---------------------------------------------------------
# BUSCAR IMÓVEL EXISTENTE
# ---------------------------------------------------------

def buscar_existente(url):

    filtro = quote(url, safe="")

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


# ---------------------------------------------------------
# SALVAR / ATUALIZAR
# ---------------------------------------------------------

def salvar_imovel(imovel):

    url = imovel["url"]

    existente = buscar_existente(url)

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

        endpoint = f"{SUPABASE_URL}/rest/v1/imoveis"

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


# ---------------------------------------------------------
# PROCESSAR RESULTADO
# ---------------------------------------------------------

def processar_resultado(resultado):

    url = resultado.get("url")

    titulo = resultado.get("title") or ""

    conteudo_tavily = resultado.get("content") or ""

    if not url:
        return None

    if pagina_generica(titulo):

        print(f"Página genérica ignorada: {titulo}")

        return None

    print(f"Analisando: {titulo}")

    conteudo_pagina = obter_conteudo_pagina(url)

    texto = f"{titulo} {conteudo_tavily} {conteudo_pagina}"

    texto = limpar_html(texto)

    preco = extrair_preco(texto)
    area = extrair_area(texto)
    quartos = extrair_quartos(texto)
    banheiros = extrair_banheiros(texto)
    garagens = extrair_garagens(texto)
    tipo = extrair_tipo(texto)

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
            conteudo_tavily[:5000]
            if conteudo_tavily
            else texto[:5000]
        ),

        "atualizado_em": agora

    }

    print(
        f"  Preço: {preco} | "
        f"Área: {area} | "
        f"Quartos: {quartos} | "
        f"Banheiros: {banheiros} | "
        f"Garagens: {garagens}"
    )

    return imovel


# ---------------------------------------------------------
# PRINCIPAL
# ---------------------------------------------------------

def main():

    encontrados = 0
    salvos = 0

    urls_processadas = set()

    for busca in SEARCHES:

        print("\n" + "=" * 70)

        print(f"PESQUISANDO: {busca}")

        print("=" * 70)

        try:

            resultados = pesquisar_tavily(busca)

            print(
                f"Resultados encontrados: "
                f"{len(resultados)}"
            )

        except Exception as erro:

            print(
                f"Erro na pesquisa Tavily: {erro}"
            )

            continue

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
                    continue

                salvar_imovel(imovel)

                salvos += 1

                print(
                    f"  ✓ Salvo/atualizado: "
                    f"{imovel['titulo']}"
                )

            except Exception as erro:

                print(
                    f"  ✗ Erro ao processar: "
                    f"{erro}"
                )

    print("\n" + "=" * 70)

    print("FINALIZADO")

    print(f"Resultados analisados: {encontrados}")

    print(f"Imóveis salvos/atualizados: {salvos}")

    print("=" * 70)


if __name__ == "__main__":
    main()
