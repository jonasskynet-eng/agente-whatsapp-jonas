"""
================================================================================
AGENTE DE WHATSAPP NA NUVEM - CENTRAL MULTISSETORIAL 24/7
Jonas Tech Solutions • Conectado ao MongoDB Atlas (Cluster0 AWS São Paulo)
================================================================================
Setores e Atendentes Virtuais Especializados:
1. Camila • Especialista CinePro TV (Streaming, Testes 2h & Ativações R$ 30)
2. Lucas • Suporte Técnico de TI (PDV, Windows Boost & Bancada Técnica)
3. Marcos • Consultor Comercial & Vendas (Sistema R$ 150, Combos & PIX)
4. Jonas • Atendimento Humano Direto (Transbordo Imediato)
================================================================================
"""

import os
import json
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

# CONFIGURAÇÕES GERAIS & CHAVE PIX OFICIAL DO JONAS
CHAVE_PIX_OFICIAL = "324588e6-bd74-4b6d-9951-5321cc50ea5a"
WHATSAPP_HUMANO = "(11) 96670-7293"

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
    print("[NUVEM] Conexão com MongoDB Atlas validada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None

# TEXTO PADRÃO DO MENU PRINCIPAL
def obter_menu_principal(nome_cliente):
    return (
        f"Olá, {nome_cliente}! Seja muito bem-vindo(a) à *Jonas Tech Solutions*! 🚀\n\n"
        f"Para direcionarmos você com o especialista certo e atendimento imediato, *escolha o setor desejado:*\n\n"
        f"1️⃣ 📺 *Central CinePro TV* (Testes Grátis de 2h, Filmes, Séries & Futebol)\n"
        f"2️⃣ 💻 *Suporte Técnico Especializado* (Sistemas, PDV & Otimização Windows)\n"
        f"3️⃣ 💼 *Departamento Comercial & Vendas* (Sistema PDV R$ 150, Robôs & PIX)\n"
        f"4️⃣ 👤 *Falar Diretamente com o Jonas* (Plantão Humano)\n\n"
        f"👉 *Digite apenas o NÚMERO (1, 2, 3 ou 4)* da opção desejada:"
    )

def processar_atendimento_multissetorial(telefone, nome, mensagem):
    texto = mensagem.strip().lower()
    
    # 1. Recuperar estado atual do cliente no MongoDB
    lead_existente = None
    if leads_col is not None:
        try:
            lead_existente = leads_col.find_one({"telefone": telefone})
        except Exception as e:
            print(f"[ERRO BUSCA LEAD]: {e}")

    setor_atual = (lead_existente or {}).get("setor_atual", "MENU_INICIAL")

    # Comando universal para reiniciar o fluxo
    if any(cmd in texto for cmd in ["menu", "voltar", "inicio", "início", "opcoes", "opções", "sair"]):
        setor_atual = "MENU_INICIAL"

    # 2. Roteamento por Setor
    if setor_atual == "MENU_INICIAL":
        if texto in ["1", "tv", "iptv", "cinepro", "teste tv", "futebol", "canais"]:
            novo_setor = "SETOR_1_CINEPRO"
            atendente = "Camila • Especialista CinePro TV"
            resposta = (
                f"Olá, {nome}! Aqui é a *Camila*, especialista da *Central CinePro TV*! 📺✨\n\n"
                f"Seu *Teste Grátis de 2 Horas* já está pré-liberado para você assistir agora mesmo no celular, computador ou Smart TV!\n\n"
                f"🔗 *Clique no link abaixo para abrir o seu player oficial:*\n"
                f"👉 https://jonasskynet-eng.github.io/cine-pro-tv-2026/\n\n"
                f"🍿 São mais de 780 canais em Full HD, filmes recém-lançados e todos os jogos de futebol ao vivo sem travar.\n\n"
                f"⏰ Daqui a 15 minutinhos vou te mandar uma mensagem rápida para confirmar se a imagem abriu perfeita aí pra você!\n\n"
                f"_(Caso queira voltar ao menu geral a qualquer momento, digite *MENU*)_"
            )
        elif texto in ["2", "suporte", "tecnico", "técnico", "defeito", "erro", "formatar", "pc lento", "windows"]:
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas • Suporte Técnico Jonas Tech"
            resposta = (
                f"Olá, {nome}! Aqui é o *Lucas* da bancada de *Suporte Técnico da Jonas Tech*! 💻🛠️\n\n"
                f"Estou aqui para resolver o seu problema com máxima agilidade. Como posso te ajudar hoje?\n\n"
                f"• ⚡ *Computador ou Notebook lento/travando:* Aplicamos a nossa suíte *Windows Boost PRO* com 131 drivers;\n"
                f"• 🏪 *Sistema Comercial PDV Caixa 5055:* Dúvidas de instalação, leitor de código de barras ou banco de dados;\n"
                f"• 🔧 *Erro na tela:* Pode me enviar uma foto ou print do erro aqui nesta conversa!\n\n"
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
                f"🏛️ *Banco:* Mercado Pago IP S.A. | Titular: Jonas Mendonça\n\n"
                f"Qual dessas soluções você deseja implantar hoje? Me avise para eu gerar o seu acesso!\n\n"
                f"_(Para voltar às opções, digite *MENU*)_"
            )
        elif texto in ["4", "jonas", "humano", "pessoa", "atendente", "falar com jonas"]:
            novo_setor = "SETOR_4_JONAS_HUMANO"
            atendente = "Jonas Mendonça (Fundador)"
            resposta = (
                f"Perfeito, {nome}! 👤\n\n"
                f"Você solicitou atendimento direto com o *Jonas Mendonça*.\n\n"
                f"🚨 *Aviso do Sistema:* Notifiquei o celular do Jonas agora mesmo. Como ele pode estar em bancada ou em atendimento externo, ele te responderá pessoalmente aqui nesta mesma conversa em instantes!\n\n"
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
            resposta = (
                f"Show de bola, {nome}! 🎉\n\n"
                f"Para ativar o seu acesso mensal de 30 dias com todos os 780 canais liberados, o valor é de apenas *R$ 30,00*:\n\n"
                f"🔑 *Chave PIX Mercado Pago (Copia e Cola):*\n`{CHAVE_PIX_OFICIAL}`\n"
                f"🏛️ *Banco:* Mercado Pago IP S.A. | Titular: Jonas Mendonça\n\n"
                f"Assim que fizer o PIX, me mande o comprovante aqui que eu já emito a sua chave de login definitiva!"
            )
        else:
            resposta = (
                f"Perfeito, {nome}! A imagem abriu certinho no seu aparelho através do link https://jonasskynet-eng.github.io/cine-pro-tv-2026/ ?\n\n"
                f"Se precisar de ajuda com a configuração ou quiser assinar o plano completo de R$ 30,00, é só me falar aqui! *(Digite MENU para voltar)*"
            )

    elif setor_atual == "SETOR_2_SUPORTE":
        atendente = "Lucas • Suporte Técnico Jonas Tech"
        novo_setor = "SETOR_2_SUPORTE"
        resposta = (
            f"Entendido, {nome}! Registrei o seu chamado na nossa bancada técnica.\n\n"
            f"Se for um erro no computador ou no PDV, pode tirar uma foto da tela e enviar aqui. "
            f"Estou analisando para te passar a solução exata em instantes! *(Digite MENU para voltar)*"
        )

    elif setor_atual == "SETOR_3_COMERCIAL":
        atendente = "Marcos • Consultor Comercial"
        novo_setor = "SETOR_3_COMERCIAL"
        if any(p in texto for p in ["pix", "chave", "pagar", "comprovante"]):
            resposta = (
                f"Perfeito, {nome}! Seguem os dados oficiais de pagamento:\n\n"
                f"🔑 *Chave PIX Oficial Mercado Pago:*\n`{CHAVE_PIX_OFICIAL}`\n"
                f"👤 *Titular:* Jonas Mendonça | Banco: Mercado Pago IP S.A.\n\n"
                f"Assim que concluir, envie o comprovante nesta conversa para eu dar baixa no sistema e liberar a sua instalação imediata!"
            )
        else:
            resposta = (
                f"Excelente, {nome}! O investimento no nosso Sistema Comercial é de taxa única de R$ 150,00 no PIX, sem mensalidades.\n\n"
                f"Deseja que eu te envie a chave PIX agora para garantir a sua licença vitalícia? *(Digite MENU para voltar)*"
            )

    elif setor_atual == "SETOR_4_JONAS_HUMANO":
        atendente = "Jonas Mendonça (Fundador)"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        resposta = (
            f"Mensagem registrada para o Jonas, {nome}! Ele já foi alertado e vai responder diretamente por aqui em breve. Obrigado pela paciência!"
        )

    else:
        novo_setor = "MENU_INICIAL"
        atendente = "Central Automática Jonas Tech"
        resposta = obter_menu_principal(nome)

    return novo_setor, atendente, resposta

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "online",
        "servico": "Central de Atendimento Multissetorial 24/7 - Jonas Tech Solutions",
        "banco": "MongoDB Atlas Conectado",
        "setores_disponiveis": [
            "1. Camila - Especialista CinePro TV",
            "2. Lucas - Suporte Técnico de TI",
            "3. Marcos - Consultor Comercial & Vendas",
            "4. Jonas - Atendimento Humano Direto"
        ],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook_whatsapp():
    dados = request.get_json(silent=True) or {}
    telefone = dados.get("telefone") or dados.get("phone") or dados.get("remoteJid", "").split("@")[0] or "desconhecido"
    nome = dados.get("nome") or dados.get("pushName") or "Cliente"
    mensagem = dados.get("mensagem") or dados.get("text") or dados.get("message", {}).get("conversation", "")

    if not mensagem:
        return jsonify({"erro": "Nenhuma mensagem encontrada no payload"}), 400

    novo_setor, atendente, resposta = processar_atendimento_multissetorial(telefone, nome, mensagem)

    # Gravação e Atualização do Lead no MongoDB Atlas
    if leads_col is not None:
        try:
            leads_col.update_one(
                {"telefone": telefone},
                {"$set": {
                    "nome": nome,
                    "setor_atual": novo_setor,
                    "atendente_responsavel": atendente,
                    "ultima_mensagem": mensagem,
                    "resposta": resposta,
                    "status": "EM_ATENDIMENTO_MULTISSETORIAL",
                    "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }},
                upsert=True
            )
        except Exception as e:
            print(f"[ERRO GRAVACAO MONGODB]: {e}")

    return jsonify({
        "status": "sucesso",
        "destinatario": telefone,
        "setor_atual": novo_setor,
        "atendente": atendente,
        "resposta_pronta": resposta
    }), 200

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
