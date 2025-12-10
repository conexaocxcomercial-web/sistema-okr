import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
        /* Paleta de Cores */
        :root {
            --color-purple-light: #dbbfff;
            --color-green-neon: #bef533;
            --color-pink-neon: #ff43c0;
            --color-blue-purple: #7371ff;
            --color-dark-gray: #1e1e1e;
            --color-text-dark: #1e1e1e;
            --color-bg-light: #f8f9fa;
        }
        
        .stApp {
            background-color: var(--color-bg-light);
            color: var(--color-text-dark);
        }

        /* Barra Lateral */
        section[data-testid="stSidebar"] {
            background-color: white;
            border-right: 1px solid #e0e0e0;
        }
        section[data-testid="stSidebar"] .stMarkdown h1, section[data-testid="stSidebar"] .stMarkdown h2, section[data-testid="stSidebar"] .stMarkdown h3 {
            color: var(--color-blue-purple);
        }

        /* Containers de KR */
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"] {
            border-color: var(--color-blue-purple) !important;
            background-color: var(--color-purple-light);
            border-radius: 8px;
            padding: 1rem;
            color: var(--color-dark-gray);
        }
        div[data-testid="stContainer"][style*="border-color:"] h1, div[data-testid="stContainer"][style*="border-color:"] h2, div[data-testid="stContainer"][style*="border-color:"] h3, div[data-testid="stContainer"][style*="border-color:"] p {
            color: var(--color-dark-gray);
        }

        /* Barra de Progresso */
        .stProgress > div > div > div > div {
            background-color: var(--color-green-neon);
        }

        /* Expansor de Objetivo */
        div[data-testid="stExpander"] {
            border-color: var(--color-blue-purple);
            border-radius: 8px;
            background-color: white;
        }
        div[data-testid="stExpander"] > div[role="button"] {
            color: var(--color-blue-purple);
        }

        /* Botões */
        button[kind="primary"] {
            background-color: var(--color-blue-purple) !important;
            border-color: var(--color-blue-purple) !important;
            color: white !important;
        }
        button[kind="secondary"] {
            border-color: var(--color-blue-purple) !important;
            color: var(--color-blue-purple) !important;
        }

        /* Tabelas de Dados */
        div[data-testid="stDataFrame"] div[data-testid="stHeader"] {
            background-color: #f0f0f0;
            color: var(--color-dark-gray);
        }

        /* Inputs e Selectbox */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-color: var(--color-blue-purple);
        }

        /* Abas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: white;
            border-radius: 4px 4px 0px 0px;
            color: var(--color-dark-gray);
            border: 1px solid #e0e0e0;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--color-blue-purple);
            color: white;
        }
    </style>
""", unsafe_allow_html=True)


# --- 2. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]
LOGO_FILE = "cx_CXdata_LOGO-positiva.png" # Nome correto do arquivo

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
        # CORREÇÃO DE SEGURANÇA: Só tenta carregar se o arquivo existir
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, use_column_width=True)
        else:
            # Se não tiver logo, mostra apenas o texto estilizado para não dar erro
            st.markdown(f"<h2 style='text-align: center; color: #7371ff;'>CX Data</h2>", unsafe_allow_html=True)
            
        st.header("⚙️ Configurações")
        
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
        
        st.subheader("🚀 Novo Objetivo")
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

                        st.markdown("### Resultados Chave (KRs)")
                        
                        krs = [x for x in df[mask_obj]['Resultado Chave (KR)'].unique() if x]
                        
                        if not krs:
                            st.caption("Nenhum KR criado ainda. Adicione o primeiro abaixo.")

                        for kr in krs:
                            mask_kr = mask_obj & (df['Resultado Chave (KR)'] == kr)
                            df_kr = df[mask_kr] 
                            
                            prog_kr = df_kr['Progresso (%)'].mean()
                            if pd.isna(prog_kr): prog_kr = 0.0
                            prog_kr = max(0.0, min(1.0, float(prog_kr)))

                            with st.container(border=True):
                                c_title, c_bar = st.columns([3, 1])
                                
                                with c_title:
                                    st.markdown(f"**🗝️ KR:** {kr}")
                                    new_kr = st.text_input("Editar nome do KR", value=kr, key=f"r_k_{depto}_{obj}_{kr}", label_visibility="collapsed")
                                    if new_kr != kr:
                                        st.session_state['df_master'].loc[mask_kr, 'Resultado Chave (KR)'] = new_kr
                                        st.rerun()
                                
                                with c_bar:
                                    st.progress(prog_kr, text=f"**{int(prog_kr*100)}%**")
                                
                                st.markdown("🔻 **Tarefas & Ações**")
                                
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
