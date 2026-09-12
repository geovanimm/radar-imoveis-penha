"""Radar de imóveis à venda no bairro Armação, Penha/SC.

Busca anúncios via Tavily, extrai dados (preço, área, quartos...) das
páginas encontradas e mantém a tabela `imoveis` no Supabase sincronizada.
"""

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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)

# Limites usados para descartar valores absurdos extraídos por regex.
PRECO_MIN, PRECO_MAX = 20_000, 20_000_000
AREA_MIN, AREA_MAX = 10, 10_000
AREA_MAX_CASA_APTO = 1_500
NUMERO_MIN, NUMERO_MAX = 0, 10

sessao_web = requests.Session()
sessao_web.headers.update({"User-Agent": USER_AGENT})


# ============================================================
# BUSCAS
# ============================================================
# Uma busca por combinação (tipo de imóvel x site). Bairro fixo: Armação.

QUERIES_POR_TIPO = {
    "Apartamento": 'apartamento venda "Armação" Penha SC',
    "Casa": 'casa venda "Armação" Penha SC',
    "Terreno": 'terreno lote venda "Armação" Penha SC',
}

# Imobiliárias com site próprio em Penha-SC que anunciam a região da
# Armação (confirmadas manualmente). Portais genéricos (OLX, ZAP, Viva
# Real, Imovelweb) foram removidos: traziam muito ruído de fora do
# público-alvo (imóveis de outras cidades, classificados não verificados).
SITES = [
    "imobiliariapenha.com.br",
    "h8imoveispenha.com.br",
    "olegarioimoveis.com.br",
    "shsimoveis.com",
    "solimoveis.com.br",
    "praiaalegreimoveis.com",
    "imobiliariabeatriz.com.br",
]

BUSCAS = [
    (tipo, query, site)
    for tipo, query in QUERIES_POR_TIPO.items()
    for site in SITES
]


# ============================================================
# NORMALIZAÇÃO DE NÚMEROS
# ============================================================

def normalizar_numero(valor):
    """Converte strings como 'R$ 590.000,00' ou '590.000' em float."""
    if valor is None:
        return None

    try:
        valor = str(valor).replace("R$", "").replace("m²", "").replace("m2", "").strip()

        # Exemplos: "590.000,00" | "590.000" | "590000"
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif valor.count(".") == 1 and len(valor.split(".")[1]) == 3:
            # "." usado como separador de milhar (ex: "590.000")
            valor = valor.replace(".", "")

        return float(valor)
    except (ValueError, TypeError):
        return None


# ============================================================
# EXTRAÇÃO DE CAMPOS POR REGEX
# ============================================================

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
            if valor and PRECO_MIN <= valor <= PRECO_MAX:
                return valor

    return None


def extrair_area(texto):
    if not texto:
        return None

    padroes = [
        r'(\d+(?:[\.,]\d+)?)\s*m²',
        r'(\d+(?:[\.,]\d+)?)\s*m2',
        r'área.{0,30}?(\d+(?:[\.,]\d+)?)',
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, re.I)
        if m:
            valor = normalizar_numero(m.group(1))
            if valor and AREA_MIN <= valor <= AREA_MAX:
                return valor

    return None


def extrair_inteiro(texto, palavras):
    """Procura um inteiro pequeno (0-10) associado a uma das `palavras`."""
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
                try:
                    valor = int(m.group(1))
                    if NUMERO_MIN <= valor <= NUMERO_MAX:
                        return valor
                except ValueError:
                    pass

    return None


def extrair_quartos(texto):
    return extrair_inteiro(texto, [r'quartos?', r'dormitórios?', r'dormitorios?', r'dorms?'])


def extrair_banheiros(texto):
    return extrair_inteiro(texto, [r'banheiros?', r'bwc', r'suítes?', r'suites?'])


def extrair_garagens(texto):
    return extrair_inteiro(texto, [r'vagas?', r'garagens?'])


# ============================================================
# IDENTIFICAR FONTE / TIPO
# ============================================================

FONTES_POR_DOMINIO = {
    "imobiliariapenha": "Imobiliária Penha",
    "h8imoveispenha": "H8 Imóveis",
    "olegarioimoveis": "Olegário Imóveis",
    "shsimoveis": "SHS Imóveis",
    "solimoveis": "Sol Imóveis",
    "praiaalegreimoveis": "Praia Alegre Imóveis",
    "imobiliariabeatriz": "Imobiliária Beatriz",
}


def identificar_fonte(url):
    dominio = urlparse(url).netloc.lower()

    for chave, nome in FONTES_POR_DOMINIO.items():
        if chave in dominio:
            return nome

    return dominio


PALAVRAS_TERRENO = ["terreno", "lote", "lotes"]
PALAVRAS_APARTAMENTO = ["apartamento", "apto", "cobertura", "flat"]
PALAVRAS_CASA = ["casa", "sobrado", "residência", "residencia"]


def identificar_tipo(titulo, busca_tipo, texto=""):
    titulo_lower = (titulo or "").lower()

    # O título é mais confiável que o tipo da busca original.
    if any(x in titulo_lower for x in PALAVRAS_TERRENO):
        return "Terreno"

    if any(x in titulo_lower for x in PALAVRAS_APARTAMENTO):
        return "Apartamento"

    if any(x in titulo_lower for x in PALAVRAS_CASA):
        return "Casa"

    if busca_tipo in ("Apartamento", "Casa", "Terreno"):
        return busca_tipo

    return None


# ============================================================
# VERIFICAR PÁGINA GENÉRICA (listagem, busca, categoria)
# ============================================================

PADROES_TITULO_GENERICO = [
    # Quantidade de imóveis
    r'^\d+\s+apartamentos?',
    r'^\d+\s+casas?',
    r'^\d+\s+terrenos?',
    r'^\d+\s+lotes?',
    r'^\d+\s+.*à\s+venda',

    # Categorias (só no plural: no singular é assim que a Imobiliária
    # Beatriz nomeia os anúncios individuais, ex.: "Casa à venda, Penha - SC")
    r'^apartamentos\s+(à|a)\s+venda',
    r'^casas\s+(à|a)\s+venda',
    r'^terrenos\s+(à|a)\s+venda',
    r'^lotes.*venda',
    r'^apartamentos\s+para\s+venda',
    r'^casas\s+para\s+venda',
    r'^terrenos\s+para\s+venda',
    r'^apartamentos\s+para\s+comprar',
    r'^casas\s+para\s+comprar',

    # Imóveis
    r'imóveis?\s+à\s+venda',
    r'imoveis\s+à\s+venda',
    r'imóveis?\s+para\s+venda',
    r'imoveis\s+para\s+venda',

    # Penha geral
    r'^penha\s*-\s*sc$',

    # Resultados / listagens
    r'imóveis encontrados',
    r'imoveis encontrados',
    r'^resultados',
    r'^anúncios',
    r'^anuncios',
    r'^ofertas',
    r'^classificados',
    r'^página\s+\d+',
    r'^pagina\s+\d+',

    # Terrenos
    r'lotes/terrenos\s+para\s+venda',
    r'terrenos,\s*lotes',

    # Outros
    r'apartamentos\s+e\s+pousadas',
]

PALAVRAS_URL_LISTAGEM = [
    "/busca", "/search", "/resultado", "/resultados", "/filtro",
    "/imoveis-a-venda", "/imoveis?", "/apartamentos?", "/casas?",
    "/terrenos?", "/lotes?", "/venda?",
]

PALAVRAS_URL_CONFIRMACAO = [
    "filtro", "search", "busca", "result", "pagina", "page=", "tipo=",
]


def pagina_generica(titulo, url):
    """True se o título/URL parecem ser de listagem, não de um imóvel."""
    titulo = (titulo or "").strip().lower()
    url_lower = (url or "").lower()

    if any(re.search(padrao, titulo) for padrao in PADROES_TITULO_GENERICO):
        return True

    for palavra in PALAVRAS_URL_LISTAGEM:
        if palavra in url_lower and any(x in url_lower for x in PALAVRAS_URL_CONFIRMACAO):
            return True

    return False


# ============================================================
# JSON-LD
# ============================================================

TIPOS_JSONLD_GENERICOS = {"ItemList", "CollectionPage", "SearchResultsPage"}


def extrair_jsonld(soup):
    resultados = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            conteudo = script.string
            if not conteudo:
                continue

            dados = json.loads(conteudo)
            if isinstance(dados, list):
                resultados.extend(dados)
            else:
                resultados.append(dados)
        except (json.JSONDecodeError, TypeError):
            continue

    return resultados


def _definir_se_ausente(dados, campo, valor):
    """Preenche `campo` só se ainda não houver valor (primeiro bloco vence)."""
    if valor is not None and dados.get(campo) is None:
        dados[campo] = valor


def analisar_jsonld(jsonlds):
    """Extrai dados estruturados dos blocos JSON-LD de uma página.

    Quando há vários blocos, o primeiro com um dado válido vence — evita que
    um schema secundário (ex.: Organization) sobrescreva o schema principal
    do imóvel.
    """
    dados = {}

    for item in jsonlds:
        if not isinstance(item, dict):
            continue

        # @type pode vir como string ou como lista de strings.
        tipo_item = item.get("@type", "")
        tipos_item = tipo_item if isinstance(tipo_item, list) else [tipo_item]

        if any(t in TIPOS_JSONLD_GENERICOS for t in tipos_item):
            dados["generica"] = True
            continue

        _definir_se_ausente(dados, "titulo", item.get("name"))

        # Preço: pode vir em offers (dict ou list) ou direto no item.
        offers = item.get("offers")
        preco = None

        if isinstance(offers, dict):
            preco = offers.get("price")
        elif isinstance(offers, list):
            preco = next(
                (o.get("price") for o in offers if isinstance(o, dict) and o.get("price")),
                None,
            )
        if preco is None:
            preco = item.get("price")

        _definir_se_ausente(dados, "preco", normalizar_numero(preco))

        # Área
        floor_size = item.get("floorSize")
        if floor_size is not None:
            valor = floor_size.get("value") if isinstance(floor_size, dict) else floor_size
            _definir_se_ausente(dados, "area_m2", normalizar_numero(valor))

        # Quartos, banheiros, garagem
        for campo_origem in ("numberOfBedrooms", "numberOfRooms"):
            if item.get(campo_origem) is not None:
                try:
                    _definir_se_ausente(dados, "quartos", int(item[campo_origem]))
                except (ValueError, TypeError):
                    pass

        if item.get("numberOfBathroomsTotal") is not None:
            try:
                _definir_se_ausente(dados, "banheiros", int(item["numberOfBathroomsTotal"]))
            except (ValueError, TypeError):
                pass

        if item.get("numberOfParkingSpaces") is not None:
            try:
                _definir_se_ausente(dados, "garagens", int(item["numberOfParkingSpaces"]))
            except (ValueError, TypeError):
                pass

        # Endereço
        endereco = item.get("address")
        if isinstance(endereco, dict):
            partes = [
                str(endereco[campo])
                for campo in ("streetAddress", "addressLocality", "addressRegion")
                if endereco.get(campo)
            ]
            if partes:
                _definir_se_ausente(dados, "endereco", ", ".join(partes))

    return dados


# ============================================================
# HTTP: PÁGINA DO ANÚNCIO / TAVILY
# ============================================================

def baixar_pagina(url):
    try:
        resposta = sessao_web.get(url, timeout=20, allow_redirects=True)

        if resposta.status_code >= 400:
            print(f"    Página retornou HTTP {resposta.status_code}")
            return None, None

        return BeautifulSoup(resposta.text, "html.parser"), resposta.text
    except requests.RequestException as e:
        print(f"    Erro ao acessar página: {e}")
        return None, None


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
            timeout=60,
        )
        response.raise_for_status()

        return response.json().get("results", [])
    except requests.RequestException as e:
        print(f"Erro Tavily: {e}")
        return []


# ============================================================
# VALIDAÇÃO E QUALIDADE
# ============================================================

def validar_dados(dados, tipo):
    """Zera campos fora de faixa ou incoerentes com o tipo do imóvel."""
    if tipo == "Terreno":
        dados["quartos"] = None
        dados["banheiros"] = None
        dados["garagens"] = None

    area = dados.get("area_m2")
    if tipo in ("Apartamento", "Casa") and area and area > AREA_MAX_CASA_APTO:
        dados["area_m2"] = None

    for campo in ("quartos", "banheiros", "garagens"):
        valor = dados.get(campo)
        if valor is not None and not (NUMERO_MIN <= valor <= NUMERO_MAX):
            dados[campo] = None

    preco = dados.get("preco")
    if preco is not None and not (PRECO_MIN <= preco <= PRECO_MAX):
        dados["preco"] = None

    area = dados.get("area_m2")
    if area is not None and not (AREA_MIN <= area <= AREA_MAX):
        dados["area_m2"] = None

    return dados


def calcular_qualidade(dados, veio_jsonld):
    campos = ("preco", "area_m2", "quartos", "banheiros", "garagens")
    preenchidos = sum(1 for campo in campos if dados.get(campo) is not None)

    if veio_jsonld and preenchidos >= 3:
        return "alta"
    if preenchidos >= 3:
        return "media"
    if preenchidos >= 1:
        return "baixa"

    return None


# ============================================================
# FORA DE SANTA CATARINA
# ============================================================
# As imobiliárias em SITES às vezes anunciam imóveis fora de Penha-SC
# (outras cidades do litoral catarinense, ou até outros estados — algumas
# repetem a mesma marca "Imobiliária em Penha SC" no título mesmo para
# imóveis de outras regiões). Detecta padrões "Cidade/UF" ou "Cidade - UF"
# apontando para um estado que não seja SC.

OUTRAS_UFS = {
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt",
    "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro",
    "rr", "sp", "se", "to",
}


def menciona_outra_uf(texto):
    for m in re.finditer(r'[/\-]\s*([A-Z]{2})\b', texto):
        if m.group(1).lower() in OUTRAS_UFS:
            return True
    return False


# ============================================================
# TIPO INCOMPATÍVEL COM A BUSCA
# ============================================================

PALAVRAS_POR_TIPO = {
    "Terreno": ["apartamento", "apto", "casa", "sobrado"],
    "Apartamento": ["terreno", "lote", "casa", "sobrado"],
    "Casa": ["terreno", "lote", "apartamento", "apto"],
}


def tipo_incompativel(busca_tipo, titulo_lower):
    palavras_proibidas = PALAVRAS_POR_TIPO.get(busca_tipo, [])
    return any(x in titulo_lower for x in palavras_proibidas)


# ============================================================
# PROCESSAR RESULTADO
# ============================================================

def processar_resultado(resultado, busca_tipo):
    url = resultado.get("url")
    if not url:
        return None

    titulo_original = (resultado.get("title") or "").strip()
    resumo = (resultado.get("content") or "").strip()

    # O título não pode ser a própria URL.
    if titulo_original.startswith(("http://", "https://")):
        titulo_original = ""

    if pagina_generica(titulo_original, url):
        print(f"    IGNORADA: {titulo_original or url}")
        return None

    soup, _ = baixar_pagina(url)

    dados = {}
    veio_jsonld = False
    titulo = titulo_original

    if soup:
        jsondados = analisar_jsonld(extrair_jsonld(soup))

        if jsondados.get("generica"):
            print("    IGNORADA: página de categoria")
            return None

        if jsondados:
            veio_jsonld = True
            dados.update({k: v for k, v in jsondados.items() if k != "generica"})

            if jsondados.get("titulo"):
                titulo = str(jsondados["titulo"]).strip()

    if not titulo:
        print("    IGNORADA: sem título confiável")
        return None

    if pagina_generica(titulo, url):
        print(f"    IGNORADA: {titulo}")
        return None

    # Usamos apenas título + snippet (não a página inteira) para evitar
    # misturar dados de vários imóveis listados na mesma página.
    texto = f"{titulo} {resumo}"
    texto_lower = texto.lower()

    if not any(p in texto_lower for p in ("penha", "armação", "armacao")):
        print("    IGNORADA: fora de Penha/Armação")
        return None

    if menciona_outra_uf(texto):
        print("    IGNORADA: fora de Santa Catarina")
        return None

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

    tipo = identificar_tipo(titulo, busca_tipo, texto)
    if not tipo:
        print("    IGNORADA: tipo não identificado")
        return None

    if tipo_incompativel(busca_tipo, titulo.lower()):
        print("    IGNORADA: tipo incompatível")
        return None

    dados = validar_dados(dados, tipo)
    qualidade = calcular_qualidade(dados, veio_jsonld)

    if dados.get("preco") is None and dados.get("area_m2") is None:
        print("    IGNORADA: sem preço ou área")
        return None

    bairro = "Armação" if ("armação" in texto_lower or "armacao" in texto_lower) else None

    return {
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


# ============================================================
# SUPABASE
# ============================================================

def headers_supabase():
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def salvar_imovel(imovel):
    """Insere o imóvel, ou atualiza se a URL já existir na tabela."""
    url_base = SUPABASE_URL.rstrip("/") + "/rest/v1/" + SUPABASE_TABLE
    headers = headers_supabase()

    try:
        busca = requests.get(
            url_base,
            headers=headers,
            params={"url": "eq." + imovel["url"], "select": "id"},
            timeout=30,
        )

        if busca.status_code >= 300:
            print("    Erro consultando Supabase:", busca.status_code)
            print("    Resposta:", busca.text[:1000])
            return False

        existentes = busca.json()
        if not isinstance(existentes, list):
            print("    Resposta inesperada do Supabase:")
            print(str(existentes)[:1000])
            return False
    except requests.RequestException as e:
        print(f"    Erro verificando imóvel: {e}")
        return False

    if existentes:
        id_imovel = existentes[0].get("id")
        if not id_imovel:
            print("    Imóvel encontrado, mas sem ID.")
            return False

        try:
            resposta = requests.patch(
                url_base,
                headers=headers,
                params={"id": f"eq.{id_imovel}"},
                json=imovel,
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"    Erro PATCH: {e}")
            return False

        if resposta.status_code >= 300:
            print("    Erro PATCH:", resposta.status_code)
            print(resposta.text[:1000])
            return False

        return True

    try:
        resposta = requests.post(url_base, headers=headers, json=imovel, timeout=30)
    except requests.RequestException as e:
        print(f"    Erro POST: {e}")
        return False

    if resposta.status_code >= 300:
        print("    Erro POST:", resposta.status_code)
        print(resposta.text[:1000])
        return False

    return True


def limpar_tabela():
    """Apaga todos os registros da tabela antes de rodar.

    Uso temporário para a fase de testes (ligado via a variável de
    ambiente LIMPAR_TABELA_ANTES=true) — remover depois que os dados
    já puderem ser tratados como definitivos.
    """
    url_base = SUPABASE_URL.rstrip("/") + "/rest/v1/" + SUPABASE_TABLE
    headers = headers_supabase()

    try:
        resposta = requests.delete(
            url_base,
            headers=headers,
            params={"id": "not.is.null"},
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"Erro ao limpar tabela: {e}")
        return False

    if resposta.status_code >= 300:
        print("Erro ao limpar tabela:", resposta.status_code)
        print(resposta.text[:1000])
        return False

    print("Tabela limpa antes da execução (LIMPAR_TABELA_ANTES=true).")
    return True


# ============================================================
# MAIN
# ============================================================

def validar_configuracao():
    faltando = [
        nome
        for nome, valor in (
            ("TAVILY_API_KEY", TAVILY_API_KEY),
            ("SUPABASE_URL", SUPABASE_URL),
            ("SUPABASE_SECRET_KEY", SUPABASE_SECRET_KEY),
        )
        if not valor
    ]

    if faltando:
        raise SystemExit(
            "Variáveis de ambiente ausentes: " + ", ".join(faltando)
        )


def mostrar_imovel(imovel):
    print(f"    Tipo: {imovel.get('tipo')}")
    print(f"    Preço: {imovel.get('preco')}")
    print(f"    Área: {imovel.get('area_m2')}")
    print(f"    Quartos: {imovel.get('quartos')}")
    print(f"    Banheiros: {imovel.get('banheiros')}")
    print(f"    Garagens: {imovel.get('garagens')}")
    print(f"    Fonte: {imovel.get('fonte')}")
    print(f"    Qualidade: {imovel.get('qualidade_dados')}")


def main():
    validar_configuracao()

    print("=" * 70)
    print("RADAR DE IMÓVEIS - PENHA / ARMAÇÃO")
    print("VERSÃO 7")
    print("=" * 70)

    if os.getenv("LIMPAR_TABELA_ANTES", "").lower() == "true":
        limpar_tabela()

    urls_processadas = set()
    analisados = salvos = ignorados = 0

    for tipo, consulta, dominio in BUSCAS:
        query = f"{consulta} site:{dominio}"

        print()
        print("=" * 70)
        print(f"BUSCANDO: {tipo}")
        print(f"SITE: {dominio}")
        print("=" * 70)

        resultados = pesquisar_tavily(query, dominio)
        print(f"Resultados encontrados: {len(resultados)}")

        for resultado in resultados:
            url = resultado.get("url")
            if not url:
                ignorados += 1
                continue

            if url in urls_processadas:
                print(f"    DUPLICADO: {url}")
                continue

            urls_processadas.add(url)
            analisados += 1

            print()
            print(f"    Analisando: {resultado.get('title') or url}")

            try:
                imovel = processar_resultado(resultado, tipo)
            except Exception as e:
                print(f"    ERRO inesperado processando resultado: {e}")
                ignorados += 1
                continue

            if not imovel:
                ignorados += 1
                continue

            mostrar_imovel(imovel)

            if salvar_imovel(imovel):
                print("    ✓ Salvo/atualizado")
                salvos += 1
            else:
                print("    ✗ Erro ao salvar")

    print()
    print("=" * 70)
    print("RADAR FINALIZADO")
    print("=" * 70)
    print(f"Resultados analisados: {analisados}")
    print(f"Imóveis salvos/atualizados: {salvos}")
    print(f"Ignorados: {ignorados}")
    print("=" * 70)


if __name__ == "__main__":
    main()
