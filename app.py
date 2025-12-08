import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestor de OKR", layout="wide", page_icon="💼")

# --- 2. ESTILOS E CONSTANTES ---
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]

# --- 3. FUNÇÕES DE TRATAMENTO DE DADOS ---

def carregar_dados_upload(uploaded_file):
    """Lê Excel/CSV e padroniza para evitar erros."""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        # Tratamento de Textos (Remove nulos)
        cols_texto = ['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 'Status', 'Responsável']
        for col in cols_texto:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '').fillna('')
        
        # Tratamento de Datas
        if 'Prazo' in df.columns:
            df['Prazo'] = pd.to_datetime(df['Prazo'], errors='coerce')
            
        # Tratamento de Números
        cols_num = ['Avanço', 'Alvo', 'Progresso (%)']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None

def criar_template_vazio():
    return pd.DataFrame(columns=[
        'Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 
        'Status', 'Responsável', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
    ])

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'Prazo' in df_exp.columns:
            df_exp['Prazo'] = df_exp['Prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False, sheet_name='OKRs')
    return output.getvalue()

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0: return min(av / al, 1.0)
        return 0.0
    except: return 0.0

def barra_progresso_html(valor):
    if pd.isna(valor): valor = 0.0
    pct = int(valor * 100)
    cor = "#ef4444" if pct < 30 else "#eab308" if pct < 70 else "#22c55e"
    return f"""<div style="width:100%; background:#e5e7eb; border-radius:4px; height:18px; display:flex; align-items:center;"><div style="background:{cor}; width:{pct}%; height:100%; border-radius:4px; transition:width 0.3s;"></div><span style="margin-left:8px; font-size:12px; font-weight:bold; color:#333;">{pct}%</span></div>"""

# --- 4. GESTÃO DE ESTADO (MEMÓRIA) ---
if 'df_ativo' not in st.session_state:
    st.session_state['df_ativo'] = criar_template_vazio()

# Departamentos extras (criados na sessão além dos que vieram no arquivo)
if 'deptos_extras' not in st.session_state:
    st.session_state['deptos_extras'] = ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]

# --- 5. APP PRINCIPAL ---

st.title("💼 Gestor de OKRs")

df = st.session_state['df_ativo']

# Lista unificada de departamentos (Do arquivo + Extras criados)
deptos_do_arquivo = [d for d in df['Departamento'].unique() if d and d.strip()]
lista_deptos_final = sorted(list(set(deptos_do_arquivo) | set(st.session_state['deptos_extras'])))

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📂 Arquivo")
    upload = st.file_uploader("Carregar Planilha Cliente", type=['xlsx', 'csv'])
    
    if upload is not None:
        if st.button("🔄 Carregar Dados", type="primary"):
            df_novo = carregar_dados_upload(upload)
            if df_novo is not None:
                st.session_state['df_ativo'] = df_novo
                st.session_state['deptos_extras'] = [] # Reseta extras ao carregar novo
                st.success("Carregado!")
                st.rerun()
    
    if st.button("🗑️ Limpar / Novo Projeto"):
        st.session_state['df_ativo'] = criar_template_vazio()
        st.rerun()

    st.markdown("---")
    
    # --- GERENCIAR DEPARTAMENTOS ---
    with st.expander("🏢 Gerenciar Departamentos"):
        novo_d = st.text_input("Novo:")
        if st.button("Add Dept"):
            if novo_d and novo_d not in st.session_state['deptos_extras']:
                st.session_state['deptos_extras'].append(novo_d)
                st.rerun()
        
        rem_d = st.selectbox("Remover da Lista:", ["-"] + st.session_state['deptos_extras'])
        if st.button("Del Dept"):
            if rem_d != "-":
                st.session_state['deptos_extras'].remove(rem_d)
                st.rerun()

    st.markdown("---")
    
    # --- NOVO REGISTRO ---
    st.subheader("📝 Novo OKR")
    with st.form("add_form", clear_on_submit=True):
        f_dp = st.selectbox("Departamento", lista_deptos_final)
        f_ob = st.text_input("Objetivo")
        f_kr = st.text_input("KR")
        
        if st.form_submit_button("Salvar"):
            novo_reg = {
                'Departamento': f_dp, 'Objetivo': f_ob, 'Resultado Chave (KR)': f_kr,
                'Status': 'Não Iniciado', 'Avanço': 0, 'Alvo': 1, 'Progresso (%)': 0,
                'Prazo': pd.to_datetime(date.today()), 'Tarefa': '', 'Responsável': ''
            }
            st.session_state['df_ativo'] = pd.concat([df, pd.DataFrame([novo_reg])], ignore_index=True)
            st.rerun()

    st.markdown("---")
    # Botão de Download
    if not df.empty:
        st.download_button(
            label="💾 Baixar Excel Atualizado",
            data=converter_para_excel(st.session_state['df_ativo']),
            file_name="okr_cliente_atualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- ÁREA VISUAL ---

if df.empty:
    st.info("Comece carregando um arquivo ou adicionando um OKR manualmente.")
else:
    # Abas apenas para departamentos que têm dados ou estão na lista ativa
    depts_visuais = [d for d in lista_deptos_final if d in df['Departamento'].unique() or d in st.session_state['deptos_extras']]
    
    abas = st.tabs(depts_visuais) if depts_visuais else []
    
    mudanca = False

    for i, depto in enumerate(depts_visuais):
        with abas[i]:
            df_d = df[df['Departamento'] == depto]
            
            if df_d.empty:
                st.caption("Sem dados neste departamento.")
                continue

            objs = [o for o in df_d['Objetivo'].unique() if o and o.strip()]
            for obj in objs:
                mask = (df['Departamento'] == depto) & (df['Objetivo'] == obj)
                df_obj = df[mask]
                
                media = df_obj['Progresso (%)'].mean()
                
                with st.expander(f"{obj}"):
                    st.markdown(barra_progresso_html(media), unsafe_allow_html=True)
                    
                    # Renomear
                    c_rn, _ = st.columns([3,1])
                    novo_nome = c_rn.text_input("Renomear:", value=obj, key=f"rn_{depto}_{obj}")
                    if novo_nome != obj:
                        st.session_state['df_ativo'].loc[mask, 'Objetivo'] = novo_nome
                        st.rerun()
                        
                    # Editor
                    cfg = {
                        "Progresso (%)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                        "Status": st.column_config.SelectboxColumn(options=OPCOES_STATUS, required=True),
                        "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Departamento": None, "Objetivo": None
                    }
                    
                    # CORREÇÃO AQUI: Trocado use_container_width=True por width="stretch"
                    df_ed = st.data_editor(
                        df_obj,
                        key=f"ed_{depto}_{obj}",
                        column_config=cfg,
                        width="stretch", # <--- AQUI MUDOU
                        num_rows="dynamic"
                    )
                    
                    if not df_ed.equals(df_obj):
                        # Atualiza em Memória
                        df_ed['Progresso (%)'] = df_ed.apply(calcular_progresso, axis=1)
                        df_ed['Departamento'] = depto
                        df_ed['Objetivo'] = obj
                        
                        idx_rem = df_obj.index
                        st.session_state['df_ativo'] = st.session_state['df_ativo'].drop(idx_rem)
                        st.session_state['df_ativo'] = pd.concat([st.session_state['df_ativo'], df_ed], ignore_index=True)
                        mudanca = True

    if mudanca:
        st.rerun()

    st.markdown("---")
    with st.expander("Ver Tabela Completa"):
        # CORREÇÃO AQUI TAMBÉM
        st.dataframe(st.session_state['df_ativo'], width=None) # width=None deixa automático ou use width="stretch" se quiser forçar
        