#!/usr/bin/env python3
# baixar_videos.py
"""Script para download automatizado de vídeos do YouTube para testes de QA com yt-dlp."""

import json
import os
import time
import yt_dlp
from core.config_exercicios import EXERCICIOS


def baixar_dataset():
    pasta_destino = "dataset_qa"
    os.makedirs(pasta_destino, exist_ok=True)
    caminho_mapa = os.path.join(pasta_destino, "urls_mapeamento.json")

    # Carrega o mapeamento de URLs existente, se houver
    mapa_urls = {}
    if os.path.exists(caminho_mapa):
        try:
            with open(caminho_mapa, "r", encoding="utf-8") as f:
                dados_existentes = json.load(f)
                if isinstance(dados_existentes, dict):
                    # Mantém apenas URLs válidas previamente salvas
                    mapa_urls = {
                        str(k): v for k, v in dados_existentes.items()
                        if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://"))
                    }
        except Exception:
            mapa_urls = {}

    print(f"Iniciando download do dataset de QA na pasta '{pasta_destino}'...\n")

    for id_ex, dados in EXERCICIOS.items():
        nome_exercicio = dados["nome"]
        query = f"ytsearch5: como fazer {nome_exercicio} execução correta short"

        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][height<=720][vcodec^=avc1]/best[ext=mp4]/best',
            'outtmpl': f'{pasta_destino}/{id_ex}.%(ext)s',
            'quiet': True,
            'match_filter': yt_dlp.utils.match_filter_func('duration <= 60'),
        }

        print(f"Buscando e baixando [{id_ex}] {nome_exercicio}...")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)

            url_real = None
            if info:
                # Trata múltiplos resultados de pesquisa devolvidos (ex: ytsearch5)
                entries = info.get('entries')
                if entries:
                    for entry in entries:
                        if not entry or not isinstance(entry, dict):
                            continue
                        candidato = entry.get('webpage_url') or entry.get('original_url')
                        if not candidato and entry.get('id'):
                            candidato = f"https://www.youtube.com/watch?v={entry['id']}"
                        if not candidato and entry.get('url'):
                            url_entry = entry.get('url')
                            if isinstance(url_entry, str) and (url_entry.startswith("http://") or url_entry.startswith("https://")):
                                candidato = url_entry
                        if candidato and (str(candidato).startswith("http://") or str(candidato).startswith("https://")):
                            url_real = str(candidato)
                            break

                # Fallback se info representar diretamente um único vídeo
                if not url_real and info.get('_type') != 'playlist':
                    candidato = info.get('webpage_url') or info.get('original_url')
                    if not candidato and info.get('id'):
                        candidato = f"https://www.youtube.com/watch?v={info['id']}"
                    if candidato and (str(candidato).startswith("http://") or str(candidato).startswith("https://")):
                        url_real = str(candidato)

            if url_real:
                mapa_urls[str(id_ex)] = url_real
                try:
                    with open(caminho_mapa, "w", encoding="utf-8") as f:
                        json.dump(mapa_urls, f, indent=2, ensure_ascii=False)
                except Exception as err:
                    print(f"Aviso ao salvar mapeamento de URLs: {err}")

            print(f"[{id_ex}] {nome_exercicio}: Processamento concluído com sucesso! (URL: {url_real or 'N/A'})")
        except Exception as e:
            print(f"[{id_ex}] {nome_exercicio}: Falha/Vídeo ignorado - {e}")

        time.sleep(3)

    print("\nProcesso de download do dataset de QA finalizado.")


if __name__ == "__main__":
    baixar_dataset()

