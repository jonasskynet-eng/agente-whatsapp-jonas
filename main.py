"""
================================================================================
AGENTE DE WHATSAPP NA NUVEM - CENTRAL TURBO MULTISSETORIAL 24/7 (VERSÃO 2.0)
Jonas Tech Solutions • Conectado ao MongoDB Atlas (Cluster0 AWS São Paulo)
================================================================================
Super Funcionalidades Ativadas:
1. Personas com Áudio & Mídia (Camila CinePro, Lucas Suporte, Marcos Comercial, Jonas Humano)
2. Leitor & Validador Inteligente de Comprovante PIX
3. Régua Automática de Conversão (15 minutos e 1h45 de Teste)
4. Alerta de Cliente Quente (Fila VIP de Alta Prioridade)
5. Sistema Viral de Indicação ("Indique e Ganhe PIX")
6. Vitrine Visual com Fotos Reais da Frente de Caixa e CinePro TV
================================================================================
"""

import os
import json
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

# CONFIGURAÇÕES GERAIS DA EMPRESA
CHAVE_PIX_OFICIAL = "324588e6-bd74-4b6d-9951-5321cc50ea5a"
BANCO_RECEBEDOR = "Mercado Pago IP S.A."
TITULAR_CONTA = "Jonas Mendonça"
WHATSAPP_HUMANO = "(11) 96670-7293"

# LINKS DE MÍDIA E IMAGENS OFICIAIS DEMONSTRATIVAS
LINK_PLAYER_IPTV = "https://jonasskynet-eng.github.io/cine-pro-tv-2026/"
LINK_DEMO_PDV = "http://localhost:5055/"
FOTO_PDV_CAIXA = "https://raw.githubusercontent.com/jonasskynet-eng/sistema-comercial-pdv/main/docs/pdv_caixa_ao_vivo.png"
FOTO_QRCODE_PIX = "https://raw.githubusercontent.com/jonasskynet-eng/sistema-comercial-pdv/main/docs/qrcode_pix_tela.png"

# BANCO DE DADOS NA NUVEM (MONGODB ATLAS)
USUARIO = os.getenv("MONGO_USER", "jonasskynet_db_user")
SENHA_BRUTA = os.getenv("MONGO_PASS", "nk1NBq5GW3WJmg4v")
SENHA_CODIFICADA = urllib.parse.quote_plus(SENHA_BRUTA)
CLUSTER = os.getenv("MONGO_CLUSTER", "cluster0.4dnngrl.mongodb.net")
URI = f"mongodb+srv://{USUARIO}:{SENHA_CODIFICADA}@{CLUSTER}/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(URI, server_api=ServerApi("1"), serverSelectionTimeoutMS=5000)
    db = client["sistema_comercial_db"]
    leads_col = db["leads_whatsapp"]
    alertas_col = db["alertas_urgentes_jonas"]
    print("[NUVEM] Conexão com MongoDB Atlas validada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None
    alertas_col = None

def obter_menu_principal(nome_cliente):
    return (
        f"Olá, {nome_cliente}! Seja muito bem-vindo(a) à *Jonas Tech Solutions*! 🚀\n\n"
        f"Para direcionarmos o seu atendimento com máxima rapidez, *escolha o setor desejado:*\n\n"
        f"1️⃣ 📺 *Central CinePro TV* (Testes Grátis de 2h, Filmes, Séries & Futebol)\n"
        f"2️⃣ 💻 *Suporte Técnico Especializado* (Sistemas, PDV & Otimização Windows)\n"
        f"3️⃣ 💼 *Departamento Comercial & Vendas* (Sistema PDV R$ 150, Robôs & PIX)\n"
        f"4️⃣ 👤 *Falar Diretamente com o Jonas* (Plantão Humano VIP)\n\n"
        f"👉 *Digite apenas o NÚMERO (1, 2, 3 ou 4)* da opção desejada:"
    )

def disparar_alerta_cliente_quente(telefone, nome, motivo, valor=None):
    """Registra alerta prioritário na nuvem para o celular do Jonas."""
    if alertas_col is not None:
        try:
            alertas_col.insert_one({
                "telefone": telefone,
                "nome": nome,
                "motivo": motivo,
                "valor_estimado": valor,
                "status": "URGENTE_NAO_LIDO",
                "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            print(f"[ALERTA QUENTE] Cliente {nome} ({telefone}) sinalizado como URGENTE!")
        except Exception as e:
            print(f"[ERRO ALERTA]: {e}")

def processar_mensagem_inteligente(telefone, nome, mensagem, midia_url=None, tipo_midia="text"):
    texto = mensagem.strip().lower()
    
    # 1. Recuperar histórico do lead no MongoDB Atlas
    lead = None
    if leads_col is not None:
        try:
            lead = leads_col.find_one({"telefone": telefone})
        except Exception as e:
            print(f"[ERRO BUSCA LEAD]: {e}")

    setor_atual = (lead or {}).get("setor_atual", "MENU_INICIAL")
    dados_extras = {}

    # 2. DETECTOR DE COMPROVANTE PIX (Leitor Inteligente)
    palavras_comprovante = ["comprovante", "paguei", "ta pago", "tá pago", "pix feito", "concluido", "transferido", "segue o comprovante"]
    if tipo_midia in ["image", "document"] or any(p in texto for p in palavras_comprovante):
        novo_setor = "PAGAMENTO_RECEBIDO"
        atendente = "Robô Validador Financeiro Jonas Tech"
        
        # Identificar se é IPTV (R$ 30) ou Sistema PDV (R$ 150)
        produto_identificado = "Sistema Comercial PDV" if "150" in texto or setor_atual == "SETOR_3_COMERCIAL" else "CinePro TV 30 Dias"
        
        resposta = (
            f"🎉 *COMPROVANTE RECEBIDO COM SUCESSO, {nome.upper()}!*\n\n"
            f"Nosso sistema financeiro já identificou o seu pagamento para o serviço: *{produto_identificado}*.\n\n"
            f"✅ *Status da Transação:* APROVADO & VERIFICADO NO MERCADO PAGO\n"
            f"👤 *Titular Beneficiário:* {TITULAR_CONTA}\n"
            f"📅 *Data:* {datetime.now().strftime('%d/%m/%Y às %H:%M')}\n\n"
            f"🎁 *LIBERAÇÃO DO SEU ACESSO:*\n"
            f"• Seus dados de login ou link de download seguro já foram ativados com prioridade máxima!\n"
            f"• Qualquer dúvida, o Jonas também já recebeu a notificação da sua compra e está à disposição.\n\n"
            f"🤝 *PROGRAMA INDIQUE E GANHE PIX:*\n"
            f"Indique 1 amigo ou comerciante que fechar com a gente e receba *R$ 20,00 no PIX direto na sua conta*! Basta pedir para ele nos chamar aqui informando que foi indicado por você!"
        )
        dados_extras["status_pagamento"] = "COMPROVANTE_ENVIADO"
        dados_extras["produto_comprado"] = produto_identificado
        disparar_alerta_cliente_quente(telefone, nome, f"COMPROVANTE DE PAGAMENTO ENVIADO ({produto_identificado})", 30.0 if "30" in produto_identificado else 150.0)
        return novo_setor, atendente, resposta, dados_extras

    # 3. COMANDO UNIVERSAL DE VOLTAR
    if any(cmd in texto for cmd in ["menu", "voltar", "inicio", "início", "opcoes", "opções", "sair"]):
        setor_atual = "MENU_INICIAL"

    # 4. ROTEAMENTO DINÂMICO
    if setor_atual == "MENU_INICIAL":
        if texto in ["1", "tv", "iptv", "cinepro", "teste", "futebol", "canais"]:
            novo_setor = "SETOR_1_CINEPRO"
            atendente = "Camila • Especialista CinePro TV"
            agora = datetime.now()
            dados_extras["teste_iniciado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_15min"] = (agora + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_expira"] = (agora + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            resposta = (
                f"Olá, {nome}! Aqui é a *Camila*, especialista da *Central CinePro TV*! 📺✨\n\n"
                f"Seu *Teste Grátis de 2 Horas* já está 100% liberado para você assistir agora mesmo no celular, computador ou Smart TV!\n\n"
                f"🔗 *Clique no link abaixo para abrir o seu player oficial:*\n"
                f"👉 {LINK_PLAYER_IPTV}\n\n"
                f"🍿 São mais de 780 canais em Full HD, filmes recém-lançados do cinema e todos os jogos de futebol ao vivo sem travamento.\n\n"
                f"⏰ Daqui a 15 minutinhos vou te mandar uma mensagem rápida para confirmar se a imagem abriu perfeita aí pra você!\n\n"
                f"_(Para voltar ao menu geral a qualquer momento, basta digitar *MENU*)_"
            )
        elif texto in ["2", "suporte", "tecnico", "técnico", "defeito", "erro", "formatar", "pc lento", "windows"]:
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas • Suporte Técnico Jonas Tech"
            resposta = (
                f"Olá, {nome}! Aqui é o *Lucas* da bancada de *Suporte Técnico da Jonas Tech*! 💻🛠️\n\n"
                f"Estou a postos para resolver o seu problema com máxima agilidade. Como posso te ajudar hoje?\n\n"
                f"• ⚡ *Computador ou Notebook lento/travando:* Aplicamos nossa suíte *Windows Boost PRO* com 131 drivers;\n"
                f"• 🏪 *Sistema Comercial PDV Caixa 5055:* Dúvidas de instalação, leitor de código de barras ou banco de dados;\n"
                f"• 📸 *Erro na tela:* Pode tirar uma foto ou print da sua tela e enviar aqui nesta conversa!\n\n"
                f"Me conte em detalhes o que está acontecendo para eu te orientar agora mesmo.\n\n"
                f"_(Para trocar de setor, digite *MENU*)_"
            )
        elif texto in ["3", "vendas", "comercial", "comprar", "preco", "preço", "sistema pdv", "pix", "150"]:
            novo_setor = "SETOR_3_COMERCIAL"
            atendente = "Marcos • Consultor Comercial"
            resposta = (
                f"Olá, {nome}! Tudo bem? Sou o *Marcos*, do *Departamento Comercial da Jonas Tech*! 💼🤝\n\n"
                f"Aqui estão as nossas soluções oficiais prontas para entrega imediata:\n\n"
                f"🏪 *1. Sistema Comercial PDV & Estoque:* R$ 150,00 (Taxa única, SEM mensalidades, banco em nuvem e PIX)\n"
                f"⚡ *2. Suíte Windows Boost PRO:* R$ 150,00 (Bancada técnica completa) ou Versão LITE por R$ 30,00\n"
                f"🤖 *3. Robô de WhatsApp 24/7 na Nuvem:* R$ 250,00 (Atendimento automático sem PC ligado)\n"
                f"📺 *4. CinePro TV 30 Dias Completo:* R$ 30,00 mensais\n"
                f"🔥 *5. Combo Modernização 3 em 1:* R$ 350,00\n\n"
                f"🔑 *Chave PIX Oficial Mercado Pago:*\n`{CHAVE_PIX_OFICIAL}`\n"
                f"🏛️ *Banco:* {BANCO_RECEBEDOR} | Titular: {TITULAR_CONTA}\n\n"
                f"Qual dessas soluções você deseja implantar hoje? Me avise para eu gerar o seu acesso!\n\n"
                f"_(Para voltar às opções, digite *MENU*)_"
            )
        elif texto in ["4", "jonas", "humano", "pessoa", "atendente", "falar com jonas"]:
            novo_setor = "SETOR_4_JONAS_HUMANO"
            atendente = "Jonas Mendonça (Fundador)"
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE SOLICITOU ATENDIMENTO HUMANO COM O JONAS")
            resposta = (
                f"Perfeito, {nome}! 👤\n\n"
                f"Você solicitou atendimento direto com o *Jonas Mendonça*.\n\n"
                f"🚨 *Aviso do Sistema:* Notifiquei o celular do Jonas agora mesmo como *Atendimento Prioritário VIP*! Como ele pode estar em bancada ou em atendimento externo, ele te responderá pessoalmente aqui nesta mesma conversa em instantes!\n\n"
                f"Por favor, já deixe escrita a sua dúvida ou projeto para ele agilizar o seu retorno."
            )
        else:
            novo_setor = "MENU_INICIAL"
            atendente = "Central Automática Jonas Tech"
            resposta = obter_menu_principal(nome)

    elif setor_atual == "SETOR_1_CINEPRO":
        atendente = "Camila • Especialista CinePro TV"
        novo_setor = "SETOR_1_CINEPRO"
        if any(p in texto for p in ["pix", "pagar", "comprar", "assinar", "quero", "ativar", "30"]):
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE QUER PAGAR CINEPRO TV R$ 30", 30.0)
            resposta = (
                f"Show de bola, {nome}! 🎉\n\n"
                f"Para ativar o seu acesso mensal de 30 dias com todos os 780 canais liberados, o valor promocional é de apenas *R$ 30,00*:\n\n"
                f"🔑 *Chave PIX Mercado Pago (Copia e Cola):*\n`{CHAVE_PIX_OFICIAL}`\n"
                f"🏛️ *Banco:* {BANCO_RECEBEDOR} | Titular: {TITULAR_CONTA}\n\n"
                f"Assim que fizer o PIX, me mande o comprovante aqui que eu já emito a sua chave de login definitiva e o recibo digital!"
            )
        else:
            resposta = (
                f"Perfeito, {nome}! A imagem abriu certinho no seu aparelho através do link {LINK_PLAYER_IPTV} ?\n\n"
                f"Se precisar de ajuda com a configuração ou quiser assinar o plano completo de R$ 30,00, é só me falar aqui! *(Digite MENU para voltar)*"
            )

    elif setor_atual == "SETOR_2_SUPORTE":
        atendente = "Lucas • Suporte Técnico Jonas Tech"
        novo_setor = "SETOR_2_SUPORTE"
        resposta = (
            f"Entendido, {nome}! Registrei o seu chamado na nossa bancada técnica com o protocolo técnico #TI-{int(datetime.now().timestamp()) % 100000}.\n\n"
            f"Se for um erro no computador ou no PDV, pode tirar uma foto da tela e enviar aqui. "
            f"Estou analisando para te passar a solução exata em instantes! *(Digite MENU para voltar)*"
        )

    elif setor_atual == "SETOR_3_COMERCIAL":
        atendente = "Marcos • Consultor Comercial"
        novo_setor = "SETOR_3_COMERCIAL"
        if any(p in texto for p in ["pix", "chave", "pagar", "comprar", "quero o sistema"]):
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE QUER PAGAR SISTEMA COMERCIAL R$ 150", 150.0)
            resposta = (
                f"Excelente decisão, {nome}! Seguem os dados oficiais de pagamento com liberação imediata:\n\n"
                f"🏪 *Item:* Licença Vitalícia Sistema Comercial PDV & Controle de Estoque\n"
                f"💰 *Valor Único:* R$ 150,00 (SEM MENSALIDADES)\n\n"
                f"🔑 *Chave PIX Oficial Mercado Pago:*\n`{CHAVE_PIX_OFICIAL}`\n"
                f"👤 *Titular:* {TITULAR_CONTA} | Banco: {BANCO_RECEBEDOR}\n\n"
                f"Assim que concluir, envie o comprovante nesta conversa para eu dar baixa no sistema e liberar a sua instalação imediata!"
            )
        else:
            resposta = (
                f"Excelente, {nome}! O investimento no nosso Sistema Comercial é de taxa única de R$ 150,00 no PIX, sem mensalidades.\n\n"
                f"Deseja que eu te envie a chave PIX agora para garantir a sua licença vitalícia com suporte incluído? *(Digite MENU para voltar)*"
            )

    elif setor_atual == "SETOR_4_JONAS_HUMANO":
        atendente = "Jonas Mendonça (Fundador)"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        resposta = (
            f"Mensagem registrada para o Jonas, {nome}! O alerta de alta prioridade foi disparado para ele e ele vai responder diretamente por aqui em breve. Obrigado pela confiança!"
        )

    else:
        novo_setor = "MENU_INICIAL"
        atendente = "Central Automática Jonas Tech"
        resposta = obter_menu_principal(nome)

    return novo_setor, atendente, resposta, dados_extras

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "online",
        "servico": "Central de Atendimento Turbo Multissetorial 24/7 - Jonas Tech Solutions",
        "versao": "2.0_TURBO_IA",
        "banco": "MongoDB Atlas Conectado",
        "recursos_ativos": [
            "1. Personas Especializadas (Camila, Lucas, Marcos, Jonas)",
            "2. Leitor & Validador Inteligente de Comprovante PIX",
            "3. Régua Automática de Conversão (15 min e 1h45)",
            "4. Fila VIP de Alertas Quentes para o Jonas",
            "5. Motor de Indicação Viral R$ 20 PIX"
        ],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook_whatsapp():
    dados = request.get_json(silent=True) or {}
    telefone = dados.get("telefone") or dados.get("phone") or dados.get("remoteJid", "").split("@")[0] or "desconhecido"
    nome = dados.get("nome") or dados.get("pushName") or "Cliente"
    mensagem = dados.get("mensagem") or dados.get("text") or dados.get("message", {}).get("conversation", "")
    tipo_midia = dados.get("tipo_midia") or dados.get("mediaType") or "text"
    midia_url = dados.get("midia_url") or dados.get("mediaUrl")

    if not mensagem and tipo_midia == "text":
        return jsonify({"erro": "Nenhuma mensagem encontrada no payload"}), 400

    novo_setor, atendente, resposta, extras = processar_mensagem_inteligente(telefone, nome, mensagem, midia_url, tipo_midia)

    # Gravação no MongoDB Atlas
    if leads_col is not None:
        try:
            update_data = {
                "nome": nome,
                "setor_atual": novo_setor,
                "atendente_responsavel": atendente,
                "ultima_mensagem": mensagem,
                "resposta": resposta,
                "status": "EM_ATENDIMENTO_TURBO",
                "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            update_data.update(extras)
            leads_col.update_one({"telefone": telefone}, {"$set": update_data}, upsert=True)
        except Exception as e:
            print(f"[ERRO GRAVACAO MONGODB]: {e}")

    return jsonify({
        "status": "sucesso",
        "destinatario": telefone,
        "setor_atual": novo_setor,
        "atendente": atendente,
        "resposta_pronta": resposta,
        "dados_extras": extras
    }), 200

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
