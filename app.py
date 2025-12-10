import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- 2. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]

# --- 3. FUNÇÕES DE DADOS (ROBUSTAS) ---

def carregar_dados_seguro():
    """Carrega dados, corrige datas e preenche buracos vazios."""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=[
            'Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 
            'Status', 'Responsável', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
        ])
    
    try:
        df = pd.read_csv(DATA_FILE)
        
        # 1. Preenche textos vazios com string vazia
        text_cols = ['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 'Status', 'Responsável']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '').fillna('')
        
        # 2. Corrige Datas
        if 'Prazo' in df.columns:
            df['Prazo'] = pd.to_datetime(df['Prazo'], errors='coerce')
        
        # 3. Corrige Números
        num_cols = ['Avanço', 'Alvo', 'Progresso (%)']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        return pd.DataFrame()

def carregar_departamentos():
    """Lê o arquivo de departamentos ou cria o padrão."""
    if os.path.exists(DEPT_FILE):
        try:
            return pd.read_csv(DEPT_FILE)['Departamento'].tolist()
        except:
            pass 
    
    padrao = ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]
    pd.DataFrame(padrao, columns=['Departamento']).to_csv(DEPT_FILE, index=False)
    return padrao

def salvar_departamentos(lista_deptos):
    """Salva a lista atualizada no arquivo."""
    pd.DataFrame(lista_deptos, columns=['Departamento']).to_csv(DEPT_FILE, index=False)

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0:
            return min(av / al, 1.0)
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

def barra_progresso_html(valor):
    if pd.isna(valor): valor = 0.0
    pct = int(valor * 100)
    cor = "#ef4444" if pct < 30 else "#eab308" if pct < 70 else "#22c55e"
    return f"""
    <div style="width:100%; background-color:#e5e7eb; border-radius:4px; height:18px; display:flex; align-items:center;">
        <div style="background-color:{cor}; width:{pct}%; height:100%; border-radius:4px; transition:width 0.3s;"></div>
        <span style="margin-left:8px; font-size:12px; font-weight:bold; color:#333;">{pct}%</span>
    </div>
    """

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

    # Variáveis de trabalho
    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- BARRA LATERAL (MENU) ---
    with st.sidebar:
        st.title("Menu")

        # --- A. GERENCIAR DEPARTAMENTOS ---
        with st.expander("🏢 Gerenciar Departamentos", expanded=False):
            st.caption("Adicione ou remova setores da lista.")
            
            with st.form("form_add_dept", clear_on_submit=True):
                novo_dept_input = st.text_input("Criar Novo:")
                enviou = st.form_submit_button("➕ Adicionar Dept")
                
                if enviou:
                    if novo_dept_input and novo_dept_input not in lista_deptos:
                        lista_deptos.append(novo_dept_input)
                        salvar_departamentos(lista_deptos)
                        st.success(f"{novo_dept_input} criado!")
                        st.rerun()
                    elif novo_dept_input in lista_deptos:
                        st.warning("Já existe!")

            st.divider()
            
            # Remover
            dept_to_remove = st.selectbox("Excluir Dept:", ["Selecione..."] + lista_deptos)
            if st.button("🗑️ Excluir Selecionado"):
                if dept_to_remove != "Selecione...":
                    lista_deptos.remove(dept_to_remove)
                    salvar_departamentos(lista_deptos)
                    st.success("Removido!")
                    st.rerun()

        st.divider()

        # --- B. NOVO REGISTRO DE OKR ---
        st.subheader("📝 Novo Registro")
        with st.form("quick_add", clear_on_submit=True):
            qd_dept = st.selectbox("Departamento", lista_deptos)
            qd_obj = st.text_input("Objetivo")
            qd_kr = st.text_input("KR (Resultado Chave)")
            
            if st.form_submit_button("Salvar Novo OKR"):
                novo_okr = {
                    'Departamento': qd_dept, 'Objetivo': qd_obj, 'Resultado Chave (KR)': qd_kr,
                    'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                    'Prazo': pd.to_datetime(date.today()), 'Tarefa': '', 'Responsável': ''
                }
                st.session_state['df_master'] = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                st.rerun()

        st.divider()
        if st.button("💾 Forçar Salvamento Geral"):
            st.session_state['df_master'].to_csv(DATA_FILE, index=False)
            st.toast("Dados salvos com sucesso!", icon="✅")

    # --- VISÃO PRINCIPAL ---
    
    if df.empty:
        st.info("Nenhum OKR cadastrado. Use o menu lateral para criar o primeiro.")
    else:
        depts_com_dados = [d for d in df['Departamento'].unique() if d and d.strip()]
        todos_depts_visualizacao = sorted(list(set(depts_com_dados) | set(lista_deptos)))
        
        abas = st.tabs(todos_depts_visualizacao)
        
        # Variável para controlar se houve edição
        houve_edicao = False

        for i, depto in enumerate(todos_depts_visualizacao):
            with abas[i]:
                df_depto = df[df['Departamento'] == depto]
                
                if df_depto.empty:
                    st.caption(f"O departamento '{depto}' existe, mas não tem OKRs cadastrados ainda.")
                    continue
                
                objs_unicos = [o for o in df_depto['Objetivo'].unique() if o and o.strip()]

                for obj in objs_unicos:
                    mask_obj = (df['Departamento'] == depto) & (df['Objetivo'] == obj)
                    df_obj = df[mask_obj]
                    
                    media = df_obj['Progresso (%)'].mean()
                    
                    with st.expander(f"{obj}", expanded=False):
                        # Barra desenhada ANTES da edição
                        st.markdown(barra_progresso_html(media), unsafe_allow_html=True)
                        
                        c_ren, _ = st.columns([3,1])
                        novo_nome = c_ren.text_input("Renomear Objetivo", value=obj, key=f"ren_{depto}_{obj}")
                        if novo_nome != obj:
                            st.session_state['df_master'].loc[mask_obj, 'Objetivo'] = novo_nome
                            st.rerun()

                        col_cfg = {
                            "Progresso (%)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                            "Status": st.column_config.SelectboxColumn(options=OPCOES_STATUS, required=True),
                            "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            "Departamento": None, 
                            "Objetivo": None
                        }
                        
                        df_editado = st.data_editor(
                            df_obj,
                            column_config=col_cfg,
                            use_container_width=True,
                            num_rows="dynamic",
                            key=f"editor_{depto}_{obj}"
                        )
                        
                        # --- CORREÇÃO DE ATUALIZAÇÃO ---
                        if not df_editado.equals(df_obj):
                            # 1. Recalcula percentual
                            df_editado['Progresso (%)'] = df_editado.apply(calcular_progresso, axis=1)
                            # 2. Garante chaves
                            df_editado['Departamento'] = depto
                            df_editado['Objetivo'] = obj
                            
                            # 3. Atualiza Master
                            idxs_originais = df_obj.index
                            st.session_state['df_master'] = st.session_state['df_master'].drop(idxs_originais)
                            st.session_state['df_master'] = pd.concat(
                                [st.session_state['df_master'], df_editado], 
                                ignore_index=True
                            )
                            
                            # 4. Salva no Disco
                            st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                            
                            # 5. Mágica do Refresh: Roda o script de novo para atualizar a barra lá em cima
                            st.rerun()

    st.markdown("---")
    with st.expander("📂 Exportar Dados"):
        st.dataframe(st.session_state['df_master'], use_container_width=True)
        st.download_button(
            "📥 Baixar Excel Completo",
            converter_para_excel(st.session_state['df_master']),
            "okrs_imobanco.xlsx"
        )
        
