"""
AGENTE DE WHATSAPP NA NUVEM (API REST / WEBHOOK 24/7)
Jonas Tech Solutions • Conectado ao MongoDB Atlas
"""

import os
import json
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

# CONFIGURACOES DO BANCO DE DADOS NA NUVEM (MONGODB ATLAS)
USUARIO = os.getenv("MONGO_USER", "jonasskynet_db_user")
SENHA_BRUTA = os.getenv("MONGO_PASS", "nk1NBq5GW3WJmg4v")
SENHA_CODIFICADA = urllib.parse.quote_plus(SENHA_BRUTA)
CLUSTER = os.getenv("MONGO_CLUSTER", "cluster0.4dnngrl.mongodb.net")
URI = f"mongodb+srv://{USUARIO}:{SENHA_CODIFICADA}@{CLUSTER}/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(URI, server_api=ServerApi("1"), serverSelectionTimeoutMS=5000)
    db = client["sistema_comercial_db"]
    leads_col = db["leads_whatsapp"]
    print("[NUVEM] Conexao com MongoDB Atlas inicializada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None

def classificar_intencao(texto):
    t = texto.lower()
    # 1. Ofertas e Afiliado Mercado Livre (checar antes de 'mercado' genérico)
    if any(p in t for p in ["achadinho", "achados", "promoção", "promocao", "oferta", "desconto", "recomenda", "comprar", "afiliado", "mercado livre", "loja online"]):
        return "OFERTAS_AFILIADO"
    # 2. Fabrica Dark
    elif any(p in t for p in ["video", "dark", "canal", "youtube", "tiktok", "reels"]):
        return "FABRICA_DARK"
    # 3. Rastreador de Precos E-commerce
    elif any(p in t for p in ["rastreador", "concorrente", "espiao", "preço", "preco"]):
        return "RASTREADOR_PRECOS"
    # 4. Sistema Comercial R$ 150
    elif any(p in t for p in ["sistema", "estoque", "caixa", "150", "caderno", "comercial", "mercadinho", "mercado"]):
        return "SISTEMA_COMERCIAL"
    else:
        return "ATENDIMENTO_GERAL"

def gerar_resposta_comercial(nome_cliente, mensagem):
    intencao = classificar_intencao(mensagem)
    saudacao = f"Olá, {nome_cliente}! Tudo bem? Aqui é o atendimento automático da Jonas Tech Solutions."

    if intencao == "SISTEMA_COMERCIAL":
        resposta = (
            f"{saudacao}\n\n"
            f"Perfeito! Nosso *Sistema Comercial de Gestão & Estoque* foi desenhado para quem quer sair do caderno e ter controle total:\n"
            f"✅ Acesso direto no celular ou PC (sem precisar instalar nada);\n"
            f"✅ Controle de produtos com margem de lucro automática;\n"
            f"✅ Histórico de vendas e registro de PIX instantâneo;\n"
            f"✅ Banco de dados 100% na nuvem seguro (MongoDB Atlas).\n\n"
            f"💰 *Investimento:* R$ 150 (taxa única de implantação, SEM MENSALIDADE).\n\n"
            f"Deseja que eu te envie o link de teste para você mexer na demonstração agora?"
        )
    elif intencao == "FABRICA_DARK":
        resposta = (
            f"{saudacao}\n\n"
            f"Excelente! Produzimos *Vídeos Dark Virais de Alta Retenção* para YouTube Shorts e TikTok:\n"
            f"🎬 Animação fluida em 24fps com IA de vídeo (sem fotos paradas);\n"
            f"🎙️ 3 Camadas de Áudio: Voz teatral + Trilha sonora + Efeitos sonoros foley;\n"
            f"⚡ Ganchos magnéticos nos primeiros 3 segundos para reter audiência.\n\n"
            f"💰 Pacotes a partir de R$ 50 por vídeo ou R$ 350 o lote com 10 vídeos prontos."
        )
    elif intencao == "RASTREADOR_PRECOS":
        resposta = (
            f"{saudacao}\n\n"
            f"Ótimo! O *Rastreador de E-commerce* monitora o Mercado Livre e Shopee 24h por dia:\n"
            f"📈 Te avisa no WhatsApp assim que seu concorrente mexer no preço ou o estoque dele acabar;\n"
            f"💰 Mensalidade de apenas R$ 90/mês para monitorar seus principais produtos."
        )
    elif intencao == "OFERTAS_AFILIADO":
        resposta = (
            f"{saudacao}\n\n"
            f"🛍️ *Achadinhos e Ofertas Recomendadas no Mercado Livre!*\n\n"
            f"Separamos as melhores oportunidades verificadas e com até 50% de desconto:\n"
            f"👉 *Vitrine Oficial do Jonas:* https://www.mercadolivre.com.br/social/detonadormendona\n\n"
            f"🔥 *Achadinho em Destaque:* Inversor 1000W Onda Senoidal Pura 12V/220V\n"
            f"🔗 *Link direto com desconto:* https://meli.la/2Uuzpmf\n\n"
            f"Qual produto ou ferramenta você precisa hoje? Me diga que busco o melhor link para você!"
        )
    else:
        resposta = (
            f"{saudacao}\n\n"
            f"Como posso ajudar o seu negócio hoje?\n\n"
            f"1️⃣ Sistema Comercial de Estoque e Vendas (R$ 150)\n"
            f"2️⃣ Produção de Vídeos Virais Dark para Redes Sociais\n"
            f"3️⃣ Rastreador de Preços de Concorrentes\n"
            f"4️⃣ Achadinhos e Ofertas Verificadas (Mercado Livre)\n\n"
            f"Digite o número ou me diga o que procura!"
        )

    return intencao, resposta

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "online",
        "servico": "Agente WhatsApp na Nuvem - Jonas Tech Solutions",
        "banco": "MongoDB Atlas Conectado",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook_whatsapp():
    """
    Endpoint universal para receber mensagens de provedores de WhatsApp (Evolution API, Z-API, Baileys ou Meta Cloud API)
    """
    dados = request.get_json(silent=True) or {}
    
    # Suporta diferentes formatos de payload
    telefone = dados.get("telefone") or dados.get("phone") or dados.get("remoteJid", "").split("@")[0] or "desconhecido"
    nome = dados.get("nome") or dados.get("pushName") or "Amigo(a)"
    mensagem = dados.get("mensagem") or dados.get("text") or dados.get("message", {}).get("conversation", "")
    
    if not mensagem:
        return jsonify({"erro": "Nenhuma mensagem encontrada no payload"}), 400

    intencao, resposta = gerar_resposta_comercial(nome, mensagem)

    # Registro do Lead no MongoDB Atlas
    if leads_col is not None:
        try:
            leads_col.update_one(
                {"telefone": telefone},
                {"$set": {
                    "nome": nome,
                    "intencao": intencao,
                    "ultima_mensagem": mensagem,
                    "resposta": resposta,
                    "status": "ATENDIDO_NUVEM_24H",
                    "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }},
                upsert=True
            )
        except Exception as e:
            print(f"[ERRO GRAVACAO MONGODB]: {e}")

    return jsonify({
        "status": "sucesso",
        "destinatario": telefone,
        "intencao": intencao,
        "resposta_pronta": resposta
    }), 200

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
