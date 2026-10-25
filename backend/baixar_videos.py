#!/usr/bin/env python3
# baixar_videos.py
"""Script para download automatizado de vídeos do YouTube para testes de QA com yt-dlp."""

import json
import os
import time
from typing import Dict, List, Optional
import yt_dlp
from core.config_exercicios import EXERCICIOS


def baixar_dataset() -> None:
    """Realiza o download de até 5 vídeos curtos (<= 60s) por exercício para o dataset de QA.

    Consulta os 10 primeiros resultados do YouTube para cada exercício cadastrado,
    filtra por duração de até 60 segundos, descarrega até 5 vídeos no formato H.264
    e salva o mapeamento de URLs no arquivo dataset_qa/urls_mapeamento.json.
    """
    pasta_backend = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(pasta_backend, "dataset_qa")
    os.makedirs(pasta_destino, exist_ok=True)
    caminho_mapa = os.path.join(pasta_destino, "urls_mapeamento.json")

    # Carrega o mapeamento de URLs existente, se houver
    mapa_urls: Dict[str, List[str]] = {}
    if os.path.exists(caminho_mapa):
        try:
            with open(caminho_mapa, "r", encoding="utf-8") as f:
                dados_existentes = json.load(f)
                if isinstance(dados_existentes, dict):
                    for k, v in dados_existentes.items():
                        if isinstance(v, list):
                            mapa_urls[str(k)] = [str(u) for u in v if isinstance(u, str)]
                        elif isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                            mapa_urls[str(k)] = [v]
        except Exception:
            mapa_urls = {}

    print(f"Iniciando download do dataset de QA na pasta '{pasta_destino}'...\n")

    for id_ex, dados in EXERCICIOS.items():
        nome_exercicio = dados["nome"]
        query = f"ytsearch10: como fazer {dados['nome']} execução correta short"

        print(f"Buscando vídeos para [{id_ex}] {nome_exercicio}...")

        videos_baixados = 0
        urls_exercicio: List[str] = []

        try:
            # Opções para extração dos metadados das 10 entradas da pesquisa sem download prévio
            ydl_busca_opts = {
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_busca_opts) as ydl:
                info = ydl.extract_info(query, download=False)

            if info and 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if not entry or not isinstance(entry, dict):
                        continue

                    # Verifica se a entrada tem menos de 60 segundos
                    duracao = entry.get('duration')
                    if duracao is not None and duracao <= 60:
                        videos_baixados += 1
                        url_video = entry.get('webpage_url') or (
                            f"https://www.youtube.com/watch?v={entry['id']}" if entry.get('id') else None
                        )
                        if not url_video:
                            videos_baixados -= 1
                            continue

                        entry['webpage_url'] = url_video

                        ydl_opts = {
                            'format': 'bestvideo[ext=mp4][height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][height<=720][vcodec^=avc1]/best[ext=mp4]/best',
                            'outtmpl': f'{pasta_destino}/{id_ex}_{videos_baixados}.%(ext)s',
                            'quiet': True,
                        }

                        try:
                            print(f"  -> Baixando vídeo {videos_baixados}/5 ({duracao}s): {url_video}")
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([entry['webpage_url']])
                            urls_exercicio.append(url_video)
                        except Exception as e_down:
                            print(f"  -> Falha no download de {url_video}: {e_down}")
                            videos_baixados -= 1

                        if videos_baixados == 5:
                            break

            if urls_exercicio:
                mapa_urls[str(id_ex)] = urls_exercicio
                try:
                    with open(caminho_mapa, "w", encoding="utf-8") as f:
                        json.dump(mapa_urls, f, indent=2, ensure_ascii=False)
                except Exception as err:
                    print(f"Aviso ao salvar mapeamento de URLs: {err}")

            print(f"[{id_ex}] {nome_exercicio}: {videos_baixados} vídeos baixados com sucesso.\n")
        except Exception as e:
            print(f"[{id_ex}] {nome_exercicio}: Falha/Erro na busca - {e}\n")

        time.sleep(3)

    print("\nProcesso de download do dataset de QA finalizado.")


if __name__ == "__main__":
    baixar_dataset()
