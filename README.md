# Projeto Aerodinâmica XFoil

Este repositório contém scripts para interpolação de aerofólios, geração de arquivos `.dat` de perfis intermediários e execução em lote do XFoil para gerar polares que podem ser usados em MATLAB.

> Se você baixou este projeto do GitHub como um arquivo `.zip`, extraia todo o conteúdo para uma pasta local antes de seguir os passos abaixo. Em geral, use o botão `Code -> Download ZIP` e depois clique com o botão direito no arquivo `.zip` para descompactar.
>
> Todos os comandos `cd` abaixo assumem que o repositório foi descompactado em uma pasta local. Substitua `C:\Users\pedro\Downloads\multiperfil_xfoil\projeto-aerodinamica` pelo caminho correto da sua extração. (Ao obter o .zip, o arquivo tem nome  projeto-aerodinamica-main)

## 1. Estrutura do repositório

- `app/`
  - `morph_airfoil.py`: gera perfis interpolados entre `e63` e `naca4412`.
  - `rodar_simulação_neg_posit.py`: script principal que roda o XFoil, coleta coeficientes e faz extrapolação.
  - `batch_xfoil_to_mat.py`: processa arquivos `.dat` gerados pelo `morph_airfoil.py` e salva `.mat` para MATLAB.
  - `teste.py`: teste rápido para validar se o pacote `xfoil` está configurado.
- `requirements.txt`: lista de dependências do Python necessárias.
- `app/data/`: arquivos Selig dos perfis originais + resultados prévios para comparação.

## 2. Pré-requisitos

Recomendado usar um ambiente Conda ou venv Python.

Requisitos principais:
- Python 3.7 ou compatível
- `numpy`
- `scipy`
- `xfoil`
- `matplotlib` (opcional para visualização)

> No Windows, prefira rodar os comandos no CMD/Powershell adequado ao ambiente Python com XFoil.

## 3. Configurando o ambiente em outro computador

### 3.1 Usando Conda

1. Abra o terminal (CMD ou PowerShell).
2. Crie ou ative o ambiente Conda:

```powershell
conda create -n xfoil_py37 python=3.7 -y
conda activate xfoil_py37
```

3. Instale as dependências do `requirements.txt`:

```powershell
cd <caminho\para\pasta\projeto-aerodinamica>
pip install -r requirements.txt
```

4. Caso o pacote `xfoil` não esteja disponível diretamente, instale-o via:

```powershell
pip install xfoil
```

### 3.2 Usando venv Python

1. Crie o ambiente virtual:

```powershell
python -m venv venv
```

2. Ative o ambiente:

```powershell
.\venv\Scripts\activate
```

3. Instale dependências:

```powershell
pip install -r requirements.txt
```

4. Se necessário, instale o `xfoil` manualmente:

```powershell
pip install xfoil
```

## 4. Verificando a instalação do XFoil

Execute o teste inicial para confirmar que o pacote `xfoil` está funcionando:

```powershell
cd <caminho\para\pasta\projeto-aerodinamica>\app
python teste.py
```

Se o ambiente estiver correto, o script `teste.py` deve importar `xfoil`, criar uma instância `XFoil()` e carregar o perfil `naca0012` sem erro.

## 5. Gerando os perfis interpolados

O script `app/morph_airfoil.py` lê os perfis originais em `app/data/` e gera perfis intermediários entre `e63` e `naca4412`.

### 5.1 Perfis base

Os perfis fonte são:
- `app/data/seligdatfile.e63.txt`
- `app/data/seligdatfile.naca4412.txt`

### 5.2 Executar a interpolação

No mesmo diretório `app/`, execute:

```powershell
python morph_airfoil.py
```

Isso irá gerar uma pasta com os arquivos `.dat` interpolados, por exemplo:
- `e63_naca4412_6_interpolados/`
- `e63_naca4412_10_interpolados2/`
- `e63_naca4412_10_interpolados10x7e/`
- `e63_naca4412_6_interpolados27x13e/`

Os nomes podem variar conforme a configuração interna do script.em 
`linha 96 :   out_dir = f"{name1}_{name2}_{len(interpolation_steps)}_interpolados" `

### 5.3 Ajustar os pesos de interpolação

No final de `morph_airfoil.py`, há duas listas de pesos:
- `pesos_interpolacao`: usa a faixa fixa `[0.22, 0.72]` para gerar estações de 0.25 a 0.70, baseado em `start_rR` e `end_rR` do arquivo PE0 do 10x7E.
- `pesos_interpolacao_27x13E`: usa o intervalo real de `r/R` baseado em `start_rR` e `end_rR` do arquivo PE0 do 27x13E.

Altere a lista usada na chamada `morph_airfoils(...)` para gerar os perfis desejados.

## 6. Gerando as polares para MATLAB

Após gerar os arquivos `.dat` interpolados, use o `batch_xfoil_to_mat.py` para processá-los e criar arquivos `.mat` com a struct `polar`.
Segue o exemplo gerando os perfis para 10x7E usando a lista de `pesos_interpolacao`

### 6.1 Requisitos de entrada

- Coloque os arquivos `.dat` interpolados em uma subpasta de `app/`, como:
  - `app/e63_naca4412_10_interpolados/`

- Ajuste a variável `GEOMETRY_FOLDER` em `app/batch_xfoil_to_mat.py` para o nome da pasta que contém esses `.dat`.
- Ajuste `GEOMETRY_PATTERN` caso seus arquivos tenham nome diferente.

### 6.2 Executar o batch

```powershell
cd C:\Users\pedro\Downloads\multiperfil_xfoil\projeto-aerodinamica\app
python batch_xfoil_to_mat.py
```

O script:
- percorre cada `.dat` da pasta definida
- roda XFoil para os valores de Reynolds configurados
- extrapola até a faixa de `-90` a `+90` graus
- interpola os resultados numa grade fixa de ângulos
- salva os resultados em arquivos `.mat`

### 6.3 Saída esperada

Para cada perfil `.dat`, será criado um `.mat` com uma variável MATLAB chamada `polar` contendo campos:
- `cl`: matriz com colunas `[alpha, Cl(Re1), Cl(Re2), ...]`
- `cd`: matriz com colunas `[alpha, Cd(Re1), Cd(Re2), ...]`

Esses arquivos `.mat` podem ser carregados no MATLAB para análise ou uso em scripts de pós-processamento.

## 7. Fluxo completo de uso

1. Configurar ambiente Python (`conda` ou `venv`).
2. Instalar dependências com `pip install -r requirements.txt`.
3. Executar `app/teste.py` para verificar o pacote `xfoil`.
4. Executar `app/morph_airfoil.py` para gerar perfis `.dat` interpolados.
5. Ajustar `app/batch_xfoil_to_mat.py` e executar para gerar `.mat`.
6. Usar os `.mat` gerados como entrada no código MATLAB.
7. A pasta gerada contendo `.mat`, exemplo `e63_naca4412_10_interpolados` pode ser adicionada a pasta Data do código MATLAB, com a nomenclatura atualizada em init e na coluna AIRFOIL_MAP da geometria usada para corretamente referencias a pasta gerada. 

## 8. Dicas rápidas

- Se `teste.py` falhar, verifique se o ambiente virtual/Conda está ativado corretamente e se `pip install xfoil` foi concluído sem erros.
- Se o XFoil não convergir para algum perfil, o `batch_xfoil_to_mat.py` preenche essa coluna com `NaN` e continua.
- Caso queira outro intervalo de ângulos ou Reynolds, ajuste `ALPHA_GRID` e `REYNOLDS_LIST` em `batch_xfoil_to_mat.py`.

## 9. Contato

Use o repositório como base para experimentos aerodinâmicos e integração com MATLAB. Ajuste os pesos de interpolação e a resolução da malha conforme necessário para seu projeto.
