import os
import re
import json
import requests

from bs4 import BeautifulSoup
from urllib.parse import urlparse


# ============================================================
# CONFIGURAÇÃO
# ============================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

SUPABASE_TABLE = "imoveis"


# ============================================================
# BUSCAS
# ============================================================

BUSCAS = [

    # --------------------------------------------------------
    # APARTAMENTOS
    # --------------------------------------------------------

    (
        "Apartamento",
        'apartamento venda "Armação" Penha SC',
        "zapimoveis.com.br"
    ),

    (
        "Apartamento",
        'apartamento venda "Armação" Penha SC',
        "vivareal.com.br"
    ),

    (
        "Apartamento",
        'apartamento venda "Armação" Penha SC',
        "olx.com.br"
    ),

    (
        "Apartamento",
        'apartamento venda "Armação" Penha SC',
        "imovelweb.com.br"
    ),


    # --------------------------------------------------------
    # CASAS
    # --------------------------------------------------------

    (
        "Casa",
        'casa venda "Armação" Penha SC',
        "zapimoveis.com.br"
    ),

    (
        "Casa",
        'casa venda "Armação" Penha SC',
        "vivareal.com.br"
    ),

    (
        "Casa",
        'casa venda "Armação" Penha SC',
        "olx.com.br"
    ),

    (
        "Casa",
        'casa venda "Armação" Penha SC',
        "imovelweb.com.br"
    ),


    # --------------------------------------------------------
    # TERRENOS
    # --------------------------------------------------------

    (
        "Terreno",
        'terreno lote venda "Armação" Penha SC',
        "zapimoveis.com.br"
    ),

    (
        "Terreno",
        'terreno lote venda "Armação" Penha SC',
        "vivareal.com.br"
    ),

    (
        "Terreno",
        'terreno lote venda "Armação" Penha SC',
        "olx.com.br"
    ),

    (
        "Terreno",
        'terreno lote venda "Armação" Penha SC',
        "imovelweb.com.br"
    ),
]


# ============================================================
# NORMALIZAÇÃO DE NÚMEROS
# ============================================================

def normalizar_numero(valor):

    if valor is None:
        return None

    try:

        valor = str(valor)

        valor = (
            valor
            .replace("R$", "")
            .replace("m²", "")
            .replace("m2", "")
            .strip()
        )

        # Exemplo:
        # 590.000,00
        # 590.000
        # 590000

        if "," in valor:

            valor = (
                valor
                .replace(".", "")
                .replace(",", ".")
            )

        else:

            if valor.count(".") == 1:

                partes = valor.split(".")

                if len(partes[1]) == 3:

                    valor = valor.replace(".", "")

        return float(valor)

    except:

        return None


# ============================================================
# EXTRAIR PREÇO
# ============================================================

def extrair_preco(texto):

    if not texto:
        return None

    padroes = [

        r'R\$\s*([\d\.]+(?:,\d{2})?)',

        r'R\$\s*([\d\.]+)',

    ]

    for padrao in padroes:

        m = re.search(
            padrao,
            texto,
            re.I
        )

        if m:

            valor = normalizar_numero(
                m.group(1)
            )

            if valor and 20_000 <= valor <= 20_000_000:

                return valor

    return None


# ============================================================
# EXTRAIR ÁREA
# ============================================================

def extrair_area(texto):

    if not texto:
        return None

    padroes = [

        r'(\d+(?:[\.,]\d+)?)\s*m²',

        r'(\d+(?:[\.,]\d+)?)\s*m2',

        r'área.{0,30}?(\d+(?:[\.,]\d+)?)',

    ]

    for padrao in padroes:

        m = re.search(
            padrao,
            texto,
            re.I
        )

        if m:

            valor = normalizar_numero(
                m.group(1)
            )

            if valor and 10 <= valor <= 10_000:

                return valor

    return None


# ============================================================
# EXTRAIR NÚMEROS
# ============================================================

def extrair_inteiro(texto, palavras):

    if not texto:
        return None

    for palavra in palavras:

        padroes = [

            rf'(\d+)\s*{palavra}',

            rf'{palavra}.{{0,15}}?(\d+)',

        ]

        for padrao in padroes:

            m = re.search(
                padrao,
                texto,
                re.I
            )

            if m:

                try:

                    valor = int(
                        m.group(1)
                    )

                    if 0 <= valor <= 10:

                        return valor

                except:

                    pass

    return None


# ============================================================
# QUARTOS
# ============================================================

def extrair_quartos(texto):

    return extrair_inteiro(
        texto,
        [
            r'quartos?',
            r'dormitórios?',
            r'dormitorios?',
            r'dorms?',
        ]
    )


# ============================================================
# BANHEIROS
# ============================================================

def extrair_banheiros(texto):

    return extrair_inteiro(
        texto,
        [
            r'banheiros?',
            r'bwc',
            r'suítes?',
            r'suites?',
        ]
    )


# ============================================================
# GARAGENS
# ============================================================

def extrair_garagens(texto):

    return extrair_inteiro(
        texto,
        [
            r'vagas?',
            r'garagens?',
        ]
    )


# ============================================================
# IDENTIFICAR FONTE
# ============================================================

def identificar_fonte(url):

    dominio = urlparse(
        url
    ).netloc.lower()

    if "zapimoveis" in dominio:

        return "ZAP Imóveis"

    if "vivareal" in dominio:

        return "Viva Real"

    if "olx" in dominio:

        return "OLX"

    if "imovelweb" in dominio:

        return "Imovelweb"

    return dominio


# ============================================================
# IDENTIFICAR TIPO
# ============================================================

def identificar_tipo(
    titulo,
    busca_tipo,
    texto=""
):

    titulo_lower = (
        titulo or ""
    ).lower()

    texto_lower = (
        texto or ""
    ).lower()


    # --------------------------------------------------------
    # PRIMEIRO: TÍTULO
    # --------------------------------------------------------

    if any(
        x in titulo_lower
        for x in [
            "terreno",
            "lote",
            "lotes"
        ]
    ):

        return "Terreno"


    if any(
        x in titulo_lower
        for x in [
            "apartamento",
            "apto",
            "cobertura",
            "flat"
        ]
    ):

        return "Apartamento"


    if any(
        x in titulo_lower
        for x in [
            "casa",
            "sobrado",
            "residência",
            "residencia"
        ]
    ):

        return "Casa"


    # --------------------------------------------------------
    # SEGUNDO: TIPO DA BUSCA
    # --------------------------------------------------------

    if busca_tipo in [
        "Apartamento",
        "Casa",
        "Terreno"
    ]:

        return busca_tipo


    return None


# ============================================================
# VERIFICAR PÁGINA GENÉRICA
# ============================================================

def pagina_generica(
    titulo,
    url
):

    titulo = (
        titulo or ""
    ).strip().lower()

    url_lower = (
        url or ""
    ).lower()


    # --------------------------------------------------------
    # TÍTULOS GENÉRICOS
    # --------------------------------------------------------

    padroes_titulo = [

        # Quantidade de imóveis
        r'^\d+\s+apartamentos?',
        r'^\d+\s+casas?',
        r'^\d+\s+terrenos?',
        r'^\d+\s+lotes?',

        # Categorias
        r'^apartamentos?\s+(à|a)\s+venda',
        r'^casas?\s+(à|a)\s+venda',
        r'^terrenos?\s+(à|a)\s+venda',
        r'^lotes?.*venda',

        r'^apartamentos?\s+para\s+venda',
        r'^casas?\s+para\s+venda',
        r'^terrenos?\s+para\s+venda',

        r'^apartamentos?\s+para\s+comprar',
        r'^casas?\s+para\s+comprar',

        # Imóveis
        r'imóveis?\s+à\s+venda',
        r'imoveis\s+à\s+venda',

        r'imóveis?\s+para\s+venda',
        r'imoveis\s+para\s+venda',

        # Penha geral
        r'^penha\s*-\s*sc$',

        # Resultados
        r'imóveis encontrados',
        r'imoveis encontrados',

        r'^resultados',

        # OLX
        r'^anúncios',
        r'^anuncios',

        r'^ofertas',

        r'^classificados',

        # Páginas
        r'^página\s+\d+',
        r'^pagina\s+\d+',

        # Terrenos
        r'lotes/terrenos\s+para\s+venda',
        r'terrenos,\s*lotes',

        # Outros
        r'apartamentos\s+e\s+pousadas',

    ]


    for padrao in padroes_titulo:

        if re.search(
            padrao,
            titulo
        ):

            return True


    # --------------------------------------------------------
    # "X imóveis à venda"
    # --------------------------------------------------------

    if re.search(
        r'^\d+\s+.*à\s+venda',
        titulo
    ):

        return True


    # --------------------------------------------------------
    # URLs DE PESQUISA
    # --------------------------------------------------------

    palavras_url = [

        "/busca",
        "/search",
        "/resultado",
        "/resultados",
        "/filtro",
        "/imoveis-a-venda",
        "/imoveis?",
        "/apartamentos?",
        "/casas?",
        "/terrenos?",
        "/lotes?",
        "/venda?",

    ]


    for palavra in palavras_url:

        if palavra in url_lower:

            if any(
                x in url_lower
                for x in [
                    "filtro",
                    "search",
                    "busca",
                    "result",
                    "pagina",
                    "page=",
                    "tipo=",
                ]
            ):

                return True


    return False


# ============================================================
# EXTRAIR JSON-LD
# ============================================================

def extrair_jsonld(soup):

    resultados = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        try:

            conteudo = script.string

            if not conteudo:
                continue

            dados = json.loads(
                conteudo
            )

            if isinstance(
                dados,
                list
            ):

                resultados.extend(
                    dados
                )

            else:

                resultados.append(
                    dados
                )

        except:

            continue

    return resultados


# ============================================================
# ANALISAR JSON-LD
# ============================================================

def analisar_jsonld(
    jsonlds
):

    dados = {}

    for item in jsonlds:

        if not isinstance(
            item,
            dict
        ):

            continue


        tipo = item.get(
            "@type",
            ""
        )


        # ----------------------------------------------------
        # PÁGINA DE CATEGORIA
        # ----------------------------------------------------

        if tipo in [
            "ItemList",
            "CollectionPage",
            "SearchResultsPage"
        ]:

            dados[
                "generica"
            ] = True

            continue


        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        nome = item.get(
            "name"
        )

        if nome and not dados.get(
            "titulo"
        ):

            dados[
                "titulo"
            ] = nome


        # ----------------------------------------------------
        # PREÇO
        # ----------------------------------------------------

        offers = item.get(
            "offers"
        )


        if isinstance(
            offers,
            dict
        ):

            preco = offers.get(
                "price"
            )

            if preco:

                dados[
                    "preco"
                ] = normalizar_numero(
                    preco
                )


        elif isinstance(
            offers,
            list
        ):

            for offer in offers:

                if isinstance(
                    offer,
                    dict
                ):

                    preco = offer.get(
                        "price"
                    )

                    if preco:

                        dados[
                            "preco"
                        ] = normalizar_numero(
                            preco
                        )

                        break


        # Alguns sites colocam preço direto

        if item.get(
            "price"
        ):

            dados[
                "preco"
            ] = normalizar_numero(
                item.get("price")
            )


        # ----------------------------------------------------
        # ÁREA
        # ----------------------------------------------------

        if item.get(
            "floorSize"
        ):

            fs = item[
                "floorSize"
            ]


            if isinstance(
                fs,
                dict
            ):

                valor = fs.get(
                    "value"
                )

            else:

                valor = fs


            dados[
                "area_m2"
            ] = normalizar_numero(
                valor
            )


        # ----------------------------------------------------
        # QUARTOS
        # ----------------------------------------------------

        for campo in [
            "numberOfBedrooms",
            "numberOfRooms"
        ]:

            if item.get(
                campo
            ) is not None:

                try:

                    dados[
                        "quartos"
                    ] = int(
                        item.get(
                            campo
                        )
                    )

                except:

                    pass


        # ----------------------------------------------------
        # BANHEIROS
        # ----------------------------------------------------

        if item.get(
            "numberOfBathroomsTotal"
        ) is not None:

            try:

                dados[
                    "banheiros"
                ] = int(
                    item.get(
                        "numberOfBathroomsTotal"
                    )
                )

            except:

                pass


        # ----------------------------------------------------
        # GARAGEM
        # ----------------------------------------------------

        if item.get(
            "numberOfParkingSpaces"
        ) is not None:

            try:

                dados[
                    "garagens"
                ] = int(
                    item.get(
                        "numberOfParkingSpaces"
                    )
                )

            except:

                pass


        # ----------------------------------------------------
        # ENDEREÇO
        # ----------------------------------------------------

        endereco = item.get(
            "address"
        )


        if isinstance(
            endereco,
            dict
        ):

            partes = []


            for campo in [
                "streetAddress",
                "addressLocality",
                "addressRegion"
            ]:

                if endereco.get(
                    campo
                ):

                    partes.append(
                        str(
                            endereco[campo]
                        )
                    )


            if partes:

                dados[
                    "endereco"
                ] = ", ".join(
                    partes
                )


    return dados


# ============================================================
# BAIXAR PÁGINA
# ============================================================

def baixar_pagina(url):

    try:

        headers = {

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"

        }


        resposta = requests.get(

            url,

            headers=headers,

            timeout=20,

            allow_redirects=True

        )


        if resposta.status_code >= 400:

            print(
                f"    Página retornou HTTP "
                f"{resposta.status_code}"
            )

            return None, None


        soup = BeautifulSoup(

            resposta.text,

            "html.parser"

        )


        return soup, resposta.text


    except Exception as e:

        print(
            f"    Erro ao acessar página: {e}"
        )

        return None, None


# ============================================================
# TAVILY
# ============================================================

def pesquisar_tavily(
    query,
    dominio
):

    try:

        response = requests.post(

            "https://api.tavily.com/search",

            json={

                "api_key":
                    TAVILY_API_KEY,

                "query":
                    query,

                "search_depth":
                    "basic",

                "max_results":
                    10,

                "include_answer":
                    False,

                "include_domains":
                    [dominio],

            },

            timeout=60

        )


        response.raise_for_status()


        return response.json().get(
            "results",
            []
        )


    except Exception as e:

        print(
            f"Erro Tavily: {e}"
        )

        return []


# ============================================================
# VALIDAR DADOS
# ============================================================

def validar_dados(
    dados,
    tipo
):

    preco = dados.get(
        "preco"
    )

    area = dados.get(
        "area_m2"
    )

    quartos = dados.get(
        "quartos"
    )

    banheiros = dados.get(
        "banheiros"
    )

    garagens = dados.get(
        "garagens"
    )


    # --------------------------------------------------------
    # TERRENO
    # --------------------------------------------------------

    if tipo == "Terreno":

        dados[
            "quartos"
        ] = None

        dados[
            "banheiros"
        ] = None

        dados[
            "garagens"
        ] = None


    # --------------------------------------------------------
    # ÁREA
    # --------------------------------------------------------

    if tipo in [
        "Apartamento",
        "Casa"
    ]:

        if area and area > 1500:

            dados[
                "area_m2"
            ] = None


    # --------------------------------------------------------
    # QUARTOS
    # --------------------------------------------------------

    if quartos is not None:

        if quartos < 0 or quartos > 10:

            dados[
                "quartos"
            ] = None


    # --------------------------------------------------------
    # BANHEIROS
    # --------------------------------------------------------

    if banheiros is not None:

        if banheiros < 0 or banheiros > 10:

            dados[
                "banheiros"
            ] = None


    # --------------------------------------------------------
    # GARAGENS
    # --------------------------------------------------------

    if garagens is not None:

        if garagens < 0 or garagens > 10:

            dados[
                "garagens"
            ] = None


    # --------------------------------------------------------
    # PREÇO
    # --------------------------------------------------------

    if preco is not None:

        if (
            preco < 20_000
            or preco > 20_000_000
        ):

            dados[
                "preco"
            ] = None


    # --------------------------------------------------------
    # ÁREA
    # --------------------------------------------------------

    if area is not None:

        if (
            area < 10
            or area > 10_000
        ):

            dados[
                "area_m2"
            ] = None


    return dados


# ============================================================
# CALCULAR QUALIDADE
# ============================================================

def calcular_qualidade(
    dados,
    veio_jsonld
):

    campos = [

        dados.get("preco"),

        dados.get("area_m2"),

        dados.get("quartos"),

        dados.get("banheiros"),

        dados.get("garagens"),

    ]


    preenchidos = sum(

        1
        for x in campos
        if x is not None

    )


    # JSON-LD + pelo menos 3 dados

    if (
        veio_jsonld
        and preenchidos >= 3
    ):

        return "alta"


    # Pelo menos 3 dados

    if preenchidos >= 3:

        return "media"


    # Pelo menos 1 dado

    if preenchidos >= 1:

        return "baixa"


    return None


# ============================================================
# PROCESSAR RESULTADO
# ============================================================

def processar_resultado(
    resultado,
    busca_tipo
):

    url = resultado.get(
        "url"
    )


    if not url:

        return None


    titulo_original = (
        resultado.get("title")
        or ""
    ).strip()


    resumo = (
        resultado.get("content")
        or ""
    ).strip()


    # --------------------------------------------------------
    # TÍTULO NÃO PODE SER URL
    # --------------------------------------------------------

    if (
        titulo_original.startswith(
            "http://"
        )
        or
        titulo_original.startswith(
            "https://"
        )
    ):

        titulo_original = ""


    # --------------------------------------------------------
    # PRIMEIRO FILTRO
    # --------------------------------------------------------

    if pagina_generica(
        titulo_original,
        url
    ):

        print(
            f"    IGNORADA: "
            f"{titulo_original or url}"
        )

        return None


    # --------------------------------------------------------
    # ABRIR PÁGINA
    # --------------------------------------------------------

    soup, html_text = baixar_pagina(
        url
    )


    dados = {}

    veio_jsonld = False

    titulo = titulo_original


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    if soup:

        jsonlds = extrair_jsonld(
            soup
        )


        jsondados = analisar_jsonld(
            jsonlds
        )


        # Página de categoria

        if jsondados.get(
            "generica"
        ):

            print(
                "    IGNORADA: "
                "página de categoria"
            )

            return None


        if jsondados:

            veio_jsonld = True


            dados.update({

                k: v

                for k, v in jsondados.items()

                if k != "generica"

            })


            if jsondados.get(
                "titulo"
            ):

                titulo = str(
                    jsondados["titulo"]
                ).strip()


    # --------------------------------------------------------
    # SEM TÍTULO
    # --------------------------------------------------------

    if not titulo:

        print(
            "    IGNORADA: "
            "sem título confiável"
        )

        return None


    # --------------------------------------------------------
    # SEGUNDO FILTRO
    # --------------------------------------------------------

    if pagina_generica(
        titulo,
        url
    ):

        print(
            f"    IGNORADA: {titulo}"
        )

        return None


    # --------------------------------------------------------
    # TEXTO PARA EXTRAÇÃO
    #
    # IMPORTANTE:
    # usamos somente título + snippet
    # para evitar pegar dados de vários imóveis
    # existentes na mesma página.
    # --------------------------------------------------------

    texto = (
        f"{titulo} {resumo}"
    )


    # --------------------------------------------------------
    # PREÇO
    # --------------------------------------------------------

    if dados.get(
        "preco"
    ) is None:

        dados[
            "preco"
        ] = extrair_preco(
            texto
        )


    # --------------------------------------------------------
    # ÁREA
    # --------------------------------------------------------

    if dados.get(
        "area_m2"
    ) is None:

        dados[
            "area_m2"
        ] = extrair_area(
            texto
        )


    # --------------------------------------------------------
    # QUARTOS
    # --------------------------------------------------------

    if dados.get(
        "quartos"
    ) is None:

        dados[
            "quartos"
        ] = extrair_quartos(
            texto
        )


    # --------------------------------------------------------
    # BANHEIROS
    # --------------------------------------------------------

    if dados.get(
        "banheiros"
    ) is None:

        dados[
            "banheiros"
        ] = extrair_banheiros(
            texto
        )


    # --------------------------------------------------------
    # GARAGENS
    # --------------------------------------------------------

    if dados.get(
        "garagens"
    ) is None:

        dados[
            "garagens"
        ] = extrair_garagens(
            texto
        )


    # --------------------------------------------------------
    # TIPO
    # --------------------------------------------------------

    tipo = identificar_tipo(

        titulo,

        busca_tipo,

        texto

    )


    if not tipo:

        print(
            "    IGNORADA: "
            "tipo não identificado"
        )

        return None


    titulo_lower = titulo.lower()


    # --------------------------------------------------------
    # NÃO ACEITAR TIPO ERRADO
    # --------------------------------------------------------

    if busca_tipo == "Terreno":

        if any(

            x in titulo_lower

            for x in [

                "apartamento",
                "apto",
                "casa",
                "sobrado",

            ]

        ):

            print(
                "    IGNORADA: "
                "tipo incompatível"
            )

            return None


    if busca_tipo == "Apartamento":

        if any(

            x in titulo_lower

            for x in [

                "terreno",
                "lote",
                "casa",
                "sobrado",

            ]

        ):

            print(
                "    IGNORADA: "
                "tipo incompatível"
            )

            return None


    if busca_tipo == "Casa":

        if any(

            x in titulo_lower

            for x in [

                "terreno",
                "lote",
                "apartamento",
                "apto",

            ]

        ):

            print(
                "    IGNORADA: "
                "tipo incompatível"
            )

            return None


    # --------------------------------------------------------
    # VALIDAÇÃO
    # --------------------------------------------------------

    dados = validar_dados(

        dados,

        tipo

    )


    # --------------------------------------------------------
    # QUALIDADE
    # --------------------------------------------------------

    qualidade = calcular_qualidade(

        dados,

        veio_jsonld

    )


    # --------------------------------------------------------
    # SEM PREÇO E SEM ÁREA
    # --------------------------------------------------------

    if (

        dados.get("preco") is None

        and

        dados.get("area_m2") is None

    ):

        print(
            "    IGNORADA: "
            "sem preço ou área"
        )

        return None


    # --------------------------------------------------------
    # BAIRRO
    # --------------------------------------------------------

    bairro = None

    texto_lower = texto.lower()


    if (
        "armação" in texto_lower
        or
        "armacao" in texto_lower
    ):

        bairro = "Armação"


    # --------------------------------------------------------
    # IMÓVEL FINAL
    # --------------------------------------------------------

    imovel = {

        "url":
            url,

        "fonte":
            identificar_fonte(url),

        "titulo":
            titulo[:500],

        "tipo":
            tipo,

        "preco":
            dados.get("preco"),

        "area_m2":
            dados.get("area_m2"),

        "quartos":
            dados.get("quartos"),

        "banheiros":
            dados.get("banheiros"),

        "garagens":
            dados.get("garagens"),

        "endereco":
            dados.get("endereco"),

        "bairro":
            bairro,

        "descricao":
            resumo[:3000],

        "qualidade_dados":
            qualidade,

        "ativo":
            True,

    }


    return imovel


# ============================================================
# HEADERS SUPABASE
# ============================================================

def headers_supabase():

    return {

        "apikey":
            SUPABASE_SECRET_KEY,

        "Authorization":
            f"Bearer {SUPABASE_SECRET_KEY}",

        "Content-Type":
            "application/json",

        "Prefer":
            "return=minimal",

    }


# ============================================================
# SALVAR IMÓVEL
# ============================================================

def salvar_imovel(
    imovel
):

    url_base = (

        SUPABASE_URL.rstrip("/")

        + "/rest/v1/"

        + SUPABASE_TABLE

    )


    headers = headers_supabase()


    # ========================================================
    # VERIFICAR SE URL JÁ EXISTE
    # ========================================================

    try:

        busca = requests.get(

            url_base,

            headers=headers,

            params={

                "url":
                    "eq." + imovel["url"],

                "select":
                    "id"

            },

            timeout=30

        )


        # ----------------------------------------------------
        # VERIFICAR ERRO HTTP
        # ----------------------------------------------------

        if busca.status_code >= 300:

            print(
                "    Erro consultando Supabase:",
                busca.status_code
            )

            print(
                "    Resposta:",
                busca.text[:1000]
            )

            return False


        # ----------------------------------------------------
        # CONVERTER JSON
        # ----------------------------------------------------

        existentes = busca.json()


        # ----------------------------------------------------
        # GARANTIR QUE É UMA LISTA
        # ----------------------------------------------------

        if not isinstance(
            existentes,
            list
        ):

            print(
                "    Resposta inesperada "
                "do Supabase:"
            )

            print(
                str(existentes)[:1000]
            )

            return False


    except Exception as e:

        print(
            f"    Erro verificando imóvel: {e}"
        )

        return False


    # ========================================================
    # ATUALIZAR IMÓVEL EXISTENTE
    # ========================================================

    if len(existentes) > 0:

        id_imovel = existentes[0].get(
            "id"
        )


        if not id_imovel:

            print(
                "    Imóvel encontrado, "
                "mas sem ID."
            )

            return False


        try:

            resposta = requests.patch(

                url_base,

                headers=headers,

                params={

                    "id":
                        f"eq.{id_imovel}"

                },

                json=imovel,

                timeout=30

            )


            if resposta.status_code >= 300:

                print(
                    "    Erro PATCH:",
                    resposta.status_code
                )

                print(
                    resposta.text[:1000]
                )

                return False


            return True


        except Exception as e:

            print(
                f"    Erro PATCH: {e}"
            )

            return False


    # ========================================================
    # INSERIR NOVO IMÓVEL
    # ========================================================

    try:

        resposta = requests.post(

            url_base,

            headers=headers,

            json=imovel,

            timeout=30

        )


        if resposta.status_code >= 300:

            print(
                "    Erro POST:",
                resposta.status_code
            )

            print(
                resposta.text[:1000]
            )

            return False


        return True


    except Exception as e:

        print(
            f"    Erro POST: {e}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)

    print(
        "RADAR DE IMÓVEIS - "
        "PENHA / ARMAÇÃO"
    )

    print(
        "VERSÃO 6"
    )

    print("=" * 70)


    # --------------------------------------------------------
    # CONTROLE DE DUPLICADOS
    # --------------------------------------------------------

    urls_processadas = set()


    analisados = 0

    salvos = 0

    ignorados = 0


    # ========================================================
    # LOOP DAS BUSCAS
    # ========================================================

    for tipo, consulta, dominio in BUSCAS:


        query = (
            f"{consulta} "
            f"site:{dominio}"
        )


        print()

        print("=" * 70)

        print(
            f"BUSCANDO: {tipo}"
        )

        print(
            f"SITE: {dominio}"
        )

        print("=" * 70)


        resultados = pesquisar_tavily(

            query,

            dominio

        )


        print(
            f"Resultados encontrados: "
            f"{len(resultados)}"
        )


        # ====================================================
        # RESULTADOS
        # ====================================================

        for resultado in resultados:


            url = resultado.get(
                "url"
            )


            if not url:

                ignorados += 1

                continue


            # ------------------------------------------------
            # DUPLICADO
            # ------------------------------------------------

            if url in urls_processadas:

                print(
                    "    DUPLICADO:"
                    f" {url}"
                )

                continue


            urls_processadas.add(
                url
            )


            analisados += 1


            titulo = (

                resultado.get(
                    "title"
                )

                or

                url

            )


            print()

            print(
                f"    Analisando: "
                f"{titulo}"
            )


            # ------------------------------------------------
            # PROCESSAR
            # ------------------------------------------------

            imovel = processar_resultado(

                resultado,

                tipo

            )


            if not imovel:

                ignorados += 1

                continue


            # ------------------------------------------------
            # MOSTRAR DADOS
            # ------------------------------------------------

            print(
                f"    Tipo: "
                f"{imovel.get('tipo')}"
            )


            print(
                f"    Preço: "
                f"{imovel.get('preco')}"
            )


            print(
                f"    Área: "
                f"{imovel.get('area_m2')}"
            )


            print(
                f"    Quartos: "
                f"{imovel.get('quartos')}"
            )


            print(
                f"    Banheiros: "
                f"{imovel.get('banheiros')}"
            )


            print(
                f"    Garagens: "
                f"{imovel.get('garagens')}"
            )


            print(
                f"    Fonte: "
                f"{imovel.get('fonte')}"
            )


            print(
                f"    Qualidade: "
                f"{imovel.get('qualidade_dados')}"
            )


            # ------------------------------------------------
            # SALVAR
            # ------------------------------------------------

            if salvar_imovel(
                imovel
            ):

                print(
                    "    ✓ Salvo/atualizado"
                )

                salvos += 1


            else:

                print(
                    "    ✗ Erro ao salvar"
                )


    # ========================================================
    # FINAL
    # ========================================================

    print()

    print("=" * 70)

    print(
        "RADAR FINALIZADO"
    )

    print("=" * 70)


    print(
        f"Resultados analisados: "
        f"{analisados}"
    )


    print(
        f"Imóveis salvos/atualizados: "
        f"{salvos}"
    )


    print(
        f"Ignorados: "
        f"{ignorados}"
    )


    print("=" * 70)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":

    main()
