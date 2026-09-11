import os
import re
import json
import html
import requests

from datetime import datetime, timezone
from urllib.parse import quote

from bs4 import BeautifulSoup


# =========================================================
# CONFIGURAÇÕES
# =========================================================

TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]


SEARCHES = [
    "apartamento venda Armação Penha SC",
    "casa venda Armação Penha SC",
    "terreno venda Armação Penha SC"
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
# LIMPAR TEXTO
# =========================================================

def limpar_texto(texto):

    if not texto:
        return ""

    texto = html.unescape(str(texto))

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# =========================================================
# CONVERTER NÚMERO
# =========================================================

def converter_numero(valor):

    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    texto = texto.replace("R$", "")
    texto = texto.replace("m²", "")
    texto = texto.replace("m2", "")
    texto = texto.strip()

    if not texto:
        return None

    try:

        if "," in texto:

            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")

        elif "." in texto:

            partes = texto.split(".")

            if len(partes[-1]) == 3:

                texto = texto.replace(".", "")

        return float(texto)

    except Exception:

        return None


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

            print(
                f"    Página retornou HTTP "
                f"{resposta.status_code}"
            )

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
            f"    Não foi possível abrir página: "
            f"{erro}"
        )

        return None


# =========================================================
# JSON-LD
# =========================================================

def obter_json_ld(soup):

    resultados = []

    if not soup:
        return resultados

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        try:

            conteudo = (
                script.string
                or script.get_text()
            )

            if not conteudo:
                continue

            objeto = json.loads(
                conteudo
            )

            if isinstance(objeto, list):

                resultados.extend(
                    objeto
                )

            elif isinstance(objeto, dict):

                if "@graph" in objeto:

                    grafico = objeto["@graph"]

                    if isinstance(
                        grafico,
                        list
                    ):

                        resultados.extend(
                            grafico
                        )

                else:

                    resultados.append(
                        objeto
                    )

        except Exception:

            continue

    return resultados


def encontrar_dados_imovel(json_ld):

    for item in json_ld:

        if not isinstance(
            item,
            dict
        ):
            continue

        tipo = item.get(
            "@type",
            ""
        )

        if isinstance(
            tipo,
            list
        ):

            tipo = " ".join(tipo)

        tipo = str(tipo).lower()

        tipos_validos = [
            "product",
            "offer",
            "realestate",
            "residence",
            "house",
            "apartment",
            "singlefamilyresidence"
        ]

        if any(
            palavra in tipo
            for palavra in tipos_validos
        ):

            return item

    return None


# =========================================================
# IDENTIFICAR TIPO
# =========================================================

def identificar_tipo(
    titulo,
    texto,
    url,
    busca
):

    titulo_lower = limpar_texto(
        titulo
    ).lower()

    url_lower = limpar_texto(
        url
    ).lower()

    busca_lower = limpar_texto(
        busca
    ).lower()


    # -----------------------------------------------------
    # 1. TÍTULO
    # -----------------------------------------------------

    if any(
        palavra in titulo_lower
        for palavra in [
            "terreno",
            "lote",
            "lotes"
        ]
    ):

        return "Terreno"


    if any(
        palavra in titulo_lower
        for palavra in [
            "apartamento",
            "apto",
            "cobertura",
            "flat"
        ]
    ):

        return "Apartamento"


    if any(
        palavra in titulo_lower
        for palavra in [
            "casa",
            "casas",
            "sobrado",
            "sobrados",
            "residência"
        ]
    ):

        return "Casa"


    # -----------------------------------------------------
    # 2. URL
    # -----------------------------------------------------

    if any(
        palavra in url_lower
        for palavra in [
            "/terreno",
            "/terrenos",
            "/lote",
            "/lotes"
        ]
    ):

        return "Terreno"


    if any(
        palavra in url_lower
        for palavra in [
            "/apartamento",
            "/apartamentos",
            "/apto",
            "/cobertura"
        ]
    ):

        return "Apartamento"


    if any(
        palavra in url_lower
        for palavra in [
            "/casa",
            "/casas",
            "/sobrado",
            "/sobrados"
        ]
    ):

        return "Casa"


    # -----------------------------------------------------
    # 3. CONSULTA TAVILY
    # -----------------------------------------------------

    if (
        "terreno" in busca_lower
        or "lote" in busca_lower
    ):

        return "Terreno"


    if "apartamento" in busca_lower:

        return "Apartamento"


    if "casa" in busca_lower:

        return "Casa"


    # -----------------------------------------------------
    # 4. TEXTO - ÚLTIMO RECURSO
    # -----------------------------------------------------

    texto_lower = texto.lower()


    if (
        "terreno" in texto_lower
        or "lote" in texto_lower
    ):

        return "Terreno"


    if "apartamento" in texto_lower:

        return "Apartamento"


    if "casa" in texto_lower:

        return "Casa"


    return None


# =========================================================
# PREÇO
# =========================================================

def extrair_preco_json(item):

    if not item:
        return None

    ofertas = item.get(
        "offers"
    )

    if isinstance(
        ofertas,
        list
    ):

        ofertas = (
            ofertas[0]
            if ofertas
            else None
        )


    if isinstance(
        ofertas,
        dict
    ):

        valor = converter_numero(
            ofertas.get("price")
        )

        if valor and (
            30000 <= valor <= 50000000
        ):

            return valor


    valor = converter_numero(
        item.get("price")
    )

    if valor and (
        30000 <= valor <= 50000000
    ):

        return valor


    return None


def extrair_preco_texto(texto):

    padroes = [

        r"R\$\s*([\d\.]+(?:,\d{1,2})?)",

        r"R\$\s*([\d]+(?:[.,]\d+)?)\s*mil"

    ]


    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            re.I
        )

        if not encontrado:
            continue


        valor = converter_numero(
            encontrado.group(1)
        )


        if (
            "mil"
            in encontrado.group(0).lower()
        ):

            if valor:
                valor *= 1000


        if valor and (
            30000 <= valor <= 50000000
        ):

            return valor


    return None


# =========================================================
# ÁREA
# =========================================================

def extrair_area_json(item):

    if not item:
        return None


    for campo in [
        "floorSize",
        "floorArea",
        "area",
        "size"
    ]:

        valor = item.get(
            campo
        )


        if isinstance(
            valor,
            dict
        ):

            valor = (
                valor.get("value")
                or valor.get("maxValue")
            )


        valor = converter_numero(
            valor
        )


        if valor and (
            15 <= valor <= 5000
        ):

            return valor


    return None


def extrair_area_texto(texto):

    padroes = [

        r"(\d+(?:[.,]\d+)?)\s*m²",

        r"(\d+(?:[.,]\d+)?)\s*m2"

    ]


    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            re.I
        )


        if encontrado:

            valor = converter_numero(
                encontrado.group(1)
            )


            if valor and (
                15 <= valor <= 5000
            ):

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

        valor = converter_numero(
            item.get(campo)
        )


        if valor and (
            1 <= valor <= 20
        ):

            return int(valor)


    return None


def extrair_quartos_texto(texto):

    padroes = [

        r"(\d+)\s+quartos?",

        r"(\d+)\s+dormitórios?",

        r"(\d+)\s+dorms?"

    ]


    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            re.I
        )


        if encontrado:

            valor = int(
                encontrado.group(1)
            )


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

        valor = converter_numero(
            item.get(campo)
        )


        if valor and (
            1 <= valor <= 20
        ):

            return int(valor)


    return None


def extrair_banheiros_texto(texto):

    padroes = [

        r"(\d+)\s+banheiros?",

        r"(\d+)\s+bwc",

        r"(\d+)\s+wc"

    ]


    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            re.I
        )


        if encontrado:

            valor = int(
                encontrado.group(1)
            )


            if 1 <= valor <= 20:

                return valor


    return None


# =========================================================
# GARAGENS
# =========================================================

def extrair_garagens_json(item):

    if not item:
        return None


    for campo in [
        "numberOfParkingSpaces",
        "parkingSpaces"
    ]:

        valor = item.get(
            campo
        )


        if isinstance(
            valor,
            dict
        ):

            valor = (
                valor.get("value")
                or valor.get("number")
            )


        valor = converter_numero(
            valor
        )


        if valor and (
            1 <= valor <= 20
        ):

            return int(valor)


    return None


def extrair_garagens_texto(texto):

    padroes = [

        r"(\d+)\s+vagas?",

        r"(\d+)\s+garagens?",

        r"(\d+)\s+vaga de garagem"

    ]


    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            re.I
        )


        if encontrado:

            valor = int(
                encontrado.group(1)
            )


            if 1 <= valor <= 20:

                return valor


    return None


# =========================================================
# PÁGINA GENÉRICA
# =========================================================

def pagina_generica(
    titulo,
    url
):

    titulo_lower = limpar_texto(
        titulo
    ).lower()

    url_lower = limpar_texto(
        url
    ).lower()


    # Redes sociais

    redes = [
        "instagram.com",
        "facebook.com",
        "youtube.com",
        "tiktok.com"
    ]


    if any(
        rede in url_lower
        for rede in redes
    ):

        return True


    # Páginas de busca/listagem

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

        r"página\s+\d+",

        r"imóveis encontrados",

        r"apartamentos e pousadas à venda",

        r"lotes e terrenos para venda",

        r"terrenos, lotes e condomínios"

    ]


    for padrao in padroes:

        if re.search(
            padrao,
            titulo_lower
        ):

            return True


    return False


# =========================================================
# VALIDAR DADOS
# =========================================================

def validar_dados(
    tipo,
    preco,
    area,
    quartos,
    banheiros,
    garagens
):

    # -----------------------------------------------------
    # TERRENO
    # -----------------------------------------------------

    if tipo == "Terreno":

        quartos = None
        banheiros = None
        garagens = None


    # -----------------------------------------------------
    # ÁREA
    # -----------------------------------------------------

    if area:

        if (
            tipo in [
                "Apartamento",
                "Casa",
                "Sobrado"
            ]
            and area > 1500
        ):

            area = None


    # -----------------------------------------------------
    # QUARTOS
    # -----------------------------------------------------

    if quartos:

        if not (
            1 <= quartos <= 20
        ):

            quartos = None


    # -----------------------------------------------------
    # BANHEIROS
    # -----------------------------------------------------

    if banheiros:

        if not (
            1 <= banheiros <= 20
        ):

            banheiros = None


    # -----------------------------------------------------
    # GARAGENS
    # -----------------------------------------------------

    if garagens:

        if not (
            1 <= garagens <= 20
        ):

            garagens = None


    # -----------------------------------------------------
    # PREÇO
    # -----------------------------------------------------

    if preco:

        if not (
            30000 <= preco <= 50000000
        ):

            preco = None


    return (
        preco,
        area,
        quartos,
        banheiros,
        garagens
    )


# =========================================================
# BUSCAR IMÓVEL EXISTENTE
# =========================================================

def buscar_existente(url):

    filtro = quote(
        url,
        safe=""
    )


    endpoint = (
        f"{SUPABASE_URL}/rest/v1/imoveis"
        f"?url=eq.{filtro}"
        f"&select=id"
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
# PROCESSAR RESULTADO
# =========================================================

def processar_resultado(
    resultado,
    busca
):

    url = resultado.get(
        "url"
    )

    titulo = resultado.get(
        "title"
    ) or ""

    resumo = resultado.get(
        "content"
    ) or ""


    if not url:

        return None


    # -----------------------------------------------------
    # IGNORAR PÁGINAS GENÉRICAS
    # -----------------------------------------------------

    if pagina_generica(
        titulo,
        url
    ):

        print(
            f"    IGNORADA: {titulo}"
        )

        return None


    print(
        f"\n    Analisando: {titulo}"
    )


    # -----------------------------------------------------
    # ABRIR PÁGINA
    # -----------------------------------------------------

    pagina = abrir_pagina(
        url
    )


    soup = None
    texto_pagina = ""


    if pagina:

        soup, texto_pagina = pagina


    texto = limpar_texto(
        f"{titulo} "
        f"{resumo} "
        f"{texto_pagina}"
    )


    # -----------------------------------------------------
    # TIPO
    # -----------------------------------------------------

    tipo = identificar_tipo(
        titulo,
        texto,
        url,
        busca
    )


    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------

    json_item = None


    if soup:

        json_ld = obter_json_ld(
            soup
        )

        json_item = encontrar_dados_imovel(
            json_ld
        )


    # -----------------------------------------------------
    # EXTRAIR DADOS
    # -----------------------------------------------------

    preco = (
        extrair_preco_json(
            json_item
        )
        or
        extrair_preco_texto(
            texto
        )
    )


    area = (
        extrair_area_json(
            json_item
        )
        or
        extrair_area_texto(
            texto
        )
    )


    quartos = (
        extrair_quartos_json(
            json_item
        )
        or
        extrair_quartos_texto(
            texto
        )
    )


    banheiros = (
        extrair_banheiros_json(
            json_item
        )
        or
        extrair_banheiros_texto(
            texto
        )
    )


    garagens = (
        extrair_garagens_json(
            json_item
        )
        or
        extrair_garagens_texto(
            texto
        )
    )


    # -----------------------------------------------------
    # VALIDAR
    # -----------------------------------------------------

    (
        preco,
        area,
        quartos,
        banheiros,
        garagens
    ) = validar_dados(
        tipo,
        preco,
        area,
        quartos,
        banheiros,
        garagens
    )


    # -----------------------------------------------------
    # SE NÃO TEM NENHUM DADO
    # -----------------------------------------------------

    if (
        preco is None
        and area is None
        and quartos is None
        and banheiros is None
        and garagens is None
    ):

        print(
            "    IGNORADO: "
            "nenhum dado imobiliário confiável"
        )

        return None


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

        "descricao": resumo[:5000],

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
# PRINCIPAL
# =========================================================

def main():

    encontrados = 0
    salvos = 0
    ignorados = 0

    urls_processadas = set()


    for busca in SEARCHES:

        print(
            "\n" + "=" * 70
        )

        print(
            f"PESQUISANDO: {busca}"
        )

        print(
            "=" * 70
        )


        try:

            resultados = pesquisar_tavily(
                busca
            )


            print(
                f"Resultados encontrados: "
                f"{len(resultados)}"
            )


        except Exception as erro:

            print(
                f"Erro Tavily: {erro}"
            )

            continue


        for resultado in resultados:

            encontrados += 1


            url = resultado.get(
                "url"
            )


            if not url:
                continue


            if url in urls_processadas:
                continue


            urls_processadas.add(
                url
            )


            try:

                imovel = processar_resultado(
                    resultado,
                    busca
                )


                if not imovel:

                    ignorados += 1

                    continue


                salvar_imovel(
                    imovel
                )


                salvos += 1


                print(
                    "    ✓ Salvo/atualizado"
                )


            except Exception as erro:

                print(
                    f"    ✗ ERRO: {erro}"
                )


    print(
        "\n" + "=" * 70
    )

    print(
        "RADAR FINALIZADO"
    )

    print(
        f"Resultados analisados: "
        f"{encontrados}"
    )

    print(
        f"Imóveis salvos/atualizados: "
        f"{salvos}"
    )

    print(
        f"Ignorados: "
        f"{ignorados}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":

    main()
