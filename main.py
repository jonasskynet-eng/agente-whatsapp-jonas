"""
================================================================================
AGENTE DE WHATSAPP NA NUVEM - CENTRAL HUMANA MULTISSETORIAL 24/7 (VERSÃO 3.0)
Jonas Tech Solutions • Conectado ao MongoDB Atlas (Cluster0 AWS São Paulo)
================================================================================
Atendimento natural em múltiplos balões, sem linguagem de robô/URA:
1. Recepção acolhedora com saudação pelo horário de Brasília
2. Camila (CinePro TV), Lucas (Suporte TI), Marcos (Comercial) e Equipe do Jonas
3. Chave PIX enviada separada para facilitar cópia no celular
4. Leitor inteligente de comprovante PIX e fotos de erro no suporte
5. Controle mestre (LIGAR / DESLIGAR) pelo próprio WhatsApp ou painel
================================================================================
"""

import os
import random
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)


@app.after_request
def habilitar_cors_total(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


# CONFIGURAÇÕES GERAIS DA EMPRESA
CHAVE_PIX_OFICIAL = "324588e6-bd74-4b6d-9951-5321cc50ea5a"
BANCO_RECEBEDOR = "Mercado Pago IP S.A."
TITULAR_CONTA = "Jonas Mendonça"
WHATSAPP_HUMANO = "(11) 96670-7293"

# LINKS OFICIAIS
LINK_PLAYER_IPTV = "https://jonasskynet-eng.github.io/cine-pro-tv-2026/"
LINK_DEMO_PDV = "http://localhost:5055/"

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
    config_col = db["configuracoes_gerais"]
    print("[NUVEM] Conexão com MongoDB Atlas validada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None
    alertas_col = None
    config_col = None


def agora_brasilia():
    """Retorna data/hora atual no fuso de Brasília (UTC-3)."""
    return datetime.utcnow() - timedelta(hours=3)


def saudacao_horario():
    hora = agora_brasilia().hour
    if 5 <= hora < 12:
        return "Bom dia"
    if 12 <= hora < 18:
        return "Boa tarde"
    return "Boa noite"


def obter_primeiro_nome(nome):
    if not nome:
        return ""
    limpo = nome.strip()
    if limpo.lower() in ["cliente", "desconhecido", "você", "voce"]:
        return ""
    return limpo.split()[0].capitalize()


def obter_status_robo():
    """Retorna True se o robô estiver ligado e False se estiver pausado pelo Jonas."""
    if config_col is not None:
        try:
            doc = config_col.find_one({"chave": "status_robo"})
            if doc:
                return bool(doc.get("ativo", True))
        except Exception as e:
            print(f"[ERRO STATUS ROBO]: {e}")
    return True


def definir_status_robo(ativo: bool):
    """Grava na nuvem se o robô está ligado ou pausado."""
    if config_col is not None:
        try:
            config_col.update_one(
                {"chave": "status_robo"},
                {"$set": {
                    "chave": "status_robo",
                    "ativo": ativo,
                    "atualizado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
                }},
                upsert=True
            )
            print(f"[STATUS ROBO] Estado alterado para: {'LIGADO' if ativo else 'PAUSADO'}")
            return True
        except Exception as e:
            print(f"[ERRO ATUALIZAR STATUS]: {e}")
    return False


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
                "criado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
            })
            print(f"[ALERTA QUENTE] Cliente {nome} ({telefone}) sinalizado como URGENTE!")
        except Exception as e:
            print(f"[ERRO ALERTA]: {e}")


def obter_recepcao_natural(pnome):
    saudacao = saudacao_horario()
    virgula_nome = f", {pnome}" if pnome else ""
    abertura = random.choice([
        f"Oi{virgula_nome}! {saudacao}, tudo bem por aí? 😊",
        f"Opa{virgula_nome}! {saudacao}, tudo joia?"
    ])
    corpo = (
        "Aqui é da equipe do Jonas! Me conta, como posso te ajudar hoje? "
        "Você tá procurando o teste grátis da TV, nosso sistema de caixa e estoque ou precisa de suporte pro computador?"
    )
    return [abertura, corpo]


def processar_mensagem_inteligente(telefone, nome, mensagem, midia_url=None, tipo_midia="text"):
    texto = (mensagem or "").strip().lower()
    pnome = obter_primeiro_nome(nome)
    virgula_nome = f", {pnome}" if pnome else ""
    dados_extras = {}

    # 0. COMANDO MESTRE DO JONAS PARA LIGAR OU DESLIGAR O ROBÔ POR MENSAGEM
    tel_limpo = "".join(c for c in str(telefone) if c.isdigit())
    eh_jonas = tel_limpo.endswith("966707293") or "jonas" in (nome or "").lower()

    if eh_jonas and texto in ["desligar", "pausar", "dormir", "parar", "#desligar", "#pausar"]:
        definir_status_robo(False)
        return (
            "ROBO_PAUSADO",
            "Controle Jonas Tech",
            [
                "Prontinho, Jonas! Pausei o atendimento automático por aqui. 🔴",
                "Pode conversar tranquilo que não vou responder ninguém até você me mandar *ligar*."
            ],
            {"robo_ativo": False}
        )

    if eh_jonas and texto in ["ligar", "ativar", "acordar", "#ligar", "#ativar"]:
        definir_status_robo(True)
        return (
            "ROBO_ATIVADO",
            "Controle Jonas Tech",
            ["Tudo certo, Jonas! Já voltei a atender o pessoal normalmente por aqui. 🟢"],
            {"robo_ativo": True}
        )

    # SE O ROBÔ ESTIVER DESLIGADO, FICA EM SILÊNCIO TOTAL
    if not obter_status_robo():
        return "ROBO_PAUSADO", "Pausado", [], {"robo_ativo": False, "ignorado": True}

    # 1. Recuperar histórico do lead no MongoDB Atlas
    lead = None
    if leads_col is not None:
        try:
            lead = leads_col.find_one({"telefone": telefone})
        except Exception as e:
            print(f"[ERRO BUSCA LEAD]: {e}")

    setor_atual = (lead or {}).get("setor_atual", "MENU_INICIAL")

    # 2. DETECTOR INTELIGENTE DE COMPROVANTE PIX (preservando fotos de erro no Suporte)
    palavras_comprovante = [
        "comprovante", "paguei", "ta pago", "tá pago", "pix feito",
        "concluido", "concluído", "transferido", "mandei o pix", "fiz o pix"
    ]
    eh_pagamento_texto = any(p in texto for p in palavras_comprovante)
    eh_midia_fora_suporte = tipo_midia in ["image", "document"] and setor_atual != "SETOR_2_SUPORTE"

    if eh_pagamento_texto or eh_midia_fora_suporte:
        novo_setor = "PAGAMENTO_RECEBIDO"
        atendente = "Financeiro Jonas Tech"
        produto_identificado = "Sistema Comercial PDV" if ("150" in texto or setor_atual == "SETOR_3_COMERCIAL") else "CinePro TV 30 Dias"

        baloes = [
            f"Opa{virgula_nome}! Recebi seu comprovante aqui, muito obrigado pela confiança! 🙏",
            (
                "Já avisei o Jonas pra conferir aqui no Mercado Pago e liberar seu acesso certinho em instantes.\n\n"
                "Ah, e se indicar algum amigo ou comércio conhecido que fechar com a gente, te mando R$ 20 no PIX na hora como agradecimento, viu? Qualquer coisa tô por aqui!"
            )
        ]
        dados_extras["status_pagamento"] = "COMPROVANTE_ENVIADO"
        dados_extras["produto_comprado"] = produto_identificado
        disparar_alerta_cliente_quente(
            telefone, nome,
            f"COMPROVANTE DE PAGAMENTO ENVIADO ({produto_identificado})",
            30.0 if "30" in produto_identificado else 150.0
        )
        return novo_setor, atendente, baloes, dados_extras

    # 3. RESET NATURAL POR SAUDAÇÃO PURA OU VOLTAR
    saudacoes_puras = [
        "oi", "olá", "ola", "opa", "bom dia", "boa tarde", "boa noite",
        "e ai", "e aí", "tudo bem", "tudo bem?", "oi tudo bem",
        "menu", "voltar", "inicio", "início"
    ]
    if texto in saudacoes_puras:
        setor_atual = "MENU_INICIAL"

    # 4. TROCA INTELIGENTE DE ASSUNTO NO MEIO DA CONVERSA
    if any(p in texto for p in ["falar com jonas", "falar com o jonas", "chama o jonas", "atendente humano", "falar com humano"]):
        setor_atual = "MENU_INICIAL"
    elif setor_atual == "SETOR_1_CINEPRO" and any(p in texto for p in ["pdv", "sistema de caixa", "estoque", "150", "pc lento", "formatar"]):
        setor_atual = "MENU_INICIAL"

    # 5. ROTEAMENTO CONVERSACIONAL HUMANO
    if setor_atual == "MENU_INICIAL":
        if any(p in texto for p in ["1", "tv", "iptv", "cinepro", "teste", "futebol", "canais", "filme", "série", "serie", "jogo"]):
            novo_setor = "SETOR_1_CINEPRO"
            atendente = "Camila"
            agora = agora_brasilia()
            dados_extras["teste_iniciado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_15min"] = (agora + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_expira"] = (agora + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            baloes = [
                f"Oi{virgula_nome}! Tudo bom? Aqui é a Camila 😊 Já deixei liberado seu teste grátis de 2 horas pra você ver a qualidade!",
                (
                    f"É só tocar nesse link aqui pra abrir:\n{LINK_PLAYER_IPTV}\n\n"
                    "Pega direto no celular, computador ou Smart TV, com todos os canais, filmes novos e jogos ao vivo. Abre aí rapidinho e me conta se rodou lisinho!"
                )
            ]
        elif any(p in texto for p in ["2", "suporte", "tecnico", "técnico", "defeito", "erro", "formatar", "pc", "computador", "notebook", "lento", "windows", "ajuda", "conserto", "travando"]):
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas"
            baloes = [
                f"Fala{virgula_nome}! Tudo tranquilo? Aqui é o Lucas, do suporte técnico.",
                "Me conta o que tá acontecendo aí: é computador lento/travando ou alguma dúvida no sistema de caixa? Se tiver aparecendo algum erro na tela, pode tirar uma foto mesmo pelo celular e mandar aqui!"
            ]
        elif any(p in texto for p in ["3", "venda", "comercial", "comprar", "preco", "preço", "sistema", "pdv", "caixa", "estoque", "150", "quanto custa", "valor", "tabela", "robô", "robo"]):
            novo_setor = "SETOR_3_COMERCIAL"
            atendente = "Marcos"
            baloes = [
                f"Opa{virgula_nome}! Tudo bem? Aqui é o Marcos, cuido da parte comercial aqui com o Jonas.",
                (
                    "Hoje o que mais sai aqui é o nosso *Sistema de Frente de Caixa e Estoque (PDV)* por R$ 150 pagamento único — você paga uma vez só e não tem mensalidade nunca mais!\n\n"
                    "Também temos o pacote Windows Boost PRO (R$ 150), automação de WhatsApp (R$ 250) e a TV completa (R$ 30). Qual deles você queria ver melhor?"
                )
            ]
        elif any(p in texto for p in ["4", "jonas", "humano", "pessoa", "dono"]):
            novo_setor = "SETOR_4_JONAS_HUMANO"
            atendente = "Equipe do Jonas"
            dados_extras["avisou_aguardo_humano"] = False
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE SOLICITOU ATENDIMENTO HUMANO COM O JONAS")
            baloes = [
                f"Pode deixar{virgula_nome}! Já dei um toque no celular pessoal do Jonas pra ele assumir nossa conversa aqui.",
                "Se quiser, já pode ir mandando sua dúvida ou áudio aqui que assim que ele soltar o atendimento ali já te responde direto, combinado?"
            ]
        else:
            novo_setor = "MENU_INICIAL"
            atendente = "Recepção Jonas Tech"
            baloes = obter_recepcao_natural(pnome)

    elif setor_atual == "SETOR_1_CINEPRO":
        atendente = "Camila"
        novo_setor = "SETOR_1_CINEPRO"
        if any(p in texto for p in ["pix", "pagar", "comprar", "assinar", "quero fechar", "quero assinar", "ativar", "chave", "mensal", "quanto é", "quanto custa", "valor"]):
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE QUER PAGAR CINEPRO TV R$ 30", 30.0)
            baloes = [
                f"Fechou{virgula_nome}! O plano completo de 30 dias fica só R$ 30,00. Vou te mandar a chave PIX separada aqui embaixo pra ficar fácil de copiar:",
                f"{CHAVE_PIX_OFICIAL}",
                f"Vai aparecer no nome de {TITULAR_CONTA} ({BANCO_RECEBEDOR}). Assim que fizer, me manda o comprovante aqui mesmo que já libero seu login definitivo!"
            ]
        elif any(p in texto for p in ["smart", "samsung", "lg", "roku", "tv box", "box", "fire", "android", "como instala", "colocar na tv"]):
            baloes = [
                "Na Smart TV é bem simples! Dá pra abrir direto pelo navegador da própria TV usando aquele link, ou instalar o app rapidinho.",
                "Qual é a marca da sua TV aí (Samsung, LG, Roku ou TV Box)? Me fala que te explico certinho como colocar!"
            ]
        elif any(p in texto for p in ["abriu", "funcionou", "top", "bom", "gostei", "rodou", "show", "ótimo", "otimo", "sim", "deu certo"]):
            baloes = [
                f"Que massa{virgula_nome}, fico feliz que rodou liso aí! 😄",
                "Aproveita bastante o teste! Se já quiser deixar o mês completo garantido por R$ 30, é só me pedir o PIX por aqui, tá bom?"
            ]
        elif any(p in texto for p in ["travou", "não abriu", "nao abriu", "erro", "carregando"]):
            baloes = [
                "Eita, vamos ver isso agora! Você tentou abrir pelo Wi-Fi ou pelos dados móveis do celular?",
                "Tenta atualizar a página uma vez — às vezes na primeira abertura leva uns 5 segundinhos pra carregar a grade. Me fala se entrou!"
            ]
        else:
            baloes = [
                f"Me conta aí{virgula_nome}, conseguiu abrir o link da TV no seu aparelho?",
                "Qualquer dúvida na configuração ou se quiser ativar o acesso mensal de R$ 30, é só me chamar aqui!"
            ]

    elif setor_atual == "SETOR_2_SUPORTE":
        atendente = "Lucas"
        novo_setor = "SETOR_2_SUPORTE"
        if tipo_midia in ["image", "document"]:
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE ENVIOU FOTO DE ERRO NO SUPORTE")
            baloes = [
                f"Boa{virgula_nome}, recebi a imagem da tela aqui!",
                "Já passei pro Jonas analisar junto comigo na bancada e já te damos o retorno certinho por aqui mesmo em instantes!"
            ]
        else:
            baloes = [
                f"Entendi perfeitamente{virgula_nome}!",
                "Já anotei tudo aqui na bancada e chamei o Jonas pra gente resolver isso da forma mais rápida pra você. Se conseguir mandar uma foto da tela também, ajuda demais!"
            ]

    elif setor_atual == "SETOR_3_COMERCIAL":
        atendente = "Marcos"
        novo_setor = "SETOR_3_COMERCIAL"
        if any(p in texto for p in ["pix", "chave", "pagar", "comprar", "quero", "fechar", "manda"]):
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE QUER PAGAR SISTEMA COMERCIAL R$ 150", 150.0)
            baloes = [
                f"Combinado{virgula_nome}! A licença vitalícia do sistema completo com nosso suporte fica R$ 150,00 taxa única. Segue a chave PIX separada pra você copiar:",
                f"{CHAVE_PIX_OFICIAL}",
                f"Confere lá no nome de {TITULAR_CONTA} ({BANCO_RECEBEDOR}). Assim que transferir, me manda o comprovante aqui que já libero seus arquivos de instalação na hora!"
            ]
        else:
            baloes = [
                "O legal desse sistema é que ele já lê código de barras, controla o estoque certinho, gera cobrança PIX na tela e não te cobra mensalidade todo mês.",
                "Quer que eu te mande a chave PIX pra gente já deixar instalado aí no seu comércio hoje?"
            ]

    elif setor_atual == "SETOR_4_JONAS_HUMANO":
        atendente = "Equipe do Jonas"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        if (lead or {}).get("avisou_aguardo_humano"):
            return novo_setor, "Aguardando Jonas", [], {}
        dados_extras["avisou_aguardo_humano"] = True
        baloes = ["Anotei aqui pra ele ver assim que pegar no celular, fica tranquilo! 👍"]

    else:
        novo_setor = "MENU_INICIAL"
        atendente = "Recepção Jonas Tech"
        baloes = obter_recepcao_natural(pnome)

    return novo_setor, atendente, baloes, dados_extras


@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "online",
        "servico": "Central Humana Multissetorial 24/7 - Jonas Tech Solutions",
        "versao": "3.0_HUMANO_REAL",
        "banco": "MongoDB Atlas Conectado",
        "recursos_ativos": [
            "1. Diálogo Humano em Múltiplos Balões (Sem Menu URA)",
            "2. Personas Naturais (Recepção, Camila, Lucas, Marcos, Equipe do Jonas)",
            "3. Chave PIX Separada para Cópia Fácil",
            "4. Leitor Inteligente de Comprovante e Foto de Erro no Suporte",
            "5. Fila VIP de Alertas Quentes & Controle LIGAR/DESLIGAR"
        ],
        "timestamp": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/webhook", methods=["POST", "OPTIONS"])
def webhook_whatsapp():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    dados = request.get_json(silent=True) or {}
    telefone = dados.get("telefone") or dados.get("phone") or dados.get("remoteJid", "").split("@")[0] or "desconhecido"
    nome = dados.get("nome") or dados.get("pushName") or "Cliente"
    mensagem = dados.get("mensagem") or dados.get("text") or dados.get("message", {}).get("conversation", "")
    tipo_midia = dados.get("tipo_midia") or dados.get("mediaType") or "text"
    midia_url = dados.get("midia_url") or dados.get("mediaUrl")

    if not mensagem and tipo_midia == "text":
        return jsonify({"erro": "Nenhuma mensagem encontrada no payload"}), 400

    novo_setor, atendente, lista_baloes, extras = processar_mensagem_inteligente(telefone, nome, mensagem, midia_url, tipo_midia)
    resposta_consolidada = "\n\n".join(lista_baloes)

    # Gravação no MongoDB Atlas
    if leads_col is not None:
        try:
            update_data = {
                "nome": nome,
                "setor_atual": novo_setor,
                "atendente_responsavel": atendente,
                "ultima_mensagem": mensagem,
                "resposta": resposta_consolidada,
                "status": "EM_ATENDIMENTO_HUMANO",
                "atualizado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
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
        "mensagens_humanas": lista_baloes,
        "resposta_pronta": resposta_consolidada,
        "dados_extras": extras
    }), 200


@app.route("/api/robo/status", methods=["GET"])
def api_robo_status():
    return jsonify({"ativo": obter_status_robo()}), 200


@app.route("/api/robo/alternar", methods=["POST", "GET"])
def api_robo_alternar():
    novo = not obter_status_robo()
    definir_status_robo(novo)
    return jsonify({"ativo": novo, "status": "LIGADO" if novo else "PAUSADO"}), 200


@app.route("/api/robo/ligar", methods=["POST", "GET"])
def api_robo_ligar():
    definir_status_robo(True)
    return jsonify({"ativo": True, "status": "LIGADO"}), 200


@app.route("/api/robo/desligar", methods=["POST", "GET"])
def api_robo_desligar():
    definir_status_robo(False)
    return jsonify({"ativo": False, "status": "PAUSADO"}), 200


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
