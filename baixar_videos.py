#!/usr/bin/env python3
# baixar_videos.py
"""Script para download automatizado de vídeos do YouTube para testes de QA com yt-dlp."""

import os
import time
import yt_dlp
from core.config_exercicios import EXERCICIOS


def baixar_dataset():
    pasta_destino = "dataset_qa"
    os.makedirs(pasta_destino, exist_ok=True)

    print(f"Iniciando download do dataset de QA na pasta '{pasta_destino}'...\n")

    for id_ex, dados in EXERCICIOS.items():
        nome_exercicio = dados["nome"]
        query = f"ytsearch1: como fazer {nome_exercicio} execução correta short"

        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][height<=720][vcodec^=avc1]/best[ext=mp4]/best',
            'outtmpl': f'{pasta_destino}/{id_ex}.%(ext)s',
            'quiet': True,
            'match_filter': yt_dlp.utils.match_filter_func('duration <= 60'),
        }

        print(f"Buscando e baixando [{id_ex}] {nome_exercicio}...")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([query])
            print(f"[{id_ex}] {nome_exercicio}: Processamento concluído com sucesso!")
        except Exception as e:
            print(f"[{id_ex}] {nome_exercicio}: Falha/Vídeo ignorado - {e}")

        time.sleep(3)

    print("\nProcesso de download do dataset de QA finalizado.")


if __name__ == "__main__":
    baixar_dataset()

