import os
import requests
from datetime import datetime

TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

SEARCHES = [
    "imóveis venda Armação Penha SC",
    "apartamento venda Armação Penha SC",
    "casa venda Armação Penha SC",
    "terreno venda Armação Penha SC"
]


def pesquisar_tavily(query):
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "include_answer": False
    }

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()

    return response.json().get("results", [])


def salvar_imovel(imovel):
    url = f"{SUPABASE_URL}/rest/v1/imoveis"

    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    response = requests.post(
        url,
        json=imovel,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()


def processar_resultado(resultado):
    return {
        "url": resultado.get("url"),
        "fonte": "Tavily",
        "titulo": resultado.get("title"),
        "descricao": resultado.get("content"),
        "bairro": "Armação",
        "criado_em": datetime.utcnow().isoformat()
    }


def main():
    encontrados = 0

    for busca in SEARCHES:
        print(f"Pesquisando: {busca}")

        resultados = pesquisar_tavily(busca)

        for resultado in resultados:
            try:
                imovel = processar_resultado(resultado)
                salvar_imovel(imovel)

                encontrados += 1

                print(f"Salvo: {imovel['titulo']}")

            except Exception as erro:
                print(f"Erro ao salvar imóvel: {erro}")

    print(f"\nTotal encontrado: {encontrados}")


if __name__ == "__main__":
    main()
