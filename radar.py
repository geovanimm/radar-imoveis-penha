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
    ("Apartamento", 'apartamento venda "Armação" Penha SC', "zapimoveis.com.br"),
    ("Apartamento", 'apartamento venda "Armação" Penha SC', "vivareal.com.br"),
    ("Apartamento", 'apartamento venda "Armação" Penha SC', "olx.com.br"),
    ("Apartamento", 'apartamento venda "Armação" Penha SC', "imovelweb.com.br"),

    ("Casa", 'casa venda "Armação" Penha SC', "zapimoveis.com.br"),
    ("Casa", 'casa venda "Armação" Penha SC', "vivareal.com.br"),
    ("Casa", 'casa venda "Armação" Penha SC', "olx.com.br"),
    ("Casa", 'casa venda "Armação" Penha SC', "imovelweb.com.br"),

    ("Terreno", 'terreno lote venda "Armação" Penha SC', "zapimoveis.com.br"),
    ("Terreno", 'terreno lote venda "Armação" Penha SC', "vivareal.com.br"),
    ("Terreno", 'terreno lote venda "Armação" Penha SC', "olx.com.br"),
    ("Terreno", 'terreno lote venda "Armação" Penha SC', "imovelweb.com.br"),
]


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_numero(valor):
    if valor is None:
        return None

    try:
        valor = str(valor)
        valor = valor.replace("R$", "")
        valor = valor.replace("m²", "")
        valor = valor.replace("m2", "")
        valor = valor.strip()

        # 590.000,00
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        else:
            # 590.000
            if valor.count(".") == 1:
                partes = valor.split(".")
                if len(partes[1]) == 3:
                    valor = valor.replace(".", "")

        return float(valor)

    except:
        return None


def extrair_preco(texto):
    if not texto:
        return None

    padroes = [
        r'R\$\s*([\d\.]+(?:,\d{2})?)',
        r'R\$\s*([\d\.]+)',
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, re.I)
        if m:
            valor = normalizar_numero(m.group(1))

            if valor and 20_000 <= valor <= 20_000_000:
                return valor

    return None


def extrair_area(texto):
    if not texto:
        return None

    padroes = [
        r'(\d+(?:[\.,]\d+)?)\s*m²',
        r'(\d+(?:[\.,]\d+)?)\s*m2',
        r'área.{0,20}?(\d+(?:[\.,]\d+)?)',
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, re.I)

        if m:
            valor = normalizar_numero(m.group(1))

            if valor and 10 <= valor <= 10_000:
                return valor

    return None


def extrair_inteiro(texto, palavras):
    if not texto:
        return None

    for palavra in palavras:

        padroes = [
            rf'(\d+)\s*{palavra}',
            rf'{palavra}.{{0,15}}?(\d+)',
        ]

        for padrao in padroes:
            m = re.search(padrao, texto, re.I)

            if m:
                valor = int(m.group(1))

                if 0 <= valor <= 20:
                    return valor

    return None


def extrair_quartos(texto):
    return extrair_inteiro(
        texto,
        [
            r'quartos?',
            r'dormitórios?',
            r'dorms?',
        ]
    )


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


def extrair_garagens(texto):
    return extrair_inteiro(
        texto,
        [
            r'vagas?',
            r'garagens?',
        ]
    )


# ============================================================
# FONTE
# ============================================================

def identificar_fonte(url):

    dominio = urlparse(url).netloc.lower()

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
# TIPO
# ============================================================

def identificar_tipo(titulo, busca_tipo, texto=""):

    titulo_lower = (titulo or "").lower()
    texto_lower = (texto or "").lower()

    # Primeiro respeitamos o tipo da busca,
    # mas só se o título não contradizer.

    if any(x in titulo_lower for x in [
        "terreno",
        "lote",
        "lotes",
    ]):
        return "Terreno"

    if any(x in titulo_lower for x in [
        "apartamento",
        "apto",
        "cobertura",
        "flat",
    ]):
        return "Apartamento"

    if any(x in titulo_lower for x in [
        "casa",
        "sobrado",
        "residência",
        "residencia",
    ]):
        return "Casa"

    # Se o título não informou claramente,
    # usamos o tipo da busca.

    if busca_tipo in ["Apartamento", "Casa", "Terreno"]:
        return busca_tipo

    return None


# ============================================================
# PÁGINA GENÉRICA
# ============================================================

def pagina_generica(titulo, url):

    titulo = (titulo or "").strip().lower()
    url_lower = (url or "").lower()

    # Títulos claramente genéricos

    padroes_titulo = [

        r'^\d+\s+apartamentos?',
        r'^\d+\s+casas?',
        r'^\d+\s+terrenos?',
        r'^\d+\s+lotes?',

        r'^apartamentos?\s+(à|a)\s+venda',
        r'^casas?\s+(à|a)\s+venda',
        r'^terrenos?\s+(à|a)\s+venda',
        r'^lotes?.*venda',

        r'^apartamentos?\s+para\s+venda',
        r'^casas?\s+para\s+venda',
        r'^terrenos?\s+para\s+venda',

        r'^apartamentos?\s+para\s+comprar',
        r'^casas?\s+para\s+comprar',

        r'imóveis?\s+à\s+venda',
        r'imoveis\s+à\s+venda',
        r'imóveis?\s+para\s+venda',
        r'imoveis\s+para\s+venda',

        r'^penha\s*-\s*sc$',

        r'imóveis encontrados',
        r'imoveis encontrados',

        r'^página\s+\d+',
        r'^pagina\s+\d+',

        r'lotes/terrenos\s+para\s+venda',
        r'terrenos,\s*lotes',

        r'apartamentos\s+e\s+pousadas',
    ]

    for padrao in padroes_titulo:
        if re.search(padrao, titulo):
            return True

    # Títulos com "X imóveis à venda"

    if re.search(r'^\d+\s+.*à\s+venda', titulo):
        return True

    # URLs típicas de páginas de pesquisa

    palavras_url = [
        "/busca",
        "/search",
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

            # Não rejeitamos automaticamente todos os casos,
            # mas páginas claramente de categoria entram aqui.

            if any(x in url_lower for x in [
                "filtro",
                "search",
                "busca",
                "result",
                "pagina",
                "page=",
                "tipo=",
            ]):
                return True

    return False


# ============================================================
# JSON-LD
# ============================================================

def extrair_jsonld(soup):

    resultados = []

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:
            conteudo = script.string

            if not conteudo:
                continue

            dados = json.loads(conteudo)

            if isinstance(dados, list):
                resultados.extend(dados)

            else:
                resultados.append(dados)

        except:
            continue

    return resultados


def analisar_jsonld(jsonlds):

    dados = {}

    for item in jsonlds:

        if not isinstance(item, dict):
            continue

        tipo = item.get("@type", "")

        # Rejeita estruturas claramente de categoria

        if tipo in [
            "ItemList",
            "CollectionPage",
            "SearchResultsPage",
        ]:
            dados["generica"] = True
            continue

        nome = item.get("name")

        if nome and not dados.get("titulo"):
            dados["titulo"] = nome

        offers = item.get("offers")

        if isinstance(offers, dict):

            preco = offers.get("price")

            if preco:
                dados["preco"] = normalizar_numero(preco)

        elif isinstance(offers, list):

            for offer in offers:

                if isinstance(offer, dict):

                    preco = offer.get("price")

                    if preco:
                        dados["preco"] = normalizar_numero(preco)
                        break

        # Algumas estruturas usam price diretamente

        if item.get("price"):
            dados["preco"] = normalizar_numero(item.get("price"))

        # Área

        if item.get("floorSize"):

            fs = item["floorSize"]

            if isinstance(fs, dict):
                valor = fs.get("value")
            else:
                valor = fs

            dados["area_m2"] = normalizar_numero(valor)

        # Número de quartos

        for campo in [
            "numberOfBedrooms",
            "numberOfRooms",
        ]:

            if item.get(campo) is not None:

                try:
                    dados["quartos"] = int(
                        item.get(campo)
                    )
                except:
                    pass

        # Banheiros

        if item.get("numberOfBathroomsTotal") is not None:

            try:
                dados["banheiros"] = int(
                    item.get("numberOfBathroomsTotal")
                )
            except:
                pass

        # Garagens

        if item.get("numberOfParkingSpaces") is not None:

            try:
                dados["garagens"] = int(
                    item.get("numberOfParkingSpaces")
                )
            except:
                pass

        # Endereço

        endereco = item.get("address")

        if isinstance(endereco, dict):

            partes = []

            for campo in [
                "streetAddress",
                "addressLocality",
                "addressRegion",
            ]:

                if endereco.get(campo):
                    partes.append(
                        str(endereco[campo])
                    )

            if partes:
                dados["endereco"] = ", ".join(partes)

    return dados


# ============================================================
# DOWNLOAD DA PÁGINA
# ============================================================

def baixar_pagina(url):

    try:

        headers = {
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
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

def pesquisar_tavily(query, dominio):

    try:

        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 10,
                "include_answer": False,
                "include_domains": [dominio],
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
# VALIDAÇÃO
# ============================================================

def validar_dados(dados, tipo):

    preco = dados.get("preco")
    area = dados.get("area_m2")
    quartos = dados.get("quartos")
    banheiros = dados.get("banheiros")
    garagens = dados.get("garagens")

    # Terreno não deve ter quartos/banheiros/vagas

    if tipo == "Terreno":

        dados["quartos"] = None
        dados["banheiros"] = None
        dados["garagens"] = None

    # Área absurda para apartamento/casa

    if tipo in ["Apartamento", "Casa"]:

        if area and area > 1500:
            dados["area_m2"] = None

    # Números absurdos

    if quartos is not None:
        if quartos < 0 or quartos > 15:
            dados["quartos"] = None

    if banheiros is not None:
        if banheiros < 0 or banheiros > 20:
            dados["banheiros"] = None

    if garagens is not None:
        if garagens < 0 or garagens > 20:
            dados["garagens"] = None

    if preco is not None:

        if preco < 20_000 or preco > 20_000_000:
            dados["preco"] = None

    if area is not None:

        if area < 10 or area > 10_000:
            dados["area_m2"] = None

    return dados


# ============================================================
# QUALIDADE
# ============================================================

def calcular_qualidade(dados, veio_jsonld):

    campos = [
        dados.get("preco"),
        dados.get("area_m2"),
        dados.get("quartos"),
        dados.get("banheiros"),
        dados.get("garagens"),
    ]

    preenchidos = sum(
        1 for x in campos
        if x is not None
    )

    if veio_jsonld and preenchidos >= 3:
        return "alta"

    if preenchidos >= 3:
        return "media"

    if preenchidos >= 1:
        return "baixa"

    return None


# ============================================================
# PROCESSAR RESULTADO
# ============================================================

def processar_resultado(resultado, busca_tipo):

    url = resultado.get("url")

    if not url:
        return None

    titulo_original = (
        resultado.get("title") or ""
    ).strip()

    resumo = (
        resultado.get("content") or ""
    ).strip()

    # Não aceitar título que seja simplesmente URL

    if titulo_original.startswith("http://") or \
       titulo_original.startswith("https://"):

        titulo_original = ""

    # Primeiro filtro genérico usando título do resultado

    if pagina_generica(
        titulo_original,
        url
    ):

        print(
            f"    IGNORADA: {titulo_original or url}"
        )

        return None

    soup, html_text = baixar_pagina(url)

    dados = {}

    veio_jsonld = False

    titulo = titulo_original

    if soup:

        jsonlds = extrair_jsonld(soup)

        jsondados = analisar_jsonld(
            jsonlds
        )

        if jsondados.get("generica"):

            print(
                f"    IGNORADA: página de categoria"
            )

            return None

        if jsondados:

            veio_jsonld = True

            dados.update(
                {
                    k: v
                    for k, v in jsondados.items()
                    if k != "generica"
                }
            )

            if jsondados.get("titulo"):
                titulo = str(
                    jsondados["titulo"]
                ).strip()

    # Se título continua vazio, não inventamos título

    if not titulo:

        print(
            "    IGNORADA: sem título confiável"
        )

        return None

    # Filtro novamente depois do JSON-LD

    if pagina_generica(
        titulo,
        url
    ):

        print(
            f"    IGNORADA: {titulo}"
        )

        return None

    # Texto usado para fallback:
    # SOMENTE título + snippet da Tavily.
    # Não usamos toda a página porque isso
    # pode misturar vários imóveis.

    texto = f"{titulo} {resumo}"

    # ========================================================
    # FALLBACK DOS CAMPOS
    # ========================================================

    if dados.get("preco") is None:
        dados["preco"] = extrair_preco(texto)

    if dados.get("area_m2") is None:
        dados["area_m2"] = extrair_area(texto)

    if dados.get("quartos") is None:
        dados["quartos"] = extrair_quartos(texto)

    if dados.get("banheiros") is None:
        dados["banheiros"] = extrair_banheiros(texto)

    if dados.get("garagens") is None:
        dados["garagens"] = extrair_garagens(texto)

    # ========================================================
    # TIPO
    # ========================================================

    tipo = identificar_tipo(
        titulo,
        busca_tipo,
        texto
    )

    if not tipo:

        print(
            f"    IGNORADA: tipo não identificado"
        )

        return None

    # Se o título contradiz a busca, não salvamos
    # um apartamento como terreno, por exemplo.

    titulo_lower = titulo.lower()

    if busca_tipo == "Terreno":

        if any(x in titulo_lower for x in [
            "apartamento",
            "apto",
            "casa",
            "sobrado",
        ]):

            print(
                f"    IGNORADA: tipo incompatível"
            )

            return None

    if busca_tipo == "Apartamento":

        if any(x in titulo_lower for x in [
            "terreno",
            "lote",
            "casa",
            "sobrado",
        ]):

            print(
                f"    IGNORADA: tipo incompatível"
            )

            return None

    if busca_tipo == "Casa":

        if any(x in titulo_lower for x in [
            "terreno",
            "lote",
            "apartamento",
            "apto",
        ]):

            print(
                f"    IGNORADA: tipo incompatível"
            )

            return None

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    dados = validar_dados(
        dados,
        tipo
    )

    qualidade = calcular_qualidade(
        dados,
        veio_jsonld
    )

    # Para entrar no radar precisamos pelo menos
    # de preço OU área.
    #
    # Assim evitamos páginas completamente vazias.

    if (
        dados.get("preco") is None
        and dados.get("area_m2") is None
    ):

        print(
            f"    IGNORADA: sem preço ou área"
        )

        return None

    # ========================================================
    # BAIRRO
    # ========================================================

    bairro = None

    texto_lower = texto.lower()

    if "armação" in texto_lower or \
       "armacao" in texto_lower:

        bairro = "Armação"

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    imovel = {

        "url": url,

        "fonte": identificar_fonte(url),

        "titulo": titulo[:500],

        "tipo": tipo,

        "preco": dados.get("preco"),

        "area_m2": dados.get("area_m2"),

        "quartos": dados.get("quartos"),

        "banheiros": dados.get("banheiros"),

        "garagens": dados.get("garagens"),

        "endereco": dados.get("endereco"),

        "bairro": bairro,

        "descricao": resumo[:3000],

        "qualidade_dados": qualidade,

        "ativo": True,
    }

    return imovel


# ============================================================
# SUPABASE
# ============================================================

def headers_supabase():

    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization":
            f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type":
            "application/json",
        "Prefer":
            "return=minimal",
    }


def salvar_imovel(imovel):

    url_base = (
        SUPABASE_URL.rstrip("/")
        + "/rest/v1/"
        + SUPABASE_TABLE
    )

    headers = headers_supabase()

    # Verifica se URL já existe

    try:

        busca = requests.get(
            url_base,
            headers=headers,
            params={
                "url": f"eq.{imovel['url']}",
                "select": "id"
            },
            timeout=30
        )

        existentes = busca.json()

    except Exception as e:

        print(
            f"    Erro verificando imóvel: {e}"
        )

        return False

    # Atualiza existente

    if existentes:

        id_imovel = existentes[0]["id"]

        try:

            resposta = requests.patch(
                url_base,
                headers=headers,
                params={
                    "id": f"eq.{id_imovel}"
                },
                json=imovel,
                timeout=30
            )

            if resposta.status_code >= 300:

                print(
                    "    Erro PATCH:",
                    resposta.text
                )

                return False

            return True

        except Exception as e:

            print(
                f"    Erro PATCH: {e}"
            )

            return False

    # Insere novo

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
                resposta.text
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
    print("RADAR DE IMÓVEIS - PENHA / ARMAÇÃO")
    print("VERSÃO 5")
    print("=" * 70)

    urls_processadas = set()

    analisados = 0
    salvos = 0
    ignorados = 0

    for tipo, consulta, dominio in BUSCAS:

        query = f"{consulta} site:{dominio}"

        print()
        print("=" * 70)
        print(f"BUSCANDO: {tipo}")
        print(f"SITE: {dominio}")
        print("=" * 70)

        resultados = pesquisar_tavily(
            query,
            dominio
        )

        print(
            f"Resultados encontrados: "
            f"{len(resultados)}"
        )

        for resultado in resultados:

            url = resultado.get("url")

            if not url:
                ignorados += 1
                continue

            # Evita repetir o mesmo anúncio
            # entre buscas

            if url in urls_processadas:

                print(
                    "    DUPLICADO:"
                    f" {url}"
                )

                continue

            urls_processadas.add(url)

            analisados += 1

            titulo = (
                resultado.get("title")
                or url
            )

            print()
            print(
                f"    Analisando: {titulo}"
            )

            imovel = processar_resultado(
                resultado,
                tipo
            )

            if not imovel:

                ignorados += 1
                continue

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
                f"    Qualidade: "
                f"{imovel.get('qualidade_dados')}"
            )

            if salvar_imovel(imovel):

                print(
                    "    ✓ Salvo/atualizado"
                )

                salvos += 1

            else:

                print(
                    "    ✗ Erro ao salvar"
                )

    print()
    print("=" * 70)
    print("RADAR FINALIZADO")
    print("=" * 70)

    print(
        f"Resultados analisados: {analisados}"
    )

    print(
        f"Imóveis salvos/atualizados: {salvos}"
    )

    print(
        f"Ignorados: {ignorados}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
