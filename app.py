import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="Gestão de OKR", 
    layout="wide", 
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# --- CSS ENTERPRISE (LIMPO E HARMONIOSO) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
            --primary: #7371ff;       
            --accent: #bef533;        
            --text-dark: #1e1e1e;
            --text-light: #6b7280;
            --bg-page: #f8f9fa;
            --bg-card: #ffffff;
            --border-radius: 10px;
        }

        /* Fonte Global */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: var(--text-dark);
            -webkit-font-smoothing: antialiased;
        }

        /* Fundo da Página */
        .stApp {
            background-color: var(--bg-page);
        }

        /* --- TEMA DOS INPUTS (Nativo com leve toque da marca) --- */
        /* Removemos as bordas pretas forçadas. Deixamos o Streamlit gerenciar, 
           mas ajustamos a cor de foco para o Azul da Marca (Primary) se possível */
        
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 8px;
        }
        
        /* Ajuste fino para o foco ficar na cor da marca (Azul) e não laranja */
        .stTextInput input:focus {
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 1px var(--primary) !important;
        }
        .stSelectbox div[data-baseweb="select"] > div:focus-within {
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 1px var(--primary) !important;
        }

        /* --- BARRA LATERAL --- */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-card);
            border-right: 1px solid rgba(0,0,0,0.05);
        }
        
        section[data-testid="stSidebar"] h3 {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-light);
            margin-top: 1.5rem;
            font-weight: 600;
        }

        /* --- ABAS (DEPARTAMENTOS) --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            border-bottom: 1px solid #eee;
            margin-bottom: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: auto;
            background-color: transparent;
            border: none;
            padding: 8px 0px; /* Sem padding lateral para ficar só o texto */
            margin-right: 15px;
            font-weight: 500;
            color: var(--text-light);
            border-bottom: 2px solid transparent;
            border-radius: 0;
        }
        .stTabs [aria-selected="true"] {
            color: var(--primary) !important;
            font-weight: 700 !important;
            border-bottom: 2px solid var(--primary) !important;
        }

        /* --- EXPANDERS (OBJETIVOS) --- */
        .streamlit-expanderHeader {
            background-color: var(--bg-card);
            border: 1px solid #eee;
            border-radius: var(--border-radius);
            padding: 1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            color: var(--text-dark);
            font-weight: 600;
        }
        .streamlit-expanderHeader:hover {
            border-color: var(--primary);
            color: var(--primary);
        }
        div[data-testid="stExpander"] {
            border: none;
            background: transparent;
        }

        /* --- KR CARDS --- */
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"] {
            background-color: var(--bg-card);
            border: 1px solid #f0f0f0 !important;
            border-left: 4px solid var(--primary) !important; /* Detalhe lateral */
            border-radius: var(--border-radius);
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.06);
        }
        
        div[data-testid="stContainer"] p {
            font-size: 0.95rem;
            color: var(--text-dark);
        }

        /* --- BARRA DE PROGRESSO --- */
        .stProgress { background-color: transparent; }
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, var(--accent) 0%, #a3d929 100%);
        }
        .stProgress > div > div > div {
            background-color: #f0f0f0;
            height: 8px !important;
            border-radius: 4px;
        }
        div[data-testid="stProgress"] + div {
            font-weight: 700;
            color: var(--text-dark);
            font-size: 0.85rem;
        }

        /* --- BOTÕES --- */
        button[kind="secondary"] {
            background-color: white;
            border: 1px solid #e0e0e0;
            color: var(--text-dark);
            border-radius: 8px;
            font-weight: 500;
            font-size: 0.85rem;
        }
        button[kind="secondary"]:hover {
            border-color: var(--primary);
            color: var(--primary);
            background-color: #f8f8ff;
        }
        /* Remove estilo do botão de lixeira dentro dos containers */
        button[kind="secondary"]:has(div > svg) {
            border: none;
            background: transparent;
        }

        /* --- DATA EDITOR --- */
        div[data-testid="stDataFrame"] {
            border: 1px solid #f0f0f0;
            border-radius: 8px;
        }
        div[data-testid="stDataFrame"] div[data-testid="stHeader"] {
            background-color: #fcfcfc;
            color: var(--text-light);
            font-size: 0.85rem;
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
    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- MENU LATERAL ---
    with st.sidebar:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, use_column_width=True)
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            
        st.markdown("### CONFIGURAÇÕES")
        
        with st.expander("Gerenciar Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo Departamento")
                if st.form_submit_button("Adicionar"):
                    if novo and novo not in lista_deptos:
                        lista_deptos.append(novo)
                        salvar_departamentos(lista_deptos)
                        st.rerun()
            rm_dept = st.selectbox("Remover", ["..."] + lista_deptos)
            if st.button("Remover Selecionado"):
                if rm_dept != "...":
                    lista_deptos.remove(rm_dept)
                    salvar_departamentos(lista_deptos)
                    st.rerun()

        st.divider()
        
        st.markdown("### OPERACIONAL")
        with st.form("quick_add"):
            st.caption("Novo Objetivo Macro")
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Nome do Objetivo")
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
                    st.warning("Preencha o nome.")

    # --- ÁREA PRINCIPAL ---
    c_head_1, c_head_2 = st.columns([3,1])
    with c_head_1:
        st.markdown(f"<h2 style='font-weight: 700; color: #1e1e1e;'>Painel de Gestão</h2>", unsafe_allow_html=True)
        st.caption("Acompanhamento de Objetivos e Resultados Chave")
    
    if df.empty:
        st.info("Comece criando um Objetivo no menu lateral.")
    else:
        depts = sorted(list(set(df['Departamento'].unique()) | set(lista_deptos)))
        abas = st.tabs(depts)
        
        for i, depto in enumerate(depts):
            with abas[i]:
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                df_d = df[df['Departamento'] == depto]
                if df_d.empty:
                    st.info("Nenhum OKR iniciado neste departamento.")
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
                    
                    label_obj = f"{obj}  •  {int(prog_obj*100)}%"
                    
                    with st.expander(label_obj, expanded=True):
                        
                        c_edit_obj, c_del_obj = st.columns([6, 1])
                        with c_edit_obj:
                            new_name = st.text_input("Título do Objetivo", value=obj, key=f"n_o_{depto}_{obj}", label_visibility="collapsed")
                            if new_name != obj:
                                st.session_state['df_master'].loc[mask_obj, 'Objetivo'] = new_name
                                st.rerun()
                        with c_del_obj:
                            if st.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir Objetivo"):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                st.rerun()

                        # --- HIERARQUIA 2: KRs ---
                        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
                        st.markdown("<div style='font-size: 0.8rem; color: #6b7280; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem;'>Resultados Chave (KRs)</div>", unsafe_allow_html=True)
                        
                        krs = [x for x in df[mask_obj]['Resultado Chave (KR)'].unique() if x]
                        
                        if not krs:
                            st.caption("Este objetivo ainda não possui KRs.")

                        for kr in krs:
                            mask_kr = mask_obj & (df['Resultado Chave (KR)'] == kr)
                            df_kr = df[mask_kr] 
                            
                            prog_kr = df_kr['Progresso (%)'].mean()
                            if pd.isna(prog_kr): prog_kr = 0.0
                            prog_kr = max(0.0, min(1.0, float(prog_kr)))

                            with st.container(border=True):
                                c_title, c_bar = st.columns([3, 1])
                                
                                with c_title:
                                    st.markdown(f"<span style='font-size:1rem; font-weight:600; color:#1e1e1e;'>🎯 {kr}</span>", unsafe_allow_html=True)
                                    new_kr = st.text_input("Editar KR", value=kr, key=f"r_k_{depto}_{obj}_{kr}", label_visibility="collapsed")
                                    if new_kr != kr:
                                        st.session_state['df_master'].loc[mask_kr, 'Resultado Chave (KR)'] = new_kr
                                        st.rerun()
                                
                                with c_bar:
                                    st.progress(prog_kr, text=f"{int(prog_kr*100)}%")
                                
                                st.markdown("<div style='margin-top:12px; margin-bottom: 4px; font-size:0.75rem; font-weight:600; color:#6b7280; text-transform:uppercase;'>Tarefas & Ações</div>", unsafe_allow_html=True)
                                
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
                        with st.popover("➕ Adicionar Novo KR"):
                            nk = st.text_input("Nome do KR", key=f"nk_{obj}")
                            if st.button("Criar KR", key=f"bk_{obj}"):
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
    
    st.markdown("---")
    with st.expander("📂 Central de Exportação"):
        st.dataframe(st.session_state['df_master'], use_container_width=True)
        st.download_button(
            "📥 Baixar Excel Completo",
            converter_para_excel(st.session_state['df_master']),
            "okrs_imobanco.xlsx"
        )
