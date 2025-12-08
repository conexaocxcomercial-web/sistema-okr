import streamlit as st
import sqlite3
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Sistema OKR", layout="wide")

# --- Banco de Dados (SQLite) ---
def init_db():
    conn = sqlite3.connect('okrs.db')
    c = conn.cursor()
    
    # Tabela de Departamentos
    c.execute('''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        )
    ''')
    
    # Tabela de Objetivos
    c.execute('''
        CREATE TABLE IF NOT EXISTS objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departamento_id INTEGER,
            descricao TEXT,
            FOREIGN KEY (departamento_id) REFERENCES departamentos (id)
        )
    ''')
    
    # Tabela de Key Results (KRs)
    c.execute('''
        CREATE TABLE IF NOT EXISTS krs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objetivo_id INTEGER,
            descricao TEXT,
            meta REAL,
            atual REAL,
            FOREIGN KEY (objetivo_id) REFERENCES objetivos (id)
        )
    ''')
    conn.commit()
    conn.close()

# --- Funções de Manipulação de Dados ---
def add_departamento(nome):
    conn = sqlite3.connect('okrs.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO departamentos (nome) VALUES (?)', (nome,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_departamentos():
    conn = sqlite3.connect('okrs.db')
    df = pd.read_sql('SELECT * FROM departamentos', conn)
    conn.close()
    return df

def add_objetivo(departamento_id, descricao):
    conn = sqlite3.connect('okrs.db')
    c = conn.cursor()
    c.execute('INSERT INTO objetivos (departamento_id, descricao) VALUES (?, ?)', (departamento_id, descricao))
    conn.commit()
    conn.close()

def get_objetivos(departamento_id):
    conn = sqlite3.connect('okrs.db')
    df = pd.read_sql('SELECT * FROM objetivos WHERE departamento_id = ?', conn, params=(departamento_id,))
    conn.close()
    return df

def add_kr(objetivo_id, descricao, meta, atual):
    conn = sqlite3.connect('okrs.db')
    c = conn.cursor()
    c.execute('INSERT INTO krs (objetivo_id, descricao, meta, atual) VALUES (?, ?, ?, ?)', 
              (objetivo_id, descricao, meta, atual))
    conn.commit()
    conn.close()

def get_krs_full():
    conn = sqlite3.connect('okrs.db')
    query = '''
        SELECT 
            d.nome as Departamento,
            o.descricao as Objetivo,
            k.descricao as KR,
            k.meta as Meta,
            k.atual as Atual,
            ROUND((k.atual / k.meta) * 100, 2) as Progresso_Percentual
        FROM krs k
        JOIN objetivos o ON k.objetivo_id = o.id
        JOIN departamentos d ON o.departamento_id = d.id
    '''
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- Interface de Login ---
def check_password():
    """Retorna True se o usuário tiver logado com sucesso."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.markdown("## 🔒 Acesso Restrito - Sistema OKR")
        col1, col2 = st.columns([1, 2])
        with col1:
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            
            if st.button("Entrar"):
                # CREDENCIAIS SIMPLES (Altere conforme necessário)
                if usuario == "admin" and senha == "1234":
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        return False
    return True

# --- App Principal ---
def main_app():
    # Inicializa o banco
    init_db()

    # Sidebar para Logout
    with st.sidebar:
        st.title("Menu")
        if st.button("Sair (Logout)"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.title("📊 Gestão de OKRs Corporativos")

    tab1, tab2, tab3 = st.tabs(["📝 Cadastro", "📈 Dashboard Visual", "📥 Exportar Dados"])

    # --- ABA 1: CADASTRO ---
    with tab1:
        st.header("Cadastro de Estrutura")
        
        # 1. Cadastro de Departamento
        with st.expander("1. Novo Departamento", expanded=True):
            col_dep1, col_dep2 = st.columns([3, 1])
            with col_dep1:
                novo_dep = st.text_input("Nome do Departamento (Ex: Comercial, RH)")
            with col_dep2:
                st.write("") # Espaçamento
                st.write("") 
                if st.button("Salvar Departamento"):
                    if novo_dep:
                        sucesso = add_departamento(novo_dep)
                        if sucesso:
                            st.success(f"Departamento '{novo_dep}' criado!")
                            time.sleep(1) # Pequeno delay para ler a mensagem
                            st.rerun() # FORÇA A ATUALIZAÇÃO DA TELA
                        else:
                            st.warning("Departamento já existe.")
                    else:
                        st.warning("Digite um nome.")

        # Carregar departamentos existentes para usar nos selects
        df_deps = get_departamentos()
        
        if not df_deps.empty:
            # 2. Cadastro de Objetivo
            with st.expander("2. Novo Objetivo", expanded=False):
                dep_selecionado = st.selectbox("Selecione o Departamento", df_deps['nome'], key='sel_dep_obj')
                id_dep = df_deps[df_deps['nome'] == dep_selecionado]['id'].values[0]
                
                novo_obj = st.text_input("Descrição do Objetivo (Ex: Aumentar Receita)")
                if st.button("Salvar Objetivo"):
                    if novo_obj:
                        add_objetivo(id_dep, novo_obj)
                        st.success("Objetivo Cadastrado!")
                        time.sleep(0.5)
                        st.rerun()

            # 3. Cadastro de KR
            with st.expander("3. Novo Key Result (KR)", expanded=False):
                # Primeiro seleciona departamento para filtrar objetivos
                dep_sel_kr = st.selectbox("Filtrar por Departamento", df_deps['nome'], key='sel_dep_kr')
                id_dep_kr = df_deps[df_deps['nome'] == dep_sel_kr]['id'].values[0]
                
                # Busca objetivos desse departamento
                df_objs = get_objetivos(id_dep_kr)
                
                if not df_objs.empty:
                    obj_sel_kr = st.selectbox("Vincular ao Objetivo", df_objs['descricao'])
                    id_obj = df_objs[df_objs['descricao'] == obj_sel_kr]['id'].values[0]
                    
                    c1, c2, c3 = st.columns(3)
                    desc_kr = c1.text_input("Descrição do KR")
                    meta_kr = c2.number_input("Meta (Valor)", min_value=0.0)
                    atual_kr = c3.number_input("Valor Atual", min_value=0.0)
                    
                    if st.button("Salvar KR"):
                        add_kr(id_obj, desc_kr, meta_kr, atual_kr)
                        st.success("KR Salvo com sucesso!")
                else:
                    st.info("Cadastre objetivos para este departamento primeiro.")
        else:
            st.info("👆 Comece cadastrando um departamento acima.")

    # --- ABA 2: VISUALIZAÇÃO ---
    with tab2:
        st.header("Acompanhamento")
        df_full = get_krs_full()
        
        if not df_full.empty:
            # Filtros
            filtro_dep = st.multiselect("Filtrar Departamento", df_full['Departamento'].unique())
            
            df_view = df_full if not filtro_dep else df_full[df_full['Departamento'].isin(filtro_dep)]
            
            # Exibição Visual
            for i, row in df_view.iterrows():
                with st.container():
                    st.markdown(f"**{row['Departamento']}** | *{row['Objetivo']}*")
                    st.write(f"📌 {row['KR']}")
                    
                    col_bar, col_metric = st.columns([3, 1])
                    with col_bar:
                        progresso = min(row['Progresso_Percentual'] / 100, 1.0) # Trava em 100% visualmente
                        st.progress(progresso)
                    with col_metric:
                        st.metric("Progresso", f"{row['Progresso_Percentual']}%", f"{row['Atual']} / {row['Meta']}")
                    st.divider()
        else:
            st.info("Nenhum dado cadastrado ainda.")

    # --- ABA 3: EXPORTAR ---
    with tab3:
        st.header("Relatórios")
        df_export = get_krs_full()
        if not df_export.empty:
            st.dataframe(df_export)
            
            # Botão de download
            # Converter para CSV
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar em Excel (CSV)",
                data=csv,
                file_name='relatorio_okrs.csv',
                mime='text/csv',
            )
        else:
            st.write("Sem dados para exportar.")

# --- Fluxo de Execução ---
if __name__ == "__main__":
    if check_password():
        main_app()
