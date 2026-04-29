import os
import numpy as np
from scipy.interpolate import PchipInterpolator


def parse_airfoil(filename):
    """
    Lê arquivo Selig e retorna (header, x, y).
    """
    x, y = [], []
    with open(filename, 'r') as f:
        header = f.readline().strip()
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    x.append(float(parts[0]))
                    y.append(float(parts[1]))
                except ValueError:
                    continue
    return header, np.array(x), np.array(y)


def create_interpolators(x_norm, y_norm):
    """
    Cria interpoladores PCHIP independentes para extradorso e intradorso.
    """
    # Encontra o bordo de ataque (índice do menor x)
    min_x_index = np.argmin(x_norm)
    
    # Separa extradorso (TE -> LE) e intradorso (LE -> TE)
    x_upper, y_upper = x_norm[:min_x_index + 1], y_norm[:min_x_index + 1]
    x_lower, y_lower = x_norm[min_x_index:], y_norm[min_x_index:]
    
    # Cria interpoladores (precisa ordenar por x para Pchip)
    f_upper = PchipInterpolator(np.sort(x_upper), y_upper[np.argsort(x_upper)])
    f_lower = PchipInterpolator(np.sort(x_lower), y_lower[np.argsort(x_lower)])
    
    return f_upper, f_lower


def close_trailing_edge(xu, yu, xl, yl):
    """
    Corrige duplicatas no bordo de fuga e garante fechamento (1.0, 0.0).
    """
    # Força o fechamento em x=1.0
    if abs(xu[0] - 1.0) < 1e-6:
        xu[0], yu[0] = 1.0, 0.0
    if abs(xl[-1] - 1.0) < 1e-6:
        xl[-1], yl[-1] = 1.0, 0.0
    return xu, yu, xl, yl


def morph_airfoils(file1, file2, interpolation_steps, num_points_per_surface=100):
    """
    Gera perfis intermediários entre dois aerofólios com base em uma lista 
    de pesos de interpolação [("nome", peso_t)] e grava em formato .dat 
    compatível com QBlade.
    
    Args:
        file1 (str): Caminho para o arquivo do Perfil 1 (peso t=0.0)
        file2 (str): Caminho para o arquivo do Perfil 2 (peso t=1.0)
        interpolation_steps (list): Uma lista de tuplas. 
                                    Formato: [("nome_passo_1", t_1), ("nome_passo_2", t_2), ...]
                                    Ex: [("rR_0.25", 0.06), ("rR_0.30", 0.16)]
        num_points_per_surface (int): Número de pontos por superfície (extradorso/intradorso).
    """
    h1, x1, y1 = parse_airfoil(file1)
    h2, x2, y2 = parse_airfoil(file2)

    # Normalização
    def normalize(x, y):
        x0, x1_max = np.min(x), np.max(x)
        # Evita divisão por zero se o aerofólio já estiver normalizado
        chord = x1_max - x0
        if chord < 1e-6:
            chord = 1.0
        return (x - x0) / chord, y / chord

    x1, y1 = normalize(x1, y1)
    x2, y2 = normalize(x2, y2)

    f1u, f1l = create_interpolators(x1, y1)
    f2u, f2l = create_interpolators(x2, y2)

    # Malha comum (x de 0 a 1) com distribuição cosinoidal
    s = np.linspace(0.0, np.pi, num_points_per_surface)
    x_common = (1.0 - np.cos(s)) / 2.0

    y1u, y1l = f1u(x_common), f1l(x_common)
    y2u, y2l = f2u(x_common), f2l(x_common)

    # Diretório de saída
    name1 = os.path.splitext(os.path.basename(file1))[0].replace("seligdatfile.", "")
    name2 = os.path.splitext(os.path.basename(file2))[0].replace("seligdatfile.", "")
    out_dir = f"{name1}_{name2}_{len(interpolation_steps)}_interpolados"
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n📁 Salvando arquivos no diretório: ./{out_dir}\n")

    # --- LOOP MODIFICADO ---
    # Itera sobre a lista de passos e pesos fornecida
    for step_name, t in interpolation_steps:
        
        # t é o peso para o perfil 2 (file2)
        # (1-t) é o peso para o perfil 1 (file1)
        yu = (1 - t) * y1u + t * y2u
        yl = (1 - t) * y1l + t * y2l

        xu, xl = x_common, x_common
        
        # Garante que o bordo de fuga esteja fechado
        xu, yu, xl, yl = close_trailing_edge(xu, yu, xl, yl)

        # Combina Extradorso (invertido) e Intradorso (removendo o primeiro ponto duplicado)
        # Ordem: TE -> LE -> TE
        x_all = np.concatenate([xu[::-1], xl[1:]])
        y_all = np.concatenate([yu[::-1], yl[1:]])

        # Garante fechamento final do TE (algumas interpolações podem falhar)
        if not np.allclose([x_all[-1], y_all[-1]], [1.0, 0.0], atol=1e-6):
            x_all[-1], y_all[-1] = 1.0, 0.0

        # Gera arquivo .dat compatível
        # --- NOME DO ARQUIVO MODIFICADO ---
        filename = f"{name1}_{name2}_{step_name}.dat"
        path = os.path.join(out_dir, filename)
        
        with open(path, 'w') as f:
            # Escreve o header (nome do perfil)
            f.write(f"{name1}_{name2}_morph_{step_name}\n")
            # Escreve os pontos
            for x, y in zip(x_all, y_all):
                f.write(f"{x:.6f} {y:.6f}\n")

        print(f"✅ Gerado: {path} (Peso E63: {1-t:.2f}, Peso ClarkY: {t:.2f})")

    print("\n✅ Interpolação concluída com sucesso.\n")


# Execução principal
if __name__ == "__main__":
    # Perfil 1 (t=0.0) e Perfil 2 (t=1.0)
    arquivo1 = "data/seligdatfile.e63.txt"
    arquivo2 = "data/seligdatfile.naca4412.txt"
    #arquivo2 = "data/seligdatfile.clarkY.txt"

    # --- LISTA DE PASSOS DE INTERPOLAÇÃO (PESOS) ---
    # Baseado no intervalo real [0.22, 0.72] para 10x7E
    # t = (r_atual - r_inicio_interp) / (r_fim_interp - r_inicio_interp)
    # t = (r_atual - 0.22) / (0.72 - 0.22) = (r_atual - 0.22) / 0.50
    
    pesos_interpolacao = [
        # ("Nome da Seção", (r_atual - 0.22) / 0.50)
        ("rR_0.25", (0.25 - 0.22) / 0.50),  # t = 0.06
        ("rR_0.30", (0.30 - 0.22) / 0.50),  # t = 0.16
        ("rR_0.35", (0.35 - 0.22) / 0.50),  # t = 0.26
        ("rR_0.40", (0.40 - 0.22) / 0.50),  # t = 0.36
        ("rR_0.45", (0.45 - 0.22) / 0.50),  # t = 0.46
        ("rR_0.50", (0.50 - 0.22) / 0.50),  # t = 0.56
        ("rR_0.55", (0.55 - 0.22) / 0.50),  # t = 0.66
        ("rR_0.60", (0.60 - 0.22) / 0.50),  # t = 0.76
        ("rR_0.65", (0.65 - 0.22) / 0.50),  # t = 0.86
        ("rR_0.70", (0.70 - 0.22) / 0.50)   # t = 0.96
    ]



    # --- PARÂMETROS EXTRAÍDOS DO ARQUIVO PE0 de 27x13E ---
    # r/R inicial (3.52 / 13.50) = 0.2607
    # r/R final   (7.80 / 13.50) = 0.5778
    # Intervalo = 0.3171
    
    start_rR = 0.2607
    end_rR = 0.5778
    interval = end_rR - start_rR
    
    # Lista de estações presentes no seu arquivo de saída (APC27x13E_pre_interpolete_change.txt)
    # Apenas as estações dentro do intervalo [0.2607, 0.5778] precisam de interpolação.
    pesos_interpolacao_27x13E = [
        # ("Nome da Seção", (r_atual - start_rR) / interval)
        ("rR_0.30", (0.30 - start_rR) / interval),  # t ≈ 0.124
        ("rR_0.35", (0.35 - start_rR) / interval),  # t ≈ 0.282
        ("rR_0.40", (0.40 - start_rR) / interval),  # t ≈ 0.439
        ("rR_0.45", (0.45 - start_rR) / interval),  # t ≈ 0.597
        ("rR_0.50", (0.50 - start_rR) / interval),  # t ≈ 0.755
        ("rR_0.55", (0.55 - start_rR) / interval)   # t ≈ 0.912
    ]

    # ----------

    # Chama a função principal com a lista de pesos
    morph_airfoils(arquivo1, 
                   arquivo2, 
                   pesos_interpolacao_27x13E, 
                   num_points_per_surface=80)