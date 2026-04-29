import numpy as np
import matplotlib.pyplot as plt
from xfoil import XFoil
from xfoil.model import Airfoil
import os
import time

# =============================================================================
# FUNÇÃO: RODAR O XFOIL (PONTO A PONTO COM SKIP DE 3 FALHAS CONSECUTIVAS)
# =============================================================================
def rodar_xfoil_pre_stall(arquivo_geometria, reynolds, angulo_inicio, angulo_fim, passo, max_iteracoes=100):
    """
    Roda o XFOIL partindo de Alpha=0.
    1. Faz varredura Positiva (0 até angulo_fim).
    2. Reseta.
    3. Faz varredura Negativa (-passo até angulo_inicio).
    Utiliza estratégia de resgate (micro-passos) se encontrar falhas.
    """
    print(f"\n--- Iniciando Simulação XFOIL (Estratégia 0 -> Pontas) ---")
    print(f"  Perfil: {arquivo_geometria}")
    print(f"  Reynolds (Re): {reynolds:.2e}")

    if not os.path.exists(arquivo_geometria):
        print(f"Erro: Arquivo de geometria '{arquivo_geometria}' não encontrado.")
        return None, None, None

    try:
        coords = np.loadtxt(arquivo_geometria, skiprows=1)
        perfil = Airfoil(coords[:, 0], coords[:, 1])

        xf = XFoil()
        xf.airfoil = perfil
        xf.repanel(n_nodes=240) # Aumentado levemente para robustez
        xf.Re = reynolds
        xf.M = 0.0
        
        # Listas para guardar resultados parciais
        # Positivos (inclui o 0)
        res_pos = {'a': [], 'cl': [], 'cd': []}
        # Negativos (exclui o 0, começa em -passo)
        res_neg = {'a': [], 'cl': [], 'cd': []}

        # ====================================================================
        # VARREDURA POSITIVA (0 -> FIM)
        # ====================================================================
        print(f"  -> Iniciando varredura POSITIVA: 0.00 a {angulo_fim}...")
        
        # Garante que começamos limpos em 0
        xf.max_iter = max_iteracoes + 50 # Extra força no 0
        try:
            xf.a(0) # 'Esquenta' o solver no 0
        except:
            pass

        angulos_pos = np.arange(0, angulo_fim + passo/10, passo)
        last_converged = None
        consecutive_failures = 0

        for angle in angulos_pos:
            sucesso = False
            xf.max_iter = max_iteracoes
            
            # Tentativa Normal
            try:
                cl, cd, cm, cp = xf.a(angle)
                if np.isfinite(cl) and np.isfinite(cd):
                    sucesso = True
            except:
                pass

            # Tentativa de Resgate (Micro-passos)
            if not sucesso and last_converged is not None:
                print(f"     ! Falha em {angle:.2f}°. Tentando resgate (micro-passos)...")
                # Micro-passos de 0.05
                micro_angles = np.arange(last_converged + 0.05, angle + 0.001, 0.05)
                resgate_ok = True
                
                # Tenta re-estabilizar no anterior
                try: xf.a(last_converged)
                except: pass

                for ma in micro_angles:
                    try:
                        cl_m, cd_m, _, _ = xf.a(ma)
                        if not (np.isfinite(cl_m) and np.isfinite(cd_m)):
                            resgate_ok = False; break
                    except:
                        resgate_ok = False; break
                
                if resgate_ok:
                    cl, cd = cl_m, cd_m # Pega o último calculado
                    sucesso = True
                    print(f"     -> Resgate OK em {angle:.2f}!")

            # Armazenar ou Desistir
            if sucesso:
                res_pos['a'].append(angle)
                res_pos['cl'].append(cl)
                res_pos['cd'].append(cd)
                last_converged = angle
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"     -> 3 falhas consecutivas no lado positivo. Parando subida em {angle:.2f}°.")
                    break # Para o loop positivo, mas NÃO o código todo

        # ====================================================================
        # RE-INICIALIZAÇÃO PARA O LADO NEGATIVO
        # ====================================================================
        # É crucial limpar o histórico de turbulência dos ângulos altos positivos
        # antes de começar a descer para os negativos.
        print(f"  -> Reinicializando solver para varredura NEGATIVA...")
        # reset_bl() não existe em todos wrappers, então forçamos convergência em 0 de novo
        xf.Re = reynolds # Às vezes ajuda a "resetar" internos reatribuindo
        try:
            xf.a(0) 
        except:
            pass 

        # ====================================================================
        # VARREDURA NEGATIVA (-PASSO -> INICIO)
        # ====================================================================
        print(f"  -> Iniciando varredura NEGATIVA: -{passo} a {angulo_inicio}...")
        
        # Cria array descendente: -0.5, -1.0, -1.5 ...
        angulos_neg = np.arange(-passo, angulo_inicio - passo/10, -passo)
        
        # Nosso ponto de partida seguro agora é o 0 (que acabamos de re-calcular ou assumimos bom)
        last_converged = 0.0 
        consecutive_failures = 0

        for angle in angulos_neg:
            sucesso = False
            xf.max_iter = max_iteracoes

            try:
                cl, cd, cm, cp = xf.a(angle)
                if np.isfinite(cl) and np.isfinite(cd):
                    sucesso = True
            except:
                pass

            # Resgate (Micro-passos Descendentes)
            if not sucesso and last_converged is not None:
                print(f"     ! Falha em {angle:.2f}°. Tentando resgate (micro-passos)...")
                # Micro-passos negativos: ex: de 0.0 indo para -0.5 -> 0.0, -0.05, -0.10...
                # np.arange(start, stop, step) -> start=last-0.05, stop=angle-0.001
                micro_angles = np.arange(last_converged - 0.05, angle - 0.001, -0.05)
                resgate_ok = True
                
                try: xf.a(last_converged)
                except: pass

                for ma in micro_angles:
                    try:
                        cl_m, cd_m, _, _ = xf.a(ma)
                        if not (np.isfinite(cl_m) and np.isfinite(cd_m)):
                            resgate_ok = False; break
                    except:
                        resgate_ok = False; break
                
                if resgate_ok:
                    cl, cd = cl_m, cd_m
                    sucesso = True
                    print(f"     -> Resgate OK em {angle:.2f}!")

            if sucesso:
                res_neg['a'].append(angle)
                res_neg['cl'].append(cl)
                res_neg['cd'].append(cd)
                last_converged = angle
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"     -> 3 falhas consecutivas no lado negativo. Parando descida em {angle:.2f}°.")
                    break

        # ====================================================================
        # MONTAGEM FINAL DOS DADOS
        # ====================================================================
        # Precisamos inverter a lista negativa (está [-0.5, -1.0...]) para ficar crescente
        # e juntar com a positiva ([0.0, 0.5...])
        
        # Converte para numpy
        a_neg_arr = np.array(res_neg['a'])
        cl_neg_arr = np.array(res_neg['cl'])
        cd_neg_arr = np.array(res_neg['cd'])
        
        a_pos_arr = np.array(res_pos['a'])
        cl_pos_arr = np.array(res_pos['cl'])
        cd_pos_arr = np.array(res_pos['cd'])

        # Inverte ordem dos negativos para ficar crescente (-15 ... -0.5)
        # Nota: [::-1] inverte o array
        if len(a_neg_arr) > 0:
            a_neg_arr = a_neg_arr[::-1]
            cl_neg_arr = cl_neg_arr[::-1]
            cd_neg_arr = cd_neg_arr[::-1]

        # Concatena: Negativos (invertidos) + Positivos
        a_final = np.concatenate((a_neg_arr, a_pos_arr))
        cl_final = np.concatenate((cl_neg_arr, cl_pos_arr))
        cd_final = np.concatenate((cd_neg_arr, cd_pos_arr))

        if len(a_final) == 0:
             return None, None, None

        return a_final, cl_final, cd_final

    except Exception as e:
        print(f"Erro fatal no XFoil: {e}")
        return None, None, None



# =============================================================================
# FUNÇÃO DE EXTRAPOLAÇÃO PARA -90 a +90 GRAUS (Mesma da resposta anterior)
# =============================================================================
def extrapolate_full_range(alpha_deg_in, cl_in, cd_in, num_points_extrap=50):
    """
    Extrapola os dados de Cl e Cd para cobrir a faixa de -90 a +90 graus
    usando o método de Viterna-Montgomerie para ambos os lados (positivo e negativo).
    Retorna None, None, None se a extrapolação falhar por falta de dados válidos.
    """
    alpha_rad_in = np.deg2rad(alpha_deg_in)
    epsilon = 1e-12 # Para evitar divisões por zero

    # Garante que temos dados suficientes
    if alpha_deg_in is None or len(alpha_deg_in) < 2:
        print("Erro na extrapolação: Dados de entrada insuficientes.")
        return None, None, None

    # --- Extrapolação Lado Positivo ---
    print("\n--- Extrapolação Lado Positivo ---")
    positive_mask = alpha_deg_in >= 0
    if not np.any(positive_mask):
        print("Erro: Nenhum dado em ângulos positivos para extrapolação positiva.")
        # Tenta continuar só com o lado negativo se houver? Por enquanto, falha.
        return None, None, None
    alpha_pos = alpha_deg_in[positive_mask]
    cl_pos = cl_in[positive_mask]

    idx_stall_pos_local = np.argmax(cl_pos)
    alpha_stall_pos_deg = alpha_pos[idx_stall_pos_local]
    idx_stall_pos_global_list = np.where(alpha_deg_in == alpha_stall_pos_deg)[0]
    if len(idx_stall_pos_global_list) == 0: return None, None, None # Falha segura
    idx_stall_pos_global = idx_stall_pos_global_list[0]

    cl_stall_pos = cl_in[idx_stall_pos_global]
    cd_stall_pos = cd_in[idx_stall_pos_global]
    alpha_stall_pos_rad = alpha_rad_in[idx_stall_pos_global]

    print(f"  Ponto de Stall Positivo: Alpha={alpha_stall_pos_deg:.2f}, Cl={cl_stall_pos:.4f}, Cd={cd_stall_pos:.4f}")

    if not np.isfinite(cl_stall_pos) or not np.isfinite(cd_stall_pos):
        print("Erro: Valores inválidos no stall positivo.")
        return None, None, None

    CD_max_pos = 2.0
    B1_pos = CD_max_pos
    cos_alpha_stall_pos = np.cos(alpha_stall_pos_rad)
    if np.abs(cos_alpha_stall_pos) < epsilon: B2_pos = 0.0
    else: B2_pos = (cd_stall_pos - B1_pos * np.sin(alpha_stall_pos_rad)**2) / cos_alpha_stall_pos

    A1_pos = B1_pos / 2.0
    sin_alpha_stall_pos = np.sin(alpha_stall_pos_rad)
    if np.abs(sin_alpha_stall_pos) < epsilon: A2_pos = 0.0
    else:
        denominator_pos = (np.cos(alpha_stall_pos_rad)**2) / (sin_alpha_stall_pos + epsilon)
        if np.abs(denominator_pos) < epsilon: A2_pos = 0.0
        else: A2_pos = (cl_stall_pos - A1_pos * np.sin(2 * alpha_stall_pos_rad)) / denominator_pos

    if not (np.isfinite(A1_pos) and np.isfinite(A2_pos) and np.isfinite(B1_pos) and np.isfinite(B2_pos)):
        print("Erro: Coeficientes de Montgomerie positivos inválidos.")
        return None, None, None

    alpha_extrap_pos_deg = np.linspace(alpha_stall_pos_deg, 90, num_points_extrap)
    alpha_extrap_pos_rad = np.deg2rad(alpha_extrap_pos_deg)
    cl_extrap_pos = A1_pos * np.sin(2 * alpha_extrap_pos_rad) + A2_pos * (np.cos(alpha_extrap_pos_rad)**2) / (np.sin(alpha_extrap_pos_rad) + epsilon)
    cd_extrap_pos = B1_pos * np.sin(alpha_extrap_pos_rad)**2 + B2_pos * np.cos(alpha_extrap_pos_rad)
    cd_extrap_pos = np.maximum(cd_extrap_pos, 0.0)

    # --- Extrapolação Lado Negativo ---
    print("\n--- Extrapolação Lado Negativo ---")
    negative_mask = alpha_deg_in <= 0
    if not np.any(negative_mask):
        print("Erro: Nenhum dado em ângulos negativos para extrapolação negativa.")
        return None, None, None
    alpha_neg = alpha_deg_in[negative_mask]
    cl_neg = cl_in[negative_mask]

    idx_stall_neg_local = np.argmin(cl_neg)
    alpha_stall_neg_deg = alpha_neg[idx_stall_neg_local]
    idx_stall_neg_global_list = np.where(alpha_deg_in == alpha_stall_neg_deg)[0]
    if len(idx_stall_neg_global_list) == 0: return None, None, None
    idx_stall_neg_global = idx_stall_neg_global_list[0]

    cl_stall_neg = cl_in[idx_stall_neg_global]
    cd_stall_neg = cd_in[idx_stall_neg_global]
    alpha_stall_neg_rad = alpha_rad_in[idx_stall_neg_global]

    print(f"  Ponto de Stall Negativo: Alpha={alpha_stall_neg_deg:.2f}, Cl={cl_stall_neg:.4f}, Cd={cd_stall_neg:.4f}")

    if not np.isfinite(cl_stall_neg) or not np.isfinite(cd_stall_neg):
        print("Erro: Valores inválidos no stall negativo.")
        return None, None, None

    CD_max_neg = 2.0
    B1_neg = CD_max_neg
    cos_alpha_stall_neg = np.cos(alpha_stall_neg_rad)
    if np.abs(cos_alpha_stall_neg) < epsilon: B2_neg = 0.0
    else: B2_neg = (cd_stall_neg - B1_neg * np.sin(alpha_stall_neg_rad)**2) / cos_alpha_stall_neg

    A1_neg = B1_neg / 2.0
    sin_alpha_stall_neg = np.sin(alpha_stall_neg_rad)
    if np.abs(sin_alpha_stall_neg) < epsilon: A2_neg = 0.0
    else:
        denominator_neg = (np.cos(alpha_stall_neg_rad)**2) / (sin_alpha_stall_neg - epsilon) # Subtrai epsilon
        if np.abs(denominator_neg) < epsilon: A2_neg = 0.0
        else: A2_neg = (cl_stall_neg - A1_neg * np.sin(2 * alpha_stall_neg_rad)) / denominator_neg

    if not (np.isfinite(A1_neg) and np.isfinite(A2_neg) and np.isfinite(B1_neg) and np.isfinite(B2_neg)):
        print("Erro: Coeficientes de Montgomerie negativos inválidos.")
        return None, None, None

    alpha_extrap_neg_deg = np.linspace(-90, alpha_stall_neg_deg, num_points_extrap)
    alpha_extrap_neg_rad = np.deg2rad(alpha_extrap_neg_deg)
    cl_extrap_neg = A1_neg * np.sin(2 * alpha_extrap_neg_rad) + A2_neg * (np.cos(alpha_extrap_neg_rad)**2) / (np.sin(alpha_extrap_neg_rad) - epsilon)
    cd_extrap_neg = B1_neg * np.sin(alpha_extrap_neg_rad)**2 + B2_neg * np.cos(alpha_extrap_neg_rad)
    cd_extrap_neg = np.maximum(cd_extrap_neg, 0.0)

    # --- Combina Tudo ---
    alpha_part1 = alpha_extrap_neg_deg[:-1]
    cl_part1 = cl_extrap_neg[:-1]
    cd_part1 = cd_extrap_neg[:-1]

    mask_xfoil_middle = (alpha_deg_in >= alpha_stall_neg_deg) & (alpha_deg_in <= alpha_stall_pos_deg)
    alpha_part2 = alpha_deg_in[mask_xfoil_middle]
    cl_part2 = cl_in[mask_xfoil_middle]
    cd_part2 = cd_in[mask_xfoil_middle]

    alpha_part3 = alpha_extrap_pos_deg[1:]
    cl_part3 = cl_extrap_pos[1:]
    cd_part3 = cd_extrap_pos[1:]

    alpha_full = np.concatenate((alpha_part1, alpha_part2, alpha_part3))
    cl_full = np.concatenate((cl_part1, cl_part2, cl_part3))
    cd_full = np.concatenate((cd_part1, cd_part2, cd_part3))

    # Garante ordenação e unicidade
    unique_indices = np.unique(alpha_full, return_index=True)[1]
    alpha_full = alpha_full[unique_indices]
    cl_full = cl_full[unique_indices]
    cd_full = cd_full[unique_indices]
    sort_indices_final = np.argsort(alpha_full)

    alpha_full = alpha_full[sort_indices_final]
    cl_full = cl_full[sort_indices_final]
    cd_full = cd_full[sort_indices_final]

    if not np.all(np.isfinite(cl_full)) or not np.all(np.isfinite(cd_full)):
        print("Erro: Resultados finais combinados contêm NaN/Inf.")
        return None, None, None

    print(f"  Extrapolação concluída. Faixa final: {alpha_full[0]:.2f} a {alpha_full[-1]:.2f} graus.")
    return alpha_full, cl_full, cd_full

# =============================================================================
# SCRIPT PRINCIPAL - COM LOOP DE REYNOLDS E SALVANDO ARQUIVO DE DADOS
# =============================================================================
if __name__ == "__main__":

    ARQUIVO_PERFIL =  'e63_naca4412_rR_0.70.dat'  #'seligdatfile.naca4412.txt'#seligdatfile.e63.txt'
    REYNOLDS_LIST = [2e4, 4.5e4, 7.5e4, 1e5, 2.5e5, 5e5, 7.5e5, 1e6]
    ANGULO_INICIO = -15.0 # Tenta um pouco mais negativo
    ANGULO_FIM = 20.0
    PASSO_ANGULO = 0.25
    MAX_ITERACOES_XFOIL = 500 # Mantém alto

    alpha_grid_final = np.linspace(-90, 90, 361) # Grid final para salvar os dados
    all_results = {} # Dicionário para guardar resultados por Re

    # forma padrãode salvamento 
    output_dir = os.path.join(f"perfil_extrapolado{ARQUIVO_PERFIL}", "reynolds_extrapolado")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Definir e criar a pasta de polares
    pasta_polares = os.path.join(f"perfil_extrapolado{ARQUIVO_PERFIL}", "polares")
    os.makedirs(pasta_polares, exist_ok=True)


    print("=============================================")
    print(f"Iniciando varredura de Reynolds para {ARQUIVO_PERFIL}")
    print(f"Reynolds a serem testados: {REYNOLDS_LIST}")
    print("=============================================")

    for reynolds_atual in REYNOLDS_LIST:

        print(f"\n======== PROCESSANDO Re = {reynolds_atual:.2e} ========")

        alpha_xfoil, cl_xfoil, cd_xfoil = rodar_xfoil_pre_stall(
            ARQUIVO_PERFIL,
            reynolds_atual,
            ANGULO_INICIO,
            ANGULO_FIM,
            PASSO_ANGULO,
            MAX_ITERACOES_XFOIL
        )

        # Requer pelo menos 5 pontos válidos E dados em ângulos positivos E negativos
        if (alpha_xfoil is None or len(alpha_xfoil) < 5 or
                not np.any(alpha_xfoil >= 0) or not np.any(alpha_xfoil <= 0)):
            print(f"\nSimulação do XFOIL para Re={reynolds_atual:.2e} falhou ou não produziu dados suficientes/ambos os lados. Pulando.")
            all_results[reynolds_atual] = None
            continue
        else:
            if len(alpha_xfoil) < 15:
                 print(f"\nAVISO (Re={reynolds_atual:.2e}): Número de pontos convergidos foi baixo ({len(alpha_xfoil)}).")

            try:
                alpha_full_range, cl_full_range, cd_full_range = extrapolate_full_range(
                    alpha_xfoil,
                    cl_xfoil,
                    cd_xfoil
                )

                if alpha_full_range is None:
                    raise Exception(f"Falha durante a extrapolação completa para Re={reynolds_atual:.2e}.")

                cl_interp_final = np.interp(alpha_grid_final, alpha_full_range, cl_full_range)
                cd_interp_final = np.interp(alpha_grid_final, alpha_full_range, cd_full_range)

                all_results[reynolds_atual] = {
                    'alpha': alpha_grid_final,
                    'cl': cl_interp_final,
                    'cd': cd_interp_final
                }

                # Plotagem (mantida para verificação)
                print("\n--- Gerando Gráficos de Verificação ---")
                plt.figure(figsize=(18, 6))
                plt.subplot(1, 3, 1)
                plt.plot(alpha_xfoil, cl_xfoil, 'bo', markersize=3, label='Dados XFOIL')
                plt.plot(alpha_grid_final, cl_interp_final, 'r-', linewidth=1, label='Completo (Interpolado)')
                plt.xlabel('Ângulo de Ataque (graus)'); plt.ylabel('$C_l$')
                plt.title(f'$C_l$ vs $\\alpha$ (Re={reynolds_atual:.1e})'); plt.legend(); plt.grid(True); plt.ylim(-2, 2.5)

                plt.subplot(1, 3, 2)
                plt.plot(alpha_xfoil, cd_xfoil, 'bo', markersize=3, label='Dados XFOIL')
                plt.plot(alpha_grid_final, cd_interp_final, 'r-', linewidth=1, label='Completo (Interpolado)')
                plt.xlabel('Ângulo de Ataque (graus)'); plt.ylabel('$C_d$')
                plt.title(f'$C_d$ vs $\\alpha$ (Re={reynolds_atual:.1e})'); plt.legend(); plt.grid(True); plt.ylim(0, 2.5)

                
                plt.subplot(1, 3, 3)
                plt.plot(cd_xfoil, cl_xfoil, 'bo', markersize=3, label='Dados XFOIL')
                plt.plot(cd_interp_final, cl_interp_final, 'r-', linewidth=1, label='Completo (Interpolado)')
                plt.xlabel('$C_d$'); plt.ylabel('$C_l$')
                plt.title(f'Polar ($C_l$ vs $C_d$, Re={reynolds_atual:.1e})'); plt.legend(); plt.grid(True); plt.xlim(0, 2.5); plt.ylim(-2, 2.5)
                
                plt.tight_layout()
                
                nome_arquivo_grafico = f'resultado_Re_{reynolds_atual:.1e}.png'
                caminho_completo = os.path.join(output_dir, nome_arquivo_grafico)
                plt.savefig(caminho_completo)
                print(f"Gráficos de verificação salvos como '{caminho_completo}'")
                plt.close('all')
                
            except Exception as e:
                print(f"\nOcorreu um erro durante a extrapolação ou plotagem para Re={reynolds_atual:.2e}: {e}")
                all_results[reynolds_atual] = None
                plt.close('all')

    # --- ETAPA 4: Salvar Dados Combinados em Arquivo .txt ---
    print("\n=============================================")
    print("Salvando dados combinados...")

    output_filename = f"polares_completas_{ARQUIVO_PERFIL}.txt"
    reynolds_validos = [re for re, result in all_results.items() if result is not None]

    if not reynolds_validos:
        print("Nenhum Reynolds produziu resultados válidos. Arquivo .txt não será gerado.")
    else:
        try:
            header_lines = [
                f"# Polares Completas para o Perfil: {ARQUIVO_PERFIL}",
                f"# Dados do XFOIL combinados com extrapolação Viterna-Montgomerie (-90 a +90 graus)",
                f"# Reynolds numbers incluídos: {['{:.1e}'.format(re) for re in reynolds_validos]}" # Formata os Re no cabeçalho
            ]
            col_names = ["Alpha(deg)"]
            # Adiciona nomes das colunas Cl
            for re in reynolds_validos:
                col_names.append(f"Cl_Re{re:.1e}")
            # Adiciona nomes das colunas Cd
            for re in reynolds_validos:
                col_names.append(f"Cd_Re{re:.1e}")
            header_lines.append("\t".join(col_names)) # Usa Tab como separador

            alpha_col = all_results[reynolds_validos[0]]['alpha']
            data_to_save = [alpha_col]
            for re in reynolds_validos:
                data_to_save.append(all_results[re]['cl'])
            for re in reynolds_validos:
                data_to_save.append(all_results[re]['cd'])

            data_matrix = np.column_stack(data_to_save)
            caminho_completo_p = os.path.join(pasta_polares, output_filename)
            np.savetxt(
                caminho_completo_p,  # Caminho atualizado
                data_matrix,
                header="\n".join(header_lines),
                delimiter='\t',
                fmt='%.6f',
                comments='' # Remove o '#' padrão do numpy nas linhas de dados
            )
            print(f"Dados salvos com sucesso em '{output_filename}'")

        except Exception as e:
            print(f"\nOcorreu um erro ao salvar o arquivo de dados combinados: {e}")

    print("\n=============================================")
    print("Processo concluído.")
    print("=============================================")