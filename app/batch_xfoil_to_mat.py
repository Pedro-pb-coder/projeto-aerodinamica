"""
Batch runner: para cada arquivo .dat de geometria em uma pasta,
roda XFoil (com a lógica de skip), extrapola com Montgomerie e
salva .mat no formato de struct do MATLAB (variável 'polar' com campos 'Cl' e 'Cd').

Requer:
- python package 'xfoil'
- scipy.io (scipy)
- numpy, os

Coloque este arquivo na mesma pasta dos .dat gerados (ou aponte `GEOMETRY_FOLDER`)
e execute: python batch_xfoil_to_mat.py
"""

import os
import glob
import numpy as np
import scipy.io as sio
from pathlib import Path

# --- IMPORTS das suas funções (ajuste o import se estiver em outro arquivo)
# Aqui assumimos que estão no mesmo diretório em 'rodar_simulação_neg_posit2.py'
try:
    from rodar_simulação_neg_posit import rodar_xfoil_pre_stall, extrapolate_full_range
except ImportError:
    print("Erro: Não foi possível encontrar o arquivo 'rodar_simulação_neg_posit.py'.")
    print("Certifique-se de que ambos os scripts (.py) estão na mesma pasta.")
    exit()

# --- Configurações principais ---
GEOMETRY_FOLDER = "2e63_naca4412_6_interpolados"   # pasta onde os .dat das etapas estão (pode ser subpasta)
GEOMETRY_PATTERN = "e63_naca4412_rR_*.dat"  # padrão para encontrar os .dat gerados pelo morph
REYNOLDS_LIST = [2e4, 4.5e4, 7.5e4, 1e5, 2.5e5, 5e5, 7.5e5, 1e6]  # mesma lista do seu script
ALPHA_GRID = np.arange(-90, 91.1, 1.0)  # -90 a +91 (passo 1.0)
NUM_EXTRAP_POINTS = 200  # pontos usados na extrapolação (ajustável)

# --- PARÂMETROS DE ROBUSTEZ (AJUSTADOS) ---
ANG_START = -15.0
ANG_END = 20.0
ANG_STEP = 0.25      # (AJUSTADO) Passo menor para melhor convergência
MAX_ITER_XFOIL = 500 # (AJUSTADO) Mais iterações permitidas

# --- Função utilitária para processar um arquivo de geometria e montar as matrizes ---
def process_geometry_file(geom_path, reynolds_list=REYNOLDS_LIST,
                          alpha_grid=ALPHA_GRID,
                          ang_start=ANG_START, ang_end=ANG_END, ang_step=ANG_STEP,
                          max_iter=MAX_ITER_XFOIL,
                          num_extrap=NUM_EXTRAP_POINTS):
    """
    Para um arquivo de geometria (.dat):
      - roda XFoil para cada Re,
      - extrapola full range,
      - interpola matrizes Cd,Cl no alpha_grid,
      - retorna Cd_matrix, Cl_matrix e alpha_grid.
    Cada matriz terá shape (len(alpha_grid), len(reynolds_list)).
    Valores não obtidos (Re que falharam) serão preenchidos com np.nan.
    """
    n_alpha = len(alpha_grid)
    n_re = len(reynolds_list)
    Cd_mat = np.full((n_alpha, n_re), np.nan, dtype=float)
    Cl_mat = np.full((n_alpha, n_re), np.nan, dtype=float)

    for j, re in enumerate(reynolds_list):
        print(f"\nProcessing geometry '{geom_path.name}'  -> Re = {re:.1e}")

        a_xf, cl_xf, cd_xf = rodar_xfoil_pre_stall(
            arquivo_geometria=str(geom_path),
            reynolds=re,
            angulo_inicio=ang_start,
            angulo_fim=ang_end,
            passo=ang_step,
            max_iteracoes=max_iter
        )

        if a_xf is None or len(a_xf) < 5 or (not np.any(a_xf >= 0)) or (not np.any(a_xf <= 0)):
            print(f"  Re={re:.1e} falhou ou não produziu dados suficientes. Coluna preenchida com NaN.")
            continue

        # Extrapola full range (usa sua função)
        try:
            alpha_full, cl_full, cd_full = extrapolate_full_range(a_xf, cl_xf, cd_xf, num_points_extrap=num_extrap)
            if alpha_full is None:
                print(f"  Extrapolação falhou para Re={re:.1e}. Pulando.")
                continue
        except Exception as e:
            print(f"  Erro durante extrapolação para Re={re:.1e}: {e}. Pulando.")
            continue

        # interpola para a grade fixa alpha_grid
        cl_interp = np.interp(alpha_grid, alpha_full, cl_full, left=np.nan, right=np.nan)
        cd_interp = np.interp(alpha_grid, alpha_full, cd_full, left=np.nan, right=np.nan)

        Cl_mat[:, j] = cl_interp
        Cd_mat[:, j] = cd_interp

        print(f"  Re={re:.1e} -> preenchida coluna {j+1}/{n_re}")

    return alpha_grid, Cd_mat, Cl_mat

# --- Loop principal: encontra todos os .dat e processa um a um ---
def main():
    # Procura na pasta definida em GEOMETRY_FOLDER
    base_path = Path(GEOMETRY_FOLDER)
    geom_files = sorted(base_path.glob(GEOMETRY_PATTERN))
    
    if len(geom_files) == 0:
        print(f"Nenhum arquivo de geometria encontrado em '{base_path.resolve()}' com o padrão: '{GEOMETRY_PATTERN}'")
        return

    print(f"Encontrados {len(geom_files)} geometrias. Iniciando processamento...")

    for geom in geom_files:
        print("\n" + "="*60)
        print("Processando:", geom.name)
        
        # Define o nome do arquivo .mat de saída
        out_mat_name = geom.stem + ".mat"
        out_path = base_path / out_mat_name

        alpha_grid, Cd_mat, Cl_mat = process_geometry_file(
            geom_path=geom,
            reynolds_list=REYNOLDS_LIST,
            alpha_grid=ALPHA_GRID,
            ang_start=ANG_START, ang_end=ANG_END, ang_step=ANG_STEP,
            max_iter=MAX_ITER_XFOIL,
            num_extrap=NUM_EXTRAP_POINTS
        )

        # --- (CORREÇÃO) Monta a struct para o MATLAB ---
        # Cria matrizes (n_angles x (1 + n_re)):
        # primeira coluna = alpha, seguintes colunas = dados (Cd ou Cl) por Re.
        alpha_col = np.asarray(alpha_grid).reshape(-1, 1)  # (n_alpha, 1)
        Cd_full = np.hstack([alpha_col, Cd_mat])  # (n_alpha, 1 + n_re)
        Cl_full = np.hstack([alpha_col, Cl_mat])

        # Cria um dicionário Python. Isso será salvo como uma 'struct' no MATLAB.
        polar_data_struct = {
            'cl': Cl_full.astype(float),
            'cd': Cd_full.astype(float)
        }
        
        # Salva o dicionário 'polar_data_struct' dentro de uma variável MATLAB chamada 'polar'
        sio.savemat(str(out_path), {"polar": polar_data_struct})
        print(f"\nSalvo: {out_path}")
        print(f"  -> Struct 'polar' com campos 'Cl' (shape {Cl_full.shape}) e 'Cd' (shape {Cd_full.shape})")

    print("\n" + "="*60)
    print("Processamento de todas as geometrias concluído.")

if __name__ == "__main__":
    main()