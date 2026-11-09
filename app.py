import streamlit as st
import os
import html
import json
import pandas as pd
import sqlite3
import bcrypt
import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
from streamlit_option_menu import option_menu
import plotly.express as px

os.makedirs('dados', exist_ok=True)

# Regras de categorização automática do importador de CSV (palavra-chave na descrição -> categoria).
# Para usar regras próprias sem publicá-las, crie dados/regras_categorias.json com o mesmo formato.
REGRAS_CATEGORIAS_PADRAO = {
    "Alimentação": ["SUPERMERCADO", "MERCADO", "IFOOD", "RESTAURANTE", "PADARIA", "LANCHONETE"],
    "Lazer": ["CINEMA", "BAR ", "INGRESSO", "SHOW"],
    "Transporte": ["UBER", "99APP", "DETRAN", "POSTO", "ESTACIONAMENTO"],
    "Assinaturas": ["NETFLIX", "SPOTIFY", "AMAZON", "YOUTUBE"],
    "Saúde": ["FARMACIA", "DROGARIA", "HOSPITAL"],
}

def carregar_regras_categorias():
    caminho = os.path.join('dados', 'regras_categorias.json')
    if os.path.exists(caminho):
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    return REGRAS_CATEGORIAS_PADRAO

# Configuração da Página
st.set_page_config(page_title="BananaBudget", layout="wide", initial_sidebar_state="expanded")

# -- Banco de Dados Atualizado --
def init_db():
    conn = sqlite3.connect('dados/finance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, data TEXT, tipo TEXT, categoria TEXT, valor REAL, descricao TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    # Novas tabelas para as novas funcionalidades
    c.execute('''CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, categoria TEXT, limite REAL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS recorrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, descricao TEXT, categoria TEXT, valor REAL, dia_vencimento INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    conn.commit()
    return conn

conn = init_db()

# -- Funções de Segurança e Auth --
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Controle de Sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario_id = None
    st.session_state.usuario_nome = ""

# --- TELA DE LOGIN / CADASTRO ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🍌 BananaBudget</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Controle financeiro simples e direto.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_cadastro = st.tabs(["Entrar", "Criar Conta"])
        
        with tab_login:
            with st.form("form_login"):
                email_login = st.text_input("E-mail ou Telefone")
                senha_login = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Acessar", use_container_width=True)
                
                if submit_login:
                    c = conn.cursor()
                    c.execute("SELECT id, nome, senha FROM usuarios WHERE email = ?", (email_login,))
                    user = c.fetchone()
                    if user and check_password(senha_login, user[2]):
                        st.session_state.logged_in = True
                        st.session_state.usuario_id = user[0]
                        st.session_state.usuario_nome = user[1]
                        st.rerun()
                    else:
                        st.error("Credenciais incorretas!", icon=":material/error:")
                        
        with tab_cadastro:
            with st.form("form_cadastro"):
                nome_cad = st.text_input("Como quer ser chamado?")
                email_cad = st.text_input("E-mail ou Telefone (usado para login)")
                senha_cad = st.text_input("Crie uma Senha", type="password")
                submit_cad = st.form_submit_button("Cadastrar", use_container_width=True)
                
                if submit_cad:
                    if nome_cad and email_cad and senha_cad:
                        try:
                            c = conn.cursor()
                            c.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", 
                                      (nome_cad, email_cad, hash_password(senha_cad)))
                            conn.commit()
                            st.success("Conta criada! Agora é só fazer login.", icon=":material/check_circle:")
                        except sqlite3.IntegrityError:
                            st.error("Este e-mail/telefone já está cadastrado.", icon=":material/warning:")
                    else:
                        st.warning("Preencha todos os campos.", icon=":material/warning:")

# --- APLICATIVO PRINCIPAL ---
else:
    def obter_resumo_mes(df, data_alvo):
        df_mes = df[(df['data'].dt.month == data_alvo.month) & (df['data'].dt.year == data_alvo.year)]
        receitas = df_mes[df_mes['tipo'] == 'Receita']['valor'].sum()
        despesas = df_mes[df_mes['tipo'] == 'Despesa']['valor'].sum()
        saldo = receitas - despesas
        return receitas, despesas, saldo, df_mes

    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown(f"""<div style="text-align: center; padding-top: 10px;"><h3 style="margin-bottom: 0px;">Olá, {html.escape(st.session_state.usuario_nome)}! 👋</h3></div>""", unsafe_allow_html=True)
        st.divider()
        
        choice = option_menu(
            menu_title="BananaBudget",  
            menu_icon="wallet2",        
            # Adicionado a opção "Planejamento"
            options=["Home", "Lançar", "Planejamento", "Importar CSV", "Histórico", "Relatórios"],
            icons=["house-door-fill", "plus-circle-fill", "calendar-check-fill", "file-earmark-arrow-up-fill", "clock-history", "pie-chart-fill"],
            default_index=0,            
            orientation="vertical",     
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#fafafa", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"8px 0px", "padding": "12px", "--hover-color": "#333333"},
                "nav-link-selected": {"background-color": "#F63366"},
                "menu-title": {"text-align": "center", "margin-bottom": "15px", "font-size": "22px"} 
            }
        )
        
        st.divider()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sair (Logout)", use_container_width=True, icon=":material/logout:"):
            st.session_state.logged_in = False
            st.session_state.usuario_id = None
            st.session_state.usuario_nome = ""
            st.rerun()

    df_geral = pd.read_sql_query("SELECT * FROM transacoes WHERE usuario_id = ?", conn, params=(st.session_state.usuario_id,))
    if not df_geral.empty:
        df_geral['data'] = pd.to_datetime(df_geral['data'])

    # --- TELA: HOME (COM PROJEÇÃO E METAS) ---
    if choice == "Home":
        st.title(":material/home: Visão Geral")
        st.markdown("Acompanhamento financeiro e alertas automáticos.")
        st.divider()

        if df_geral.empty:
            st.info("Nenhuma transação encontrada. Vá em 'Lançar' ou 'Importar CSV' para começar!", icon=":material/info:")
        else:
            hoje = datetime.now()
            mes_atual = hoje
            mes_passado = hoje - relativedelta(months=1)
            mes_retrasado = hoje - relativedelta(months=2)

            rec_atual, des_atual, sal_atual, df_atual = obter_resumo_mes(df_geral, mes_atual)
            rec_passado, des_passado, sal_passado, df_passado = obter_resumo_mes(df_geral, mes_passado)
            rec_retrasado, des_retrasado, sal_retrasado, df_retrasado = obter_resumo_mes(df_geral, mes_retrasado)

            # --- NOVIDADE 1: PROJEÇÃO DE FIM DE MÊS ---
            dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
            dia_atual = hoje.day
            
            # Só faz a projeção se já tiver passado pelo menos 2 dias do mês para evitar distorções
            if dia_atual > 2 and des_atual > 0:
                gasto_diario_medio = des_atual / dia_atual
                projecao_despesas = gasto_diario_medio * dias_no_mes
                saldo_projetado = rec_atual - projecao_despesas
                
                if saldo_projetado >= 0:
                    st.success(f"**Projeção Mágica:** Mantendo seu ritmo atual de gastos, você terminará o mês com saldo **POSITIVO** de R$ {saldo_projetado:.2f}!", icon=":material/trending_up:")
                else:
                    st.error(f"**Atenção no Freio:** Mantendo seu ritmo atual, você terminará o mês com saldo **NEGATIVO** de R$ {abs(saldo_projetado):.2f}. Segure os gastos!", icon=":material/warning:")
            
            # --- NOVIDADE 2: ACOMPANHAMENTO DE METAS ---
            df_metas = pd.read_sql_query("SELECT * FROM metas WHERE usuario_id = ?", conn, params=(st.session_state.usuario_id,))
            if not df_metas.empty:
                st.subheader(":material/flag: Suas Metas do Mês")
                cols_metas = st.columns(len(df_metas))
                
                for idx, row in df_metas.iterrows():
                    cat = row['categoria']
                    limite = row['limite']
                    # Calcula quanto já gastou nessa categoria neste mês
                    gasto_cat = df_atual[(df_atual['tipo'] == 'Despesa') & (df_atual['categoria'] == cat)]['valor'].sum()
                    perc = min(gasto_cat / limite, 1.0) if limite > 0 else 1.0
                    
                    with cols_metas[idx % len(cols_metas)]:
                        st.write(f"**{cat}** (R$ {gasto_cat:.0f} / R$ {limite:.0f})")
                        # Se passou de 90% da meta, barra fica vermelha (Streamlit não suporta cor condicional nativa na barra, então damos um aviso)
                        st.progress(perc)
                        if gasto_cat > limite:
                            st.markdown(f"<span style='color: #e74c3c; font-size: 12px;'>⚠️ Estourou R$ {gasto_cat - limite:.2f}</span>", unsafe_allow_html=True)
                        elif perc > 0.85:
                            st.markdown(f"<span style='color: #f39c12; font-size: 12px;'>⚠️ Quase no limite!</span>", unsafe_allow_html=True)
                st.divider()

            # Métricas e Gráficos Padrão
            st.subheader(":material/account_balance_wallet: Comparativo Total de Despesas")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label=mes_retrasado.strftime("%B / %Y"), value=f"R$ {des_retrasado:.2f}")
            with col2:
                perc_passado = ((des_passado - des_retrasado) / des_retrasado * 100) if des_retrasado > 0 else 0
                st.metric(label=mes_passado.strftime("%B / %Y"), value=f"R$ {des_passado:.2f}", delta=f"{perc_passado:.1f}%", delta_color="inverse")
            with col3:
                perc_atual = ((des_atual - des_passado) / des_passado * 100) if des_passado > 0 else 0
                st.metric(label=mes_atual.strftime("%B / %Y"), value=f"R$ {des_atual:.2f}", delta=f"{perc_atual:.1f}%", delta_color="inverse")
            st.divider()

            despesas_trimestre = pd.concat([df_retrasado[df_retrasado['tipo'] == 'Despesa'].assign(Mes_Nome=mes_retrasado.strftime("%B")),
                                            df_passado[df_passado['tipo'] == 'Despesa'].assign(Mes_Nome=mes_passado.strftime("%B")),
                                            df_atual[df_atual['tipo'] == 'Despesa'].assign(Mes_Nome=mes_atual.strftime("%B"))])
            
            st.subheader(":material/bar_chart: Evolução Visual")
            col_graf1, col_graf2 = st.columns(2)

            with col_graf1:
                dados_barras_geral = pd.DataFrame({'Mês': [mes_retrasado.strftime("%B"), mes_passado.strftime("%B"), mes_atual.strftime("%B")], 'Receitas': [rec_retrasado, rec_passado, rec_atual], 'Despesas': [des_retrasado, des_passado, des_atual]}).melt(id_vars='Mês', var_name='Tipo', value_name='Valor')
                fig_bar = px.bar(dados_barras_geral, x='Mês', y='Valor', color='Tipo', barmode='group', color_discrete_map={'Receitas': '#2ecc71', 'Despesas': '#e74c3c'})
                fig_bar.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_title=None, margin=dict(b=0))
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_graf2:
                if not despesas_trimestre.empty:
                    fig_cat = px.bar(despesas_trimestre.groupby(['Mes_Nome', 'categoria'], as_index=False)['valor'].sum(), x="Mes_Nome", y="valor", color="categoria", text_auto='.2s', color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_cat.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_title=None, yaxis_title="Total (R$)", margin=dict(b=0))
                    fig_cat.update_xaxes(categoryorder='array', categoryarray=[mes_retrasado.strftime("%B"), mes_passado.strftime("%B"), mes_atual.strftime("%B")])
                    st.plotly_chart(fig_cat, use_container_width=True)

    elif choice == "Lançar":
        st.title(":material/add_circle: Novo Lançamento Manual")
        with st.form("form_registro", clear_on_submit=True):
            data = st.date_input("Data", datetime.now())
            tipo = st.selectbox("Tipo", ["Despesa", "Receita"])
            categoria = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Salário", "Assinaturas", "Outros"])
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
            desc = st.text_area("Descrição")

            if st.form_submit_button("Salvar Transação", icon=":material/save:"):
                c = conn.cursor()
                c.execute('INSERT INTO transacoes (usuario_id, data, tipo, categoria, valor, descricao) VALUES (?, ?, ?, ?, ?, ?)', 
                          (st.session_state.usuario_id, data.strftime("%Y-%m-%d"), tipo, categoria, valor, desc))
                conn.commit()
                st.success("Lançamento salvo com sucesso!", icon=":material/check_circle:")

    # --- NOVIDADE 3: TELA DE PLANEJAMENTO (METAS E RECORRENTES) ---
    elif choice == "Planejamento":
        st.title(":material/edit_calendar: Planejamento Financeiro")
        st.markdown("Automatize suas contas fixas e defina limites para não estourar o orçamento.")
        
        tab_fixas, tab_metas = st.tabs(["Despesas Recorrentes", "Metas de Gastos"])
        
        with tab_fixas:
            st.subheader("Contas de Todo Mês")
            st.write("Cadastre coisas como Aluguel, Academia, Spotify. Você poderá lançar todas com 1 clique todo mês.")
            
            with st.form("form_recorrente", clear_on_submit=True):
                colA, colB, colC, colD = st.columns(4)
                with colA: desc_rec = st.text_input("Descrição (Ex: Netflix)")
                with colB: cat_rec = st.selectbox("Categoria", ["Assinaturas", "Moradia", "Transporte", "Saúde", "Outros"])
                with colC: valor_rec = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
                with colD: dia_rec = st.number_input("Dia do Vencimento", min_value=1, max_value=31, step=1)
                
                if st.form_submit_button("Cadastrar Despesa Fixa"):
                    if desc_rec and valor_rec > 0:
                        c = conn.cursor()
                        c.execute("INSERT INTO recorrentes (usuario_id, descricao, categoria, valor, dia_vencimento) VALUES (?, ?, ?, ?, ?)",
                                  (st.session_state.usuario_id, desc_rec, cat_rec, valor_rec, dia_rec))
                        conn.commit()
                        st.success("Despesa fixa cadastrada!", icon=":material/check_circle:")
                        st.rerun()
            
            # Botão mágico de lançar tudo
            df_recorrentes = pd.read_sql_query("SELECT * FROM recorrentes WHERE usuario_id = ?", conn, params=(st.session_state.usuario_id,))
            if not df_recorrentes.empty:
                st.divider()
                st.dataframe(df_recorrentes[['descricao', 'categoria', 'valor', 'dia_vencimento']], hide_index=True, use_container_width=True)
                
                if st.button("🚀 PROCESSAR DESPESAS FIXAS DESTE MÊS", type="primary"):
                    c = conn.cursor()
                    hoje = datetime.now()
                    inseridos = 0
                    for _, row in df_recorrentes.iterrows():
                        # Monta a data usando o dia de vencimento, mas no mês atual
                        # Se o mês não tem o dia (ex: 31 de fev), trava no último dia possível
                        ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]
                        dia_real = min(row['dia_vencimento'], ultimo_dia_mes)
                        data_lancamento = datetime(hoje.year, hoje.month, dia_real).strftime("%Y-%m-%d")
                        
                        c.execute('INSERT INTO transacoes (usuario_id, data, tipo, categoria, valor, descricao) VALUES (?, ?, ?, ?, ?, ?)', 
                                  (st.session_state.usuario_id, data_lancamento, "Despesa", row['categoria'], row['valor'], row['descricao'] + " (Fixa)"))
                        inseridos += 1
                    conn.commit()
                    st.success(f"Mágica feita! {inseridos} despesas fixas foram lançadas para este mês.", icon=":material/check_circle:")
        
        with tab_metas:
            st.subheader("Teto de Gastos")
            st.write("Defina um limite mensal para categorias onde você costuma exagerar (Ex: Lazer, Alimentação).")
            
            with st.form("form_metas", clear_on_submit=True):
                colA, colB = st.columns(2)
                with colA: cat_meta = st.selectbox("Categoria a Limitar", ["Lazer", "Alimentação", "Transporte", "Outros"])
                with colB: limite_meta = st.number_input("Limite Mensal (R$)", min_value=0.0, step=0.01)
                
                if st.form_submit_button("Salvar Meta"):
                    c = conn.cursor()
                    # Verifica se já tem meta pra essa categoria. Se sim, atualiza. Se não, insere.
                    c.execute("SELECT id FROM metas WHERE usuario_id = ? AND categoria = ?", (st.session_state.usuario_id, cat_meta))
                    existe = c.fetchone()
                    if limite_meta == 0:
                        c.execute("DELETE FROM metas WHERE usuario_id = ? AND categoria = ?", (st.session_state.usuario_id, cat_meta))
                    elif existe:
                        c.execute("UPDATE metas SET limite = ? WHERE id = ?", (limite_meta, existe[0]))
                    else:
                        c.execute("INSERT INTO metas (usuario_id, categoria, limite) VALUES (?, ?, ?)", (st.session_state.usuario_id, cat_meta, limite_meta))
                    conn.commit()
                    st.success("Meta definida com sucesso! Acompanhe na Home.", icon=":material/flag:")
                    st.rerun()
            
            df_metas = pd.read_sql_query("SELECT * FROM metas WHERE usuario_id = ?", conn, params=(st.session_state.usuario_id,))
            if not df_metas.empty:
                st.divider()
                st.dataframe(df_metas[['categoria', 'limite']], hide_index=True, use_container_width=True)
                st.info("Para excluir ou resetar uma meta, basta defini-la como R$ 0,00 no formulário acima.")

    elif choice == "Importar CSV":
        st.title(":material/upload_file: Importar Fatura (CSV)")
        separador = st.radio("Separador do arquivo:", [", (Vírgula)", "; (Ponto e Vírgula)"], horizontal=True)
        sep_char = "," if "Vírgula" in separador else ";"
        
        arquivo_csv = st.file_uploader("Selecione o arquivo CSV", type=['csv'])
        if arquivo_csv is not None:
            try:
                df_import = pd.read_csv(arquivo_csv, sep=sep_char)
                st.dataframe(df_import.head(), use_container_width=True)
                
                st.divider()
                st.subheader(":material/tune: Mapeamento de Colunas")
                ultima_col = len(df_import.columns) - 1
                col_data = st.selectbox("1. Coluna de DATA:", df_import.columns, index=0)
                col_valor = st.selectbox("2. Coluna de VALOR:", df_import.columns, index=min(1, ultima_col))
                col_desc = st.selectbox("3. Coluna de DESCRIÇÃO:", df_import.columns, index=min(3, ultima_col))
                
                if st.button("Processar e Categorizar", type="primary", icon=":material/bolt:"):
                    c = conn.cursor()
                    inseridos = 0
                    regras_categorias = carregar_regras_categorias()
                    
                    def categorizar_lancamento(descricao, tipo):
                        if tipo == "Receita": return "Salário" if "SALÁRIO" in descricao.upper() else "Receita"
                        for categoria, palavras in regras_categorias.items():
                            for palavra in palavras:
                                if palavra in descricao.upper(): return categoria
                        return "Outros"

                    barra_progresso = st.progress(0)
                    for index, row in df_import.iterrows():
                        desc_linha = str(row[col_desc])
                        try: valor_bruto = float(str(row[col_valor]).strip())
                        except ValueError: valor_bruto = 0.0
                        if valor_bruto == 0 or "Pagamento de fatura" in desc_linha: continue 
                            
                        tipo_linha = "Despesa" if valor_bruto < 0 else "Receita"
                        cat_linha = categorizar_lancamento(desc_linha, tipo_linha)
                            
                        try: data_linha = pd.to_datetime(row[col_data], dayfirst=True).strftime("%Y-%m-%d")
                        except: data_linha = datetime.now().strftime("%Y-%m-%d")
                        
                        c.execute('INSERT INTO transacoes (usuario_id, data, tipo, categoria, valor, descricao) VALUES (?, ?, ?, ?, ?, ?)', 
                                  (st.session_state.usuario_id, data_linha, tipo_linha, cat_linha, abs(valor_bruto), desc_linha))
                        inseridos += 1
                        barra_progresso.progress((index + 1) / len(df_import))
                    
                    conn.commit()
                    st.success(f"Sucesso! {inseridos} transações processadas.", icon=":material/check_circle:")
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}", icon=":material/error:")

    elif choice == "Histórico":
        st.title(":material/history: Histórico")
        if not df_geral.empty:
            df_exibicao = df_geral.copy()
            df_exibicao['data'] = df_exibicao['data'].dt.strftime('%d/%m/%Y')
            tab1, tab2 = st.tabs(["Ver Transações", "Excluir / Limpar"])
            
            with tab1:
                st.dataframe(df_exibicao[['id', 'data', 'tipo', 'categoria', 'valor', 'descricao']], hide_index=True, use_container_width=True)
            with tab2:
                opcoes_deletar = df_exibicao.apply(lambda row: f"ID: {row['id']} | {row['data']} | {row['descricao']} | R$ {row['valor']}", axis=1)
                transacao_selecionada = st.selectbox("Selecione o registro para exclusão:", opcoes_deletar)
                if st.button("Excluir Selecionada", type="secondary", icon=":material/delete:"):
                    c = conn.cursor()
                    c.execute("DELETE FROM transacoes WHERE id = ? AND usuario_id = ?", (transacao_selecionada.split(" |")[0].replace("ID: ", ""), st.session_state.usuario_id))
                    conn.commit()
                    st.rerun()
                
                st.divider()
                if st.button("Apagar Todos os Dados", type="primary", icon=":material/warning:"):
                    c = conn.cursor()
                    c.execute("DELETE FROM transacoes WHERE usuario_id = ?", (st.session_state.usuario_id,))
                    conn.commit()
                    st.rerun() 
        else:
            st.info("Nenhuma transação registrada ainda.", icon=":material/info:")

    elif choice == "Relatórios":
        st.title(":material/monitoring: Relatórios Detalhados")
        if df_geral.empty:
            st.info("Registre transações para ver os relatórios!", icon=":material/info:")
        else:
            df_geral['mes_ano'] = df_geral['data'].dt.to_period('M').astype(str)
            tab_evolucao, tab_top, tab_exp = st.tabs(["Evolução Anual", "Top Maiores Gastos", "Exportar Dados"])
            
            with tab_evolucao:
                df_evolucao = df_geral.groupby(['mes_ano', 'tipo'], as_index=False)['valor'].sum()
                if not df_evolucao.empty:
                    fig_line = px.line(df_evolucao, x='mes_ano', y='valor', color='tipo', markers=True, color_discrete_map={'Receita': '#2ecc71', 'Despesa': '#e74c3c'})
                    fig_line.update_layout(height=450, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_title=None, yaxis_title="R$")
                    st.plotly_chart(fig_line, use_container_width=True)

            with tab_top:
                df_despesas = df_geral[df_geral['tipo'] == 'Despesa'].nlargest(10, 'valor')
                if not df_despesas.empty:
                    df_despesas['data'] = df_despesas['data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(df_despesas[['data', 'categoria', 'descricao', 'valor']], hide_index=True, use_container_width=True)

            with tab_exp:
                st.download_button(label="Baixar Planilha de Gastos", data=df_geral.to_csv(index=False).encode('utf-8'), file_name=f"Backup_{datetime.now().strftime('%Y-%m-%d')}.csv", mime="text/csv", type="primary")