import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- CSS AVANÇADO (VISUAL PRO) ---
st.markdown("""
    <style>
        /* Importando Fonte Moderna (Poppins) */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

        /* Variáveis da Paleta CX Data */
        :root {
            --cx-lilac: #dbbfff;
            --cx-neon-green: #bef533;
            --cx-neon-pink: #ff43c0;
            --cx-blue-purple: #7371ff;
            --cx-dark: #1e1e1e;
            --cx-bg: #fafafa;
            --cx-card-bg: #ffffff;
        }

        /* Aplicando a Fonte em Tudo */
        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            color: var(--cx-dark);
        }

        /* Fundo Geral */
        .stApp {
            background-color: var(--cx-bg);
        }

        /* --- BARRA LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: var(--cx-card-bg);
            border-right: 1px solid rgba(0,0,0,0.05);
            box-shadow: 4px 0 15px rgba(0,0,0,0.02);
        }
        
        /* Títulos da Sidebar */
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 {
            color: var(--cx-blue-purple) !important;
            font-weight: 600;
        }

        /* --- OBJETIVOS (EXPANDERS) --- */
        /* Estilo do cabeçalho do Objetivo fechado/aberto */
        .streamlit-expanderHeader {
            background-color: white;
            border-radius: 12px;
            border: 1px solid #eee;
            box-shadow: 0 2px 5px rgba(0,0,0,0.03);
            transition: all 0.3s ease;
            font-weight: 600;
            color: var(--cx-blue-purple);
        }
        .streamlit-expanderHeader:hover {
            border-color: var(--cx-blue-purple);
            color: var(--cx-blue-purple);
            background-color: #fefefe;
        }
        /* Corpo do Expander */
        div[data-testid="stExpander"] {
            border: none;
            background-color: transparent;
        }

        /* --- CARDS DOS KRs (A Mágica Acontece Aqui) --- */
        /* Container com borda vira um Card Flutuante */
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"] {
            border: none !important; /* Remove a borda padrão feia */
            border-left: 5px solid var(--cx-blue-purple) !important; /* Borda lateral colorida */
            background-color: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            
            /* Sombra Suave */
            box-shadow: 0 4px 6px rgba(0,0,0,0.04);
            
            /* Transição para Animação */
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        /* Efeito Hover (Levitar) */
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"]:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(115, 113, 255, 0.15); /* Sombra roxa suave */
        }

        /* Título do KR */
        div[data-testid="stContainer"] p {
            font-size: 1rem;
            font-weight: 500;
        }

        /* --- BARRA DE PROGRESSO NEON --- */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, var(--cx-neon-green) 0%, #d4ff5e 100%);
            border-radius: 10px;
            height: 12px !important;
        }
        .stProgress > div > div > div {
            background-color: #f0f0f0; /* Fundo da barra vazio */
            border-radius: 10px;
            height: 12px !important;
        }

        /* --- BOTÕES --- */
        /* Botão Primário (Adicionar, Salvar) */
        button[kind="secondary"] {
            border: 1px solid var(--cx-blue-purple);
            color: var(--cx-blue-purple);
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s;
        }
        button[kind="secondary"]:hover {
            background-color: var(--cx-blue-purple);
            color: white !important;
            border-color: var(--cx-blue-purple);
        }
        /* Botão de Excluir (Lixeira) */
        button[title="Excluir este Objetivo"] {
            border-color: #ffcccc !important;
            color: red !important;
        }
        button[title="Excluir este Objetivo"]:hover {
            background-color: red !important;
            color: white !important;
        }

        /* --- INPUTS --- */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            background-color: #f9f9f9;
        }
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus {
            border-color: var(--cx-blue-purple);
            box-shadow: 0 0 0 1px var(--cx-blue-purple);
            background-color: white;
        }

        /* --- ABAS (TABS) --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            border-bottom: none;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: white;
            border-radius: 20px; /* Pílulas arredondadas */
            border: 1px solid #eee;
            padding: 0 20px;
            font-weight: 500;
            color: #888;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--cx-blue-purple) !important;
            color: white !important;
            border: none;
            box-shadow: 0 4px 10px rgba(115, 113, 255, 0.3);
        }

        /* Ajuste fino para Dataframes */
        div[data-testid="stDataFrame"] {
            border: 1px solid #eee;
            border-radius: 8px;
            overflow: hidden;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]
LOGO_FILE = "cx_CXdata_LOGO-positiva.png" 

# --- 3. FUNÇÕES DE DADOS ---

def carregar_dados_seguro():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=[
            'Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 
            'Status', 'Responsável', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
        ])
    try:
        df = pd.read_csv(DATA_FILE)
        text_cols = ['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 'Status', 'Responsável']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '').fillna('')
        
        if 'Prazo' in df.columns:
            df['Prazo'] = pd.to_datetime(df['Prazo'], errors='coerce')
        
        num_cols = ['Avanço', 'Alvo', 'Progresso (%)']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        return pd.DataFrame()

def carregar_departamentos():
    if os.path.exists(DEPT_FILE):
        try:
            return pd.read_csv(DEPT_FILE)['Departamento'].tolist()
        except:
            pass 
    padrao = ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]
    pd.DataFrame(padrao, columns=['Departamento']).to_csv(DEPT_FILE, index=False)
    return padrao

def salvar_departamentos(lista_deptos):
    pd.DataFrame(lista_deptos, columns=['Departamento']).to_csv(DEPT_FILE, index=False)

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0:
            return min(max(av / al, 0.0), 1.0)
        return 0.0
    except:
        return 0.0

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        df_exp['Prazo'] = df_exp['Prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False, sheet_name='OKRs')
    return output.getvalue()

# --- 4. INICIALIZAÇÃO DA MEMÓRIA ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = carregar_dados_seguro()

if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

# --- 5. TELA DE LOGIN ---
def check_password():
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Login")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "admin123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

# --- 6. APLICAÇÃO PRINCIPAL ---
if check_password():
    st.title("Painel de OKRs")

    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- MENU LATERAL ---
    with st.sidebar:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, use_column_width=True)
        else:
            st.markdown(f"<h2 style='text-align: center; color: #7371ff; font-weight:700;'>CX Data</h2>", unsafe_allow_html=True)
            
        st.markdown("### ⚙️ Configurações") # Markdown para usar a fonte nova
        
        with st.expander("Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo:")
                if st.form_submit_button("Adicionar"):
                    if novo and novo not in lista_deptos:
                        lista_deptos.append(novo)
                        salvar_departamentos(lista_deptos)
                        st.rerun()
            rm_dept = st.selectbox("Remover:", ["..."] + lista_deptos)
            if st.button("Remover"):
                if rm_dept != "...":
                    lista_deptos.remove(rm_dept)
                    salvar_departamentos(lista_deptos)
                    st.rerun()

        st.divider()
        
        st.markdown("### 🚀 Novo Objetivo")
        with st.form("quick_add"):
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Objetivo Macro")
            if st.form_submit_button("Criar Objetivo"):
                if o:
                    novo_okr = {
                        'Departamento': d, 'Objetivo': o, 'Resultado Chave (KR)': '',
                        'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                        'Prazo': pd.to_datetime(date.today()), 'Tarefa': '', 'Responsável': ''
                    }
                    st.session_state['df_master'] = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                    st.rerun()
                else:
                    st.warning("Digite um nome para o objetivo.")

    # --- ÁREA PRINCIPAL ---
    if df.empty:
        st.info("Comece criando um Objetivo no menu lateral.")
    else:
        depts = sorted(list(set(df['Departamento'].unique()) | set(lista_deptos)))
        abas = st.tabs(depts)
        
        for i, depto in enumerate(depts):
            with abas[i]:
                df_d = df[df['Departamento'] == depto]
                if df_d.empty:
                    st.caption("Sem dados.")
                    continue
                
                # --- HIERARQUIA 1: OBJETIVOS ---
                objs = [x for x in df_d['Objetivo'].unique() if x]
                for obj in objs:
                    mask_obj = (df['Departamento'] == depto) & (df['Objetivo'] == obj)
                    
                    mask_validos = mask_obj & (df['Resultado Chave (KR)'] != '')
                    if not df[mask_validos].empty:
                        prog_obj = df[mask_validos]['Progresso (%)'].mean()
                    else:
                        prog_obj = 0.0

                    if pd.isna(prog_obj): prog_obj = 0.0
                    prog_obj = max(0.0, min(1.0, float(prog_obj)))
                    
                    label_obj = f"{obj}  |  📊 {int(prog_obj*100)}%"
                    
                    with st.expander(label_obj, expanded=True):
                        
                        c_edit_obj, c_del_obj = st.columns([5, 1])
                        with c_edit_obj:
                            new_name = st.text_input("Nome do Objetivo", value=obj, key=f"n_o_{depto}_{obj}", label_visibility="collapsed")
                            if new_name != obj:
                                st.session_state['df_master'].loc[mask_obj, 'Objetivo'] = new_name
                                st.rerun()
                        with c_del_obj:
                            if st.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir este Objetivo"):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                st.rerun()

                        st.markdown("##### 🗝️ Resultados Chave (KRs)")
                        
                        krs = [x for x in df[mask_obj]['Resultado Chave (KR)'].unique() if x]
                        
                        if not krs:
                            st.info("Nenhum KR criado ainda. Adicione o primeiro abaixo.")

                        for kr in krs:
                            mask_kr = mask_obj & (df['Resultado Chave (KR)'] == kr)
                            df_kr = df[mask_kr] 
                            
                            prog_kr = df_kr['Progresso (%)'].mean()
                            if pd.isna(prog_kr): prog_kr = 0.0
                            prog_kr = max(0.0, min(1.0, float(prog_kr)))

                            with st.container(border=True):
                                c_title, c_bar = st.columns([3, 1])
                                
                                with c_title:
                                    # Usando markdown com estilo inline para o título do KR
                                    st.markdown(f"<span style='font-size:1.1rem; color:#7371ff; font-weight:600;'>{kr}</span>", unsafe_allow_html=True)
                                    new_kr = st.text_input("Editar nome do KR", value=kr, key=f"r_k_{depto}_{obj}_{kr}", label_visibility="collapsed")
                                    if new_kr != kr:
                                        st.session_state['df_master'].loc[mask_kr, 'Resultado Chave (KR)'] = new_kr
                                        st.rerun()
                                
                                with c_bar:
                                    st.progress(prog_kr, text=f"**{int(prog_kr*100)}%**")
                                
                                st.markdown("<div style='margin-top:10px; font-size:0.9rem; font-weight:500;'>🔻 Tarefas & Ações</div>", unsafe_allow_html=True)
                                
                                col_cfg = {
                                    "Progresso (%)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                                    "Status": st.column_config.SelectboxColumn(options=OPCOES_STATUS, required=True),
                                    "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Departamento": None, "Objetivo": None, "Resultado Chave (KR)": None
                                }
                                
                                unique_key = f"edit_{hash(depto + obj + kr)}"
                                df_edit = st.data_editor(
                                    df_kr, 
                                    column_config=col_cfg, 
                                    use_container_width=True, 
                                    num_rows="dynamic",
                                    key=unique_key
                                )

                                if not df_edit.equals(df_kr):
                                    df_edit['Progresso (%)'] = df_edit.apply(calcular_progresso, axis=1)
                                    df_edit['Departamento'] = depto
                                    df_edit['Objetivo'] = obj
                                    df_edit['Resultado Chave (KR)'] = kr
                                    
                                    idxs = df_kr.index
                                    st.session_state['df_master'] = st.session_state['df_master'].drop(idxs)
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], df_edit], ignore_index=True)
                                    
                                    st.session_state['df_master'] = st.session_state['df_master'].sort_values(
                                        by=['Departamento', 'Objetivo', 'Resultado Chave (KR)']
                                    ).reset_index(drop=True)
                                    
                                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                    st.rerun()

                        st.markdown("")
                        with st.popover("➕ Novo KR neste Objetivo"):
                            nk = st.text_input("Nome do KR", key=f"nk_{obj}")
                            if st.button("Criar", key=f"bk_{obj}"):
                                if nk:
                                    dummy = {
                                        'Departamento': depto, 'Objetivo': obj, 'Resultado Chave (KR)': nk,
                                        'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                                        'Prazo': pd.to_datetime(date.today()), 'Tarefa': 'Nova Tarefa', 'Responsável': ''
                                    }
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([dummy])], ignore_index=True)
                                    
                                    st.session_state['df_master'] = st.session_state['df_master'].sort_values(
                                        by=['Departamento', 'Objetivo', 'Resultado Chave (KR)']
                                    ).reset_index(drop=True)
                                    
                                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                    st.rerun()
    
    # --- RODAPÉ COM EXPORTAÇÃO ---
    st.markdown("---")
    with st.expander("📂 Exportar Dados"):
        st.dataframe(st.session_state['df_master'], use_container_width=True)
        st.download_button(
            "📥 Baixar Excel Completo",
            converter_para_excel(st.session_state['df_master']),
            "okrs_imobanco.xlsx"
        )
