"""
================================================================================
AGENTE DE WHATSAPP NA NUVEM - CENTRAL HUMANA & RELATÓRIOS 24/7 (VERSÃO 5.0)
Jonas Tech Solutions • Conectado ao MongoDB Atlas (Cluster0 AWS São Paulo)
================================================================================
Recursos Ativos:
1. Linguagem 100% humana, natural e fluida (sem cara de robô ou URA)
2. Camila (CinePro TV): PIX blindado, OCR/PDF, login 30 dias e aviso ao Jonas
3. Lucas (Suporte TI): Diagnóstico real + registro técnico para e-mail
4. Marcos (Comercial): Consultoria de melhorias, combos e PIX blindado
5. Coleção eventos_relatorio_email + /api/relatorio-email (acumulado do dia)
================================================================================
"""

import hashlib
import hmac
import json
import math
import os
import random
import re
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from motor_pix import gerar_payload_pix, gerar_url_qrcode_instantaneo

app = Flask(__name__)


@app.after_request
def habilitar_cors_total(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Requested-With,X-Frota-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


# CONFIGURAÇÕES GERAIS DA EMPRESA
CHAVE_PIX_OFICIAL = "324588e6-bd74-4b6d-9951-5321cc50ea5a"
BANCO_RECEBEDOR = "Mercado Pago IP S.A."
TITULAR_CONTA = "Jonas Mendonça"
CIDADE_RECEBEDOR = "SAO PAULO"
WHATSAPP_HUMANO = "(11) 96670-7293"

# LINKS OFICIAIS
LINK_PLAYER_IPTV = "https://agente-whatsapp-jonas.onrender.com/tv"
LINK_DEMO_PDV = "https://agente-whatsapp-jonas.onrender.com/pdv"

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
    assinantes_col = db["assinantes_cinepro"]
    comprovantes_col = db["comprovantes_validados"]
    eventos_email_col = db["eventos_relatorio_email"]
    vendas_pdv_col = db["historico_vendas"]
    col_vendas = db["historico_vendas"]
    col_produtos = db["estoque_produtos"]
    col_fechamentos = db["fechamentos_caixa"]
    col_movimentacoes = db["movimentacoes_caixa"]
    col_clientes = db["clientes_crm"]
    col_custos = db["custos_fixos_loja"]
    col_veiculos = db["veiculos_frotas"]
    col_apolices = db["apolices_seguros"]
    col_chat_web = db["chat_web_historico"]
    auditoria_col = db["auditoria_agentes"]
    col_custos_escala = db["custos_operacionais_ecossistema"]
    col_metas_escala = db["plano_escala_metas"]
    print("[NUVEM] Conexão com MongoDB Atlas validada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None
    alertas_col = None
    config_col = None
    assinantes_col = None
    comprovantes_col = None
    eventos_email_col = None
    auditoria_col = None
    col_custos_escala = None
    col_metas_escala = None
    vendas_pdv_col = None
    col_vendas = None
    col_produtos = None
    col_fechamentos = None
    col_movimentacoes = None
    col_clientes = None
    col_custos = None
    col_veiculos = None
    col_apolices = None
    col_chat_web = None


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


def normalizar_ascii(texto):
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_giria_whatsapp(texto):
    """Normaliza abreviações e erros comuns de digitação no WhatsApp mantendo ASCII minúsculo."""
    base = normalizar_ascii((texto or "").strip().lower())
    return re.sub(
        r"\b(?:no|n|num|naum)\s+(pega|funciona|abre|entra|carrega|vai|da|tem|conecta|baixa|instala|consegue|consigo|aparece|roda|aceita)\b",
        r"nao \1",
        base,
    )


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
        except Exception as e:
            print(f"[ERRO ALERTA]: {e}")


def registrar_evento_email(tipo, cliente, telefone, valor=0.0, descricao="", suporte_feito=""):
    """Registra pagamentos e atendimentos técnicos para consolidar no relatório por e-mail."""
    if eventos_email_col is None:
        return
    try:
        agora = agora_brasilia()
        eventos_email_col.insert_one({
            "id_evento": f"EVT-{int(datetime.utcnow().timestamp() * 1000)}-{random.randint(100, 999)}",
            "tipo": tipo,
            "data_dia": agora.strftime("%Y-%m-%d"),
            "horario": agora.strftime("%H:%M:%S"),
            "cliente": cliente or "Cliente",
            "telefone": str(telefone),
            "valor": float(valor or 0.0),
            "descricao": (descricao or "")[:300],
            "suporte_feito": (suporte_feito or "")[:350],
            "enviado_email": False
        })
    except Exception as e:
        print(f"[ERRO EVENTO EMAIL]: {e}")


def calcular_dias_por_valor_iptv(valor_pago):
    """Mapeia o valor pago (TV ou App de Rádio) para a duração exata da assinatura em dias."""
    v = float(valor_pago or 30.0)
    if v >= 195.0:
        return 365
    if v >= 145.0:
        return 240
    if v >= 115.0:
        return 180
    if v >= 80.0:
        return 120
    if v >= 60.0:
        return 90
    if v >= 40.0:
        return 60
    return 30


def gerar_credenciais_cinepro(telefone, nome, valor_pago=30.0, resumo_comprovante="", dias=None, horas=None):
    """Gera usuário único e senha de 6 dígitos e grava no MongoDB por horas (teste 2h) ou dias."""
    pnome_limpo = re.sub(r"[^a-z0-9]", "", normalizar_ascii(obter_primeiro_nome(nome)).lower())
    base_nome = pnome_limpo[:10] if pnome_limpo else "cliente"
    digitos_tel = "".join(c for c in str(telefone or "") if c.isdigit())
    ultimos4 = digitos_tel[-4:] if len(digitos_tel) >= 4 else str(random.randint(1000, 9999))
    prefixo = "t2h_" if horas else ""
    usuario = f"{prefixo}{base_nome}{ultimos4}"
    senha = str(random.randint(100000, 999999))

    agora = agora_brasilia()
    if horas:
        delta = timedelta(hours=float(horas))
        duracao_label = f"{int(horas)} horas"
    else:
        qtd_dias = int(dias or calcular_dias_por_valor_iptv(valor_pago))
        delta = timedelta(days=qtd_dias)
        duracao_label = f"{qtd_dias} dias"

    expira_dt = agora + delta
    expira_ts = int((datetime.utcnow() + delta).timestamp() * 1000)

    if assinantes_col is not None:
        try:
            assinantes_col.update_one(
                {"usuario": usuario},
                {"$set": {
                    "usuario": usuario,
                    "senha": senha,
                    "telefone": str(telefone),
                    "nome": nome or "Assinante",
                    "status": "ATIVO",
                    "tipo_plano": "TESTE_2H" if horas else f"IPTV_{duracao_label.upper().replace(' ', '_')}",
                    "valor_pago": float(valor_pago),
                    "resumo_comprovante": (resumo_comprovante or "")[:300],
                    "criado_em": agora.strftime("%Y-%m-%d %H:%M:%S"),
                    "expira_em": expira_dt.strftime("%d/%m/%Y às %H:%M"),
                    "expira_iso": expira_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "expira_ts": expira_ts
                }},
                upsert=True
            )
        except Exception as e:
            print(f"[ERRO GRAVAR ASSINANTE]: {e}")

    formato_validade = "%d/%m/%Y às %H:%M" if horas else "%d/%m/%Y"
    return usuario, senha, expira_dt.strftime(formato_validade)


def conferir_pix_mercadopago(valor_esperado):
    """
    Consulta a API oficial do Mercado Pago para conferir se o pagamento PIX
    caiu na conta do Jonas nos últimos 90 minutos.
    Requer MERCADO_PAGO_ACCESS_TOKEN configurado nas variáveis de ambiente.
    """
    token = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN") or os.environ.get("MP_ACCESS_TOKEN")
    if not token:
        return {"consultado": False, "motivo": "TOKEN_NAO_CONFIGURADO"}
    try:
        url = "https://api.mercadopago.com/v1/payments/search?sort=date_created&criteria=desc&limit=15"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            dados = json.loads(resp.read().decode("utf-8"))

        resultados = dados.get("results") or []
        agora_utc = datetime.now(timezone.utc)
        for pag in resultados:
            if pag.get("status") == "approved":
                valor_pag = float(pag.get("transaction_amount") or 0)
                if abs(valor_pag - float(valor_esperado)) <= 0.05:
                    data_criado_str = pag.get("date_created")
                    if data_criado_str:
                        dt_pag = datetime.fromisoformat(data_criado_str.replace("Z", "+00:00"))
                        diferenca_min = (agora_utc - dt_pag).total_seconds() / 60
                        if diferenca_min <= 90:
                            return {
                                "consultado": True,
                                "aprovado_banco": True,
                                "id_pagamento": pag.get("id"),
                                "metodo": pag.get("payment_method_id"),
                                "valor": valor_pag,
                                "detalhes": pag.get("description", "")
                            }
        return {"consultado": True, "aprovado_banco": False, "motivo": "NAO_ENCONTRADO_NO_EXTRATO"}
    except Exception as e:
        print(f"[ERRO API MERCADO PAGO]: {e}")
        return {"consultado": True, "aprovado_banco": False, "erro": str(e)}


def analisar_comprovante_pix(texto_ocr, texto_msg, setor_atual, plano_salvo="30"):
    """Analisa texto extraído de imagem/PDF de comprovante PIX e evita reuso."""
    combinado = f"{texto_ocr or ''} {texto_msg or ''}".lower()
    combinado_ascii = normalizar_ascii(combinado)

    tem_titular_jonas = any(k in combinado_ascii for k in ["jonas", "mendonca", "324588e6"])
    tem_sinal_pix = any(k in combinado_ascii for k in [
        "pix", "comprovante", "transfer", "pagamento", "valor",
        "r$", "conclu", "realizado", "enviado", "mercado pago", "autentica"
    ])

    try:
        valor_padrao = float(plano_salvo) if setor_atual == "SETOR_3_COMERCIAL" and plano_salvo else 30.0
    except (TypeError, ValueError):
        valor_padrao = 30.0

    valor_detectado = valor_padrao
    m_valor = re.search(r"(?:r\$\s*|\b)(240|220|200|160|150|130|120|90|85|70|65|50|45|30|25)(?:[,\.]00)?\b", combinado_ascii)
    if m_valor:
        valor_detectado = float(m_valor.group(1))

    m_e2e = re.search(r"\be\d{8}[a-z0-9]{15,35}\b", combinado_ascii)
    chave_unica = None
    if m_e2e:
        chave_unica = m_e2e.group(0)
    elif len((texto_ocr or "").strip()) > 30:
        chave_unica = hashlib.sha256(texto_ocr.strip().encode("utf-8", errors="ignore")).hexdigest()

    ja_usado = False
    if chave_unica and comprovantes_col is not None:
        try:
            if comprovantes_col.find_one({"chave_unica": chave_unica}):
                ja_usado = True
        except Exception as e:
            print(f"[ERRO CHECAR COMPROVANTE]: {e}")

    validacao_banco = conferir_pix_mercadopago(valor_detectado)
    if validacao_banco.get("aprovado_banco"):
        aprovado = True
        origem_validacao = "BANCO_MERCADO_PAGO_API"
    else:
        aprovado = bool(tem_titular_jonas and tem_sinal_pix and not ja_usado)
        origem_validacao = "OCR_TESSERACT_COMPROVANTE"

    return {
        "aprovado_automatico": aprovado,
        "ja_usado": ja_usado,
        "valor": valor_detectado,
        "chave_unica": chave_unica,
        "validacao_banco": validacao_banco,
        "origem_validacao": origem_validacao
    }


def registrar_comprovante_usado(chave_unica, telefone, valor):
    if not chave_unica or comprovantes_col is None:
        return
    try:
        comprovantes_col.update_one(
            {"chave_unica": chave_unica},
            {"$set": {
                "chave_unica": chave_unica,
                "telefone": str(telefone),
                "valor": float(valor),
                "registrado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
            }},
            upsert=True
        )
    except Exception as e:
        print(f"[ERRO REGISTRAR COMPROVANTE]: {e}")


def montar_bloco_pix(pnome, valor_formatado):
    """Monta 3 balões com a chave PIX separada e blindagem bancária sem termos proibidos."""
    virgula_nome = f", {pnome}" if pnome else ""
    return [
        f"Fechado{virgula_nome}! Fica {valor_formatado}. Vou te mandar a chave PIX separada aqui embaixo pra ficar fácil de você copiar:",
        f"{CHAVE_PIX_OFICIAL}",
        (
            f"Quando você colar a chave no seu banco, vai aparecer exatamente o nome do nosso responsável, {TITULAR_CONTA} ({BANCO_RECEBEDOR}) — é esse nome mesmo que aparece pra você confirmar tranquilo e sem receio, viu? "
            "Só deixa a descrição do PIX em branco por favor, sem escrever nada sobre o serviço. Assim que concluir me manda o comprovante por aqui!"
        )
    ]


def obter_recepcao_natural(pnome):
    saudacao = saudacao_horario()
    virgula_nome = f", {pnome}" if pnome else ""
    abertura = random.choice([
        f"Oi{virgula_nome}! {saudacao}, tudo bem por aí? 😊",
        f"Opa{virgula_nome}! {saudacao}, tudo joia?"
    ])
    corpo = (
        "Aqui é da equipe da *Central CinePro TV & Rádios*! Como posso te ajudar hoje?\n\n"
        "1️⃣ *TV Gratuita (200 canais + 40 rádios)*, *Teste 2h* ou plano mensal (*Camila*)\n"
        "2️⃣ *Suporte Técnico* para colocar na Smart TV, TV Box, Roku ou celular (*Lucas*)\n"
        "3️⃣ *Promoções e Pacotes* de 2 meses, 3 meses ou 1 Ano com desconto (*Gerente Marcos*)\n"
        "4️⃣ *Falar com o Jonas*"
    )
    return [abertura, corpo]


def diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante, resposta_anterior="", ja_atendeu_antes=False, modo_auditoria=False):
    """Retorna (baloes, notificacao_jonas) para o Lucas resolver problemas reais com anti-loop e diagnóstico de rede."""
    virgula_nome = f", {pnome}" if pnome else ""
    texto = (mensagem or "").strip().lower()
    texto_ascii = normalizar_giria_whatsapp(texto)
    notificacao = None
    ja_atendeu_antes = bool(ja_atendeu_antes or ("Lucas" in (resposta_anterior or "")))

    if tipo_midia in ["image", "document"]:
        texto_tela = (texto_comprovante or mensagem or "").strip()
        notificacao = (
            f"📸 *FOTO DE ERRO NO SUPORTE (LUCAS):*\n"
            f"👤 {nome} ({telefone})\n"
            f"🖥️ Texto lido na tela: {texto_tela[:180] or 'sem texto legível'}"
        )
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            f"Foto de erro enviada: {texto_tela[:160] or 'imagem sem texto'}",
            "Leitura da tela realizada pelo Lucas e encaminhada para correção na bancada."
        )
        baloes = [
            f"Boa{virgula_nome}, recebi a foto da sua tela aqui e já li os detalhes do aviso!",
            "Já organizei o diagnóstico aqui na bancada e passei no celular do Jonas pra gente te dar a correção certeira por aqui mesmo em instantes!"
        ]
        return baloes, notificacao

    # 1. Computador / Windows / PDV / Impressora (prioridade sobre sintomas genéricos de TV)
    if any(p in texto_ascii for p in ["pc", "computador", "notebook", "windows", "formatar", "pdv", "caixa", "impressora", "leitor"]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Triagem técnica iniciada para Windows / Sistema PDV Caixa (impressora, leitor ou desempenho)."
        )
        baloes = [
            f"Tranquilo{virgula_nome}, vamos resolver isso no computador/PDV agora!",
            (
                "1️⃣ Se for no *Sistema PDV Caixa*, aperte *F5* para atualizar a tela e confira se o cabo USB da impressora/leitor está firme.\n"
                "2️⃣ Se for *lentidão ou erro no Windows*, me conta o que travou ou manda uma foto da tela aqui que eu te passo a correção certeira!"
            )
        ]
        return baloes, notificacao

    # 2. Marca ou aparelho específico da TV já informado (evita repetir pergunta da marca)
    if "roku" in texto_ascii:
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação específica enviada para Roku TV (espelhamento do celular)."
        )
        baloes = [
            f"Perfeito{virgula_nome}! Na *Roku TV* o sistema não traz navegador aberto para digitar links direto na televisão.",
            (
                f"O jeito mais rápido de assistir na Roku é abrir o link no seu celular ({LINK_PLAYER_IPTV}) "
                "e usar a função *Transmitir / Espelhar Tela* (Smart View, Transmitir ou AirPlay) jogando a imagem para a TV."
            ),
            "Se quiser testar espelhando agora, me avisa aqui se conectou certinho!"
        ]
        return baloes, notificacao

    if any(p in texto_ascii for p in ["samsung", "lg", "tcl", "philco", "aoc", "tv box", "chromecast", "fire", "android tv"]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação específica enviada para Smart TV / TV Box pelo navegador."
        )
        baloes = [
            f"Show{virgula_nome}! Para esse modelo de TV/aparelho é bem direto:",
            (
                "1️⃣ Abra o aplicativo *Internet / Navegador / Browser* na sua TV (ou *Chrome / Downloader* na TV Box).\n"
                f"2️⃣ Digite exatamente esse endereço na barra lá em cima:\n{LINK_PLAYER_IPTV}\n"
                "3️⃣ Depois salve nos *Favoritos* da TV para abrir com 1 clique sempre que quiser."
            ),
            "Se aparecer algum aviso na tela da TV, manda uma foto por aqui que te ajudo na hora!"
        ]
        return baloes, notificacao

    # 3. Como colocar / instalar / abrir na Smart TV ou TV Box (pedido genérico sem marca)
    if any(p in texto_ascii for p in [
        "colocar na tv", "coloca na tv", "botar na tv", "bota na tv", "por na tv",
        "instalar na tv", "instala na tv", "assistir na tv", "ver na tv", "abrir na tv",
        "como coloca", "box", "espelhar", "smart"
    ]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Passo a passo enviado para abrir a Central TV pelo navegador da Smart TV/Box ou espelhamento."
        )
        baloes = [
            f"É bem fácil colocar na TV{virgula_nome}! Você tem 2 jeitos simples de abrir:",
            (
                f"1️⃣ *Pelo navegador da Smart TV ou TV Box:* abra o navegador (Internet/Browser) da TV e entre no link:\n{LINK_PLAYER_IPTV}\n\n"
                "2️⃣ *Espelhando do celular:* abra esse mesmo link no celular e toque em *Transmitir / Smart View / Espelhar Tela* para jogar a imagem direto na televisão."
            ),
            "Qual é a marca ou modelo da sua TV (Samsung, LG, Roku, TCL ou TV Box)? Se aparecer algum aviso na tela, pode me mandar uma foto aqui que te guio passo a passo!"
        ]
        return baloes, notificacao

    # 4. Acompanhamento quando o cliente responde o diagnóstico da TV sem repetir tudo
    if ja_atendeu_antes and any(p in texto_ascii for p in ["todos os canais", "em todos", "um canal", "um so", "so um", "apenas um"]):
        if any(p in texto_ascii for p in ["um canal", "um so", "so um", "apenas um"]):
            baloes = [
                f"Entendi{virgula_nome}! Quando falha em *um canal específico*, geralmente a emissora pública está oscilando a transmissão naquele momento.",
                "Testa outro canal vizinho na lista e me diz *qual canal* parou para eu verificar o sinal dele aqui na central!"
            ]
        else:
            baloes = [
                f"Certo{virgula_nome}! Quando para em *todos os canais* ao mesmo tempo, normalmente é conexão DNS/Wi-Fi ou bloqueio do navegador da TV.",
                "Confere se o site abre normal no navegador do celular no Wi-Fi. Se no celular abrir e na TV não, me manda uma foto da tela da TV aqui que resolvo com você!"
            ]
        return baloes, notificacao

    # 4.5. TV sem internet / sem Wi-Fi / modelo comum antigo
    if any(p in texto_ascii for p in [
        "nao conecta", "sem internet", "sem wifi", "sem wi-fi",
        "tv comum", "sem smart", "nao tem internet", "nao tem wifi", "nao tem wi-fi", "modelo antigo"
    ]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação enviada para TV comum sem internet (HDMI, TV Box ou uso direto no celular)."
        )
        baloes = [
            f"Tranquilo{virgula_nome}! Quando a TV é modelo comum sem internet, você tem 3 saídas fáceis:",
            (
                f"1️⃣ *Direto no celular:* você pode assistir todos os 200 canais grátis no navegador do seu aparelho pelo link:\n{LINK_PLAYER_IPTV}\n"
                "2️⃣ *Cabo HDMI no notebook/PC:* ligue o cabo HDMI na TV e abra esse mesmo link na tela cheia.\n"
                "3️⃣ *TV Box ou Chromecast:* transforma qualquer TV comum com entrada HDMI em Smart TV pelo Wi-Fi."
            ),
            "Se você tiver notebook ou TV Box aí com você, me avisa qual deles pretende usar que te guio!"
        ]
        return baloes, notificacao

    # 4.6. TV não pega IPTV / não instala aplicativo / sem navegador
    if any(p in texto_ascii for p in [
        "nao pega iptv", "nao roda iptv", "nao aceita iptv", "nao pega aplicativo",
        "nao baixa", "nao instala", "nao tem navegador", "sem navegador", "tv antiga", "nao tem aplicativo"
    ]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação para TV que não instala app IPTV (acesso via navegador direto ou espelhamento)."
        )
        baloes = [
            f"Entendi perfeitamente{virgula_nome}! Se a sua TV não instala aplicativo de IPTV, dá para assistir sem baixar app nenhum:",
            (
                f"1️⃣ *Pelo navegador da própria TV (se tiver Wi-Fi):* abra o app *Internet / Browser* da televisão e entre direto nesse link:\n{LINK_PLAYER_IPTV}\n\n"
                "2️⃣ *Se a TV não tiver navegador:* abra o link no celular e toque em *Transmitir / Espelhar Tela* (ou use um *TV Box / cabo HDMI* ligado no computador)."
            ),
            "A sua TV chega a conectar no Wi-Fi ou ela é modelo antigo sem internet?"
        ]
        return baloes, notificacao

    # 5. TV ou canal parou de funcionar / travou / não abre / sem sinal
    if any(p in texto_ascii for p in [
        "parou", "nao funciona", "nao pega",
        "nao entra", "nao carrega", "travou", "travado",
        "congelou", "caiu", "saiu do ar", "deu erro", "canal", "canais", "fora do ar",
        "sem som", "mudo", "tela preta", "nao abre", "0:00", "sumiu", "sinal"
    ]):
        diag = obter_diagnostico_conexao_rapido()
        aviso_central = (
            f"📡 *Status da nossa Central ao vivo:* nossos servidores estão *100% online* agora "
            f"(banco `{diag.get('mongo_ms', 0)} ms` | streams `{diag.get('stream_ms', 0)} ms`) — ou seja, nossa ponta está estável.\n"
            f"Você também pode conferir nossa latência em tempo real em: https://agente-whatsapp-jonas.onrender.com/auditor"
            if diag.get("status_geral") == "ONLINE"
            else f"⚠️ *Status do Auditor ao vivo:* detectamos uma oscilação momentânea na nossa rota (`{diag.get('resumo', 'verificando')}`). Já acionei nossa auditoria técnica pra estabilizar!"
        )
        notificacao = f"🛠️ *CHAMADO DE TV / SINAL (LUCAS):*\n👤 {nome} ({telefone})\n💬 Relato: {(mensagem or '')[:160]}\n🌐 Central: {diag.get('status_geral')} ({diag.get('mongo_ms')}ms)"
        if not modo_auditoria:
            registrar_evento_email(
                "SUPORTE_TECNICO", nome, telefone, 0.0,
                mensagem[:180],
                f"Orientação de reinício 30s, play 0:00 + telemetria Central ({diag.get('status_geral')})."
            )
        baloes = [
            f"Vamos resolver isso agora{virgula_nome}! Já conferi nosso painel ao vivo antes de te responder:",
            aviso_central,
            (
                "Para ajustar aí no seu aparelho e destravar na hora, faça esses 3 passos:\n"
                "1️⃣ *Reinicie a rede e a TV:* tire a TV (ou TV Box) e o roteador da tomada por *30 segundos* e ligue de novo.\n"
                "2️⃣ *Destrave o player:* se abrir parado em 0:00 ou sem som, toque no botão de *Áudio/Play* na tela ou troque pro canal vizinho e volte.\n"
                f"3️⃣ *Recarregue o endereço:* feche e abra de novo o link {LINK_PLAYER_IPTV} no navegador.\n\n"
                "Se continuar, me responde: parou em *todos os canais* ou em *um só*? E está assistindo no *celular*, *Smart TV* ou *TV Box*?"
            )
        ]
        return baloes, notificacao

    # 6. Oscilação de Wi-Fi / internet lenta / buffering
    if any(p in texto_ascii for p in ["travando", "engasgando", "oscilando", "carregando", "bolinha", "internet", "rede", "wifi", "wi-fi", "lenta", "rota", "dns"]):
        diag = obter_diagnostico_conexao_rapido()
        if not modo_auditoria:
            registrar_evento_email(
                "SUPORTE_TECNICO", nome, telefone, 0.0,
                mensagem[:180],
                f"Orientação Wi-Fi 5G/cabo + diagnóstico Central ({diag.get('status_geral')})."
            )
        if diag.get("status_geral") == "ONLINE":
            cabecalho = (
                f"Acabei de checar nossa Central no Quadro de Conexão{virgula_nome}: nossos servidores estão *100% online e rápidos* "
                f"(banco `{diag.get('mongo_ms', 0)} ms` | streams `{diag.get('stream_ms', 0)} ms`)!"
            )
            passo = (
                "Como a nossa parte já está online liso, o engasgo aí costuma ser oscilação do Wi-Fi 2.4G ou rota da operadora. "
                "Tenta mudar para a rede *5G* (ou cabo de rede), tirar o roteador da tomada por *30 segundos* e acompanhar o medidor da sua internet no nosso quadro:\n"
                "https://agente-whatsapp-jonas.onrender.com/auditor"
            )
        else:
            cabecalho = f"Valeu por avisar{virgula_nome}! Nosso Auditor técnico já marcou oscilação aqui na nossa ponta (`{diag.get('resumo', 'rota')}`)."
            passo = "Já disparamos o alerta automático para o Jonas estabilizar a rota. Enquanto isso, tente alternar para outro canal vizinho."
        baloes = [
            cabecalho,
            passo,
            "Me fala também: tá travando em todos os canais ou em um específico? E em qual aparelho você está usando?"
        ]
        return baloes, notificacao

    registrar_evento_email(
        "SUPORTE_TECNICO", nome, telefone, 0.0,
        mensagem[:180],
        "Atendimento técnico do Lucas aguardando especificação do aparelho e sintoma."
    )
    if ja_atendeu_antes:
        baloes = [
            f"Entendi{virgula_nome}! Pra eu conseguir te passar o passo a passo exato sem te fazer perder tempo, me diz só esses 2 detalhes:",
            "1️⃣ Qual aparelho você está usando agora (*celular, computador, Smart TV ou TV Box*)?\n2️⃣ O que aparece na tela (se preferir, manda uma foto por aqui)?"
        ]
    else:
        baloes = [
            f"Fala{virgula_nome}! Tudo tranquilo? Aqui é o Lucas, cuido da parte técnica.",
            "Me conta o que tá acontecendo aí: é alguma configuração pra colocar na TV, canal que parou de funcionar ou algo no computador? Pode explicar do seu jeito ou mandar foto da tela!"
        ]
    return baloes, notificacao


def gerar_resposta_fallback_inteligente(setor, pnome, mensagem_usuario):
    """
    Gera resposta humana e contextual quando o cliente envia mensagens
    que fogem do padrão das palavras-chave exatas, mantendo a persona de cada setor (100% TV & Rádios).
    """
    virgula_nome = f", {pnome}" if pnome else ""
    texto_limpo = normalizar_giria_whatsapp(mensagem_usuario)

    # Dúvidas de Aparelhos / Compatibilidade
    if any(k in texto_limpo for k in ["roku", "fire stick", "firestick", "smart", "samsung", "lg", "tcl", "celular", "iphone", "computador", "notebook", "tv box", "box", "aparelho"]):
        if setor == "SETOR_3_COMERCIAL":
            return [
                f"Roda sim{virgula_nome}! Funciona direto pelo navegador no celular, computador, TV Box ou Smart TV (e na Roku espelhando pelo celular).",
                "Quer aproveitar qual pacote promocional do gerente hoje: *2 meses (R$ 50)*, *3 meses (R$ 70)* ou *1 Ano (R$ 240)*?"
            ]
        return [
            f"Funciona direto pelo navegador{virgula_nome}! 📺",
            "Você abre nossos *200 canais abertos e 40 rádios gratuitos* no celular, computador ou Smart TV — e também pode fazer o *Teste grátis de 2 horas* do pacote completo com 800 canais!",
            f"Link direto: {LINK_PLAYER_IPTV}"
        ]

    # Dúvidas sobre Internet / Modo Offline
    if any(k in texto_limpo for k in ["sem internet", "caiu a net", "offline", "precisa de net"]):
        return [
            f"Precisa de internet normal (Wi-Fi ou 4G/5G){virgula_nome}!",
            "Nossos canais e rádios são super leves para rodar mesmo em conexões simples sem travar. Se quiser testar agora, é só pedir o *teste de 2 horas*!"
        ]

    # Cumprimentos e confirmações informais mantêm o foco do atendente atual
    if any(k in texto_limpo for k in ["salve", "tranquilo", "beleza", "e ai", "fala ai", "opa tudo bem", "opa", "blz", "ok", "certo", "entendi"]):
        if setor == "SETOR_1_CINEPRO":
            return [
                f"Show{virgula_nome}! 😊 Aqui é a Camila. O link gratuito com os 200 canais abertos + 40 rádios já está liberado aqui:",
                f"{LINK_PLAYER_IPTV}\n\nSe quiser liberar um *Teste grátis de 2 horas* do pacote VIP completo (+1.402 canais extras — 1.602 ao todo) ou saber dos planos, é só pedir!"
            ]
        elif setor == "SETOR_3_COMERCIAL":
            return [
                f"Show{virgula_nome}! Aqui é o Marcos, gerente comercial. Tô por aqui pra fechar a melhor condição pra você:",
                "Temos *2 meses por R$ 50*, *3 meses por R$ 70*, *4 meses por R$ 90* ou *1 Ano por R$ 220* (ou *R$ 200 no PIX à vista*). Qual desses você quer garantir hoje?"
            ]
        return [
            f"Opa{virgula_nome}, tudo tranquilo por aqui e com você? 😊",
            "Posso abrir nossos *200 canais e 40 rádios gratuitos*, liberar um *Teste 2h do pacote VIP (1.602 canais)* ou te passar para o *Gerente Marcos* negociar um pacote de 2 meses, 3 meses ou 1 Ano!"
        ]

    # Fallback contextual por setor
    if setor == "SETOR_1_CINEPRO":
        return [
            f"Entendi perfeitamente{virgula_nome}! 😊 Aqui é a Camila.",
            "Temos *200 canais gratuitos + 40 rádios ao vivo* direto no link, *Teste grátis de 2 horas* e o pacote VIP completo com *1.602 canais auditados* (R$ 30/mês).",
            f"Acesse grátis por aqui: {LINK_PLAYER_IPTV}\nSe quiser desconto em pacotes de 2 meses, 3 meses ou 1 Ano, eu chamo meu gerente Marcos na hora!"
        ]
    elif setor == "SETOR_2_SUPORTE":
        return [
            f"Compreendi o seu relato{virgula_nome}. Sou o Lucas do suporte técnico especializado.",
            "Para eu te orientar com precisão: o problema está acontecendo na conexão de rede (Wi-Fi), em algum canal aberto ou no navegador da sua Smart TV / TV Box / celular?"
        ]
    elif setor == "SETOR_3_COMERCIAL":
        return [
            f"Perfeito{virgula_nome}! Sou o Marcos, gerente comercial da Central CinePro TV & Rádios.",
            "Consigo liberar pra você promoções reais nos pacotes de *2 meses (R$ 50)*, *3 meses (R$ 70)*, *4 meses (R$ 90)*, *6 meses (R$ 130)*, *8 meses (R$ 160)* e *1 Ano (R$ 220 — sai a R$ 18,33/mês)*, todos com os *1.602 canais + 40 rádios*.",
            "Qual desses planos você quer fechar ou negociar agora?"
        ]

    return obter_recepcao_natural(pnome)


# ==============================================================================
# AUDITOR DOS 3 AGENTES & TELEMETRIA DE LATÊNCIA / CONEXÃO AO VIVO
# ==============================================================================

_CACHE_REDE_AUDITOR = {
    "ts": 0.0,
    "atualizando": False,
    "dados": {
        "status_geral": "ONLINE",
        "mongo_ok": True,
        "mongo_ms": 0.0,
        "catalogo_ok": True,
        "qtd_abertos": 200,
        "qtd_vip": 0,
        "streams_testados": 0,
        "streams_online": 0,
        "stream_ms": 0.0,
        "amostras": [],
        "resumo": "Aguardando primeira medição ao vivo",
        "medido_em": ""
    }
}

_ESTADO_AUDITOR = {
    "agentes": {
        "Camila": {"atendimentos": 0, "erros": 0, "ultimo_uso": "-", "ultima_msg": "-", "papel": "Validadora PIX, Ativadora Lista VIP, 200 Grátis, Rádios & Teste 2h"},
        "Lucas": {"atendimentos": 0, "erros": 0, "ultimo_uso": "-", "ultima_msg": "-", "papel": "Suporte Técnico Autônomo (Aparelhos, Gírias, Rede & Diagnóstico)"},
        "Marcos": {"atendimentos": 0, "erros": 0, "ultimo_uso": "-", "ultima_msg": "-", "papel": "Gerente Comercial & Negociação (2, 3, 4, 6, 8 e 12 Meses — TV e Rádio)"},
    },
    "ultima_auditoria": None,
    "ultimos_eventos": []
}


def _testar_url_stream_rapido(url, timeout=2.5):
    """Testa conectividade HTTP real de uma stream de amostra medindo latência em ms."""
    t0 = time.perf_counter()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for metodo in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Auditor-Conexao-JonasTech/1.0", "Range": "bytes=0-1024"},
                method=metodo,
            )
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                ms = round((time.perf_counter() - t0) * 1000, 1)
                return True, resp.status, ms
        except urllib.error.HTTPError as he:
            if he.code in (200, 206, 301, 302, 403) and metodo == "HEAD":
                continue
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return False, he.code, ms
        except Exception:
            if metodo == "HEAD":
                continue
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return False, 0, ms
    return False, 0, round((time.perf_counter() - t0) * 1000, 1)


def medir_conexao_servidor(forcar=False):
    """Mede latência real do MongoDB Atlas, catálogos JSON/VIP e amostra de streams de TV/Rádio."""
    agora_mono = time.monotonic()
    if not forcar and (agora_mono - _CACHE_REDE_AUDITOR["ts"]) < 45.0 and _CACHE_REDE_AUDITOR["dados"].get("medido_em"):
        return _CACHE_REDE_AUDITOR["dados"]

    t0_mongo = time.perf_counter()
    mongo_ok = False
    mongo_ms = 0.0
    if client is not None:
        try:
            client.admin.command("ping")
            mongo_ok = True
        except Exception:
            mongo_ok = False
    mongo_ms = round((time.perf_counter() - t0_mongo) * 1000, 1)

    pasta = os.path.dirname(os.path.abspath(__file__))
    canais_abertos = []
    catalogo_ok = False
    arq_canais = os.path.join(pasta, "canais.json")
    if os.path.exists(arq_canais):
        try:
            with open(arq_canais, "r", encoding="utf-8") as f:
                dados_c = json.load(f)
                if isinstance(dados_c, list):
                    canais_abertos = dados_c
                    catalogo_ok = len(dados_c) > 0
        except Exception:
            catalogo_ok = False

    canais_vip = _carregar_canais_vip_nuvem()
    amostras_candidatas = []
    vistas_cat = set()
    for c in canais_abertos:
        cat = str(c.get("cat") or "TV")
        url_c = str(c.get("url") or "").strip()
        if url_c.startswith("http") and cat not in vistas_cat:
            vistas_cat.add(cat)
            amostras_candidatas.append({"nome": c.get("nome", "Canal"), "categoria": cat, "url": url_c})
        if len(amostras_candidatas) >= 3:
            break

    amostras_res = []
    streams_online = 0
    latencias_ok = []
    for item in amostras_candidatas:
        ok, codigo, ms = _testar_url_stream_rapido(item["url"], timeout=2.5)
        if ok:
            streams_online += 1
            latencias_ok.append(ms)
        amostras_res.append({
            "nome": item["nome"],
            "categoria": item["categoria"],
            "online": ok,
            "http": codigo,
            "latencia_ms": ms
        })

    stream_ms = round(sum(latencias_ok) / len(latencias_ok), 1) if latencias_ok else 0.0
    if mongo_ok and catalogo_ok and (streams_online >= 1 or not amostras_candidatas):
        status_geral = "ONLINE" if mongo_ms < 900 else "LENTO"
    else:
        status_geral = "INSTAVEL"

    resumo = f"Mongo {mongo_ms}ms • {streams_online}/{len(amostras_res)} streams ao vivo ({stream_ms}ms)"
    resultado = {
        "status_geral": status_geral,
        "mongo_ok": mongo_ok,
        "mongo_ms": mongo_ms,
        "catalogo_ok": catalogo_ok,
        "qtd_abertos": len(canais_abertos),
        "qtd_vip": len(canais_vip),
        "streams_testados": len(amostras_res),
        "streams_online": streams_online,
        "stream_ms": stream_ms,
        "amostras": amostras_res,
        "resumo": resumo,
        "medido_em": agora_brasilia().strftime("%H:%M:%S")
    }
    _CACHE_REDE_AUDITOR["dados"] = resultado
    _CACHE_REDE_AUDITOR["ts"] = time.monotonic()
    return resultado


def obter_diagnostico_conexao_rapido():
    """Retorna telemetria em cache sem bloquear atendimento e atualiza em segundo plano se expirou."""
    agora_mono = time.monotonic()
    precisa_atualizar = (agora_mono - _CACHE_REDE_AUDITOR["ts"]) >= 45.0 or not _CACHE_REDE_AUDITOR["dados"].get("medido_em")
    if precisa_atualizar and not _CACHE_REDE_AUDITOR["atualizando"]:
        def _tarefa_bg():
            _CACHE_REDE_AUDITOR["atualizando"] = True
            try:
                medir_conexao_servidor(forcar=True)
            finally:
                _CACHE_REDE_AUDITOR["atualizando"] = False
        threading.Thread(target=_tarefa_bg, daemon=True).start()
    return _CACHE_REDE_AUDITOR["dados"]


def registrar_auditoria_agente(atendente, setor, mensagem, tempo_ms, sucesso=True, observacao=""):
    """Registra execução de cada agente para o Auditor monitorar falhas e lentidão."""
    hora_str = agora_brasilia().strftime("%H:%M:%S")
    chave_ag = "Marcos" if "Marcos" in str(atendente) else ("Lucas" if "Lucas" in str(atendente) else ("Camila" if "Camila" in str(atendente) else ""))
    if chave_ag in _ESTADO_AUDITOR["agentes"]:
        st = _ESTADO_AUDITOR["agentes"][chave_ag]
        st["atendimentos"] += 1
        if not sucesso:
            st["erros"] += 1
        st["ultimo_uso"] = hora_str
        st["ultima_msg"] = (mensagem or "")[:80]

    evento = {
        "horario": hora_str,
        "atendente": atendente,
        "setor": setor,
        "tempo_ms": round(float(tempo_ms or 0.0), 1),
        "sucesso": bool(sucesso),
        "observacao": (observacao or "")[:120],
    }
    _ESTADO_AUDITOR["ultimos_eventos"].insert(0, evento)
    _ESTADO_AUDITOR["ultimos_eventos"] = _ESTADO_AUDITOR["ultimos_eventos"][:20]

    if auditoria_col is not None and (not sucesso or tempo_ms > 2000 or observacao):
        try:
            auditoria_col.insert_one({
                **evento,
                "data_dia": agora_brasilia().strftime("%Y-%m-%d")
            })
        except Exception:
            pass


def executar_auditoria_3_agentes(forcar_rede=True):
    """Audita em tempo real a saúde dos 3 agentes (Camila, Lucas, Marcos) e aponta qualquer falha."""
    rede = medir_conexao_servidor(forcar=forcar_rede)
    alertas = []
    pendencias_conferencia = 0
    if leads_col is not None:
        try:
            pendencias_conferencia = leads_col.count_documents({"setor_atual": "PAGAMENTO_EM_ANALISE"})
        except Exception:
            pendencias_conferencia = 0

    # 1. Auditoria Camila (Validadora + Catálogo + Teste 2h + Lista VIP)
    camila_checks = []
    dias_ok = (
        calcular_dias_por_valor_iptv(50) == 60
        and calcular_dias_por_valor_iptv(90) == 120
        and calcular_dias_por_valor_iptv(160) == 240
        and calcular_dias_por_valor_iptv(220) == 365
    )
    camila_checks.append(("Tabela de validação (30d a 365d)", dias_ok))
    camila_checks.append(("200 canais livres + rádios carregados", rede.get("catalogo_ok", False)))
    vip_carregado = rede.get("qtd_vip", 0) > 0
    camila_checks.append(("Lista VIP total carregada (canais_vip.json)", vip_carregado))
    if not rede.get("catalogo_ok"):
        alertas.append("CRITICO: Precisa auditar a Camila — catálogo canais.json não carregou.")
    if not vip_carregado:
        alertas.append("ATENCAO: Precisa auditar a Lista VIP Total da Camila — canais_vip.json ainda tem 0 canais VIP extras no Render (200 abertos/rádios estão ativos).")
    if pendencias_conferencia > 0:
        alertas.append(f"FINANCEIRO: Há {pendencias_conferencia} comprovante(s) aguardando conferência manual (#liberar).")

    # 2. Auditoria Lucas (Suporte + Gírias + Telemetria)
    t_lucas, _ = diagnosticar_suporte_lucas("Teste", "Auditoria", "000", "a minha tv no pega iptv", "text", "", modo_auditoria=True)
    lucas_ok = "sem baixar app nenhum" in " ".join(t_lucas).lower()
    if not lucas_ok:
        alertas.append("CRITICO: Precisa auditar o Lucas — falhou na regra de TV que não instala aplicativo IPTV.")

    # 3. Auditoria Marcos (Gerente Negociador 2, 3, 4, 6, 8 e 12 meses)
    t_marcos, extras_m = negociar_gerente_marcos("Teste", "Auditoria", "000", "quero ver planos de 4 meses e 8 meses", "quero ver planos de 4 meses e 8 meses", {}, modo_auditoria=True)
    txt_m = " ".join(t_marcos).lower()
    marcos_ok = ("90" in txt_m or "160" in txt_m) and all(k in PLANOS_IPTV for k in ["50", "70", "90", "130", "160", "220"])
    if not marcos_ok:
        alertas.append("CRITICO: Precisa auditar o Gerente Marcos — falha na tabela de 2, 3, 4, 6, 8 e 12 meses.")

    if not rede.get("mongo_ok"):
        alertas.append("CRITICO: Precisa auditar o banco MongoDB Atlas — ping falhou!")
    elif rede.get("mongo_ms", 0) > 800:
        alertas.append(f"LENTIDAO: MongoDB com latência alta ({rede.get('mongo_ms')} ms).")
    if rede.get("streams_testados", 0) > 0 and rede.get("streams_online", 0) == 0:
        alertas.append("CONEXAO: Precisa auditar as streams — nenhuma amostra respondeu ao vivo agora.")

    relatorio = {
        "executado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
        "status_processo": "REQUER_AUDITORIA" if any(a.startswith("CRITICO") or a.startswith("CONEXAO") for a in alertas) else ("COM_AVISOS" if alertas else "SAUDAVEL"),
        "rede": rede,
        "agentes": {
            "Camila": {
                **_ESTADO_AUDITOR["agentes"]["Camila"],
                "aprovada": dias_ok and rede.get("catalogo_ok", False),
                "vip_pronto": vip_carregado,
                "pendencias_conferencia": pendencias_conferencia,
                "checks": [{"nome": n, "ok": ok} for n, ok in camila_checks]
            },
            "Lucas": {
                **_ESTADO_AUDITOR["agentes"]["Lucas"],
                "aprovada": lucas_ok,
                "checks": [
                    {"nome": "Gírias WhatsApp ('no pega iptv')", "ok": lucas_ok},
                    {"nome": "Consulta latência ao vivo antes de culpar rede", "ok": rede.get("status_geral") != "INSTAVEL"}
                ]
            },
            "Marcos": {
                **_ESTADO_AUDITOR["agentes"]["Marcos"],
                "aprovada": marcos_ok,
                "checks": [
                    {"nome": "Tabela 2, 3, 4, 6, 8 e 12 meses ativa", "ok": marcos_ok},
                    {"nome": "Negociação TV + App de Rádio integrada", "ok": True}
                ]
            }
        },
        "alertas": alertas,
        "ultimos_eventos": _ESTADO_AUDITOR["ultimos_eventos"]
    }
    _ESTADO_AUDITOR["ultima_auditoria"] = relatorio
    return relatorio


PLANOS_IPTV = {
    "25": (25.0, "R$ 25,00 (1 Mês Promocional • TV ou App Rádio PRO)"),
    "30": (30.0, "R$ 30,00 (1 Mês Completo • Lista VIP TV + App Rádio PRO)"),
    "45": (45.0, "R$ 45,00 (Pacote 2 Meses Desconto Gerente ou 2 Telas no Mês)"),
    "50": (50.0, "R$ 50,00 (Pacote 2 Meses • Economia R$ 10,00 • R$ 25,00/mês)"),
    "65": (65.0, "R$ 65,00 (Pacote 3 Meses Desconto Gerente • Economia R$ 25,00)"),
    "70": (70.0, "R$ 70,00 (Pacote 3 Meses • Economia R$ 20,00 • R$ 23,33/mês)"),
    "85": (85.0, "R$ 85,00 (Pacote 4 Meses Desconto Gerente • Economia R$ 35,00)"),
    "90": (90.0, "R$ 90,00 (Pacote 4 Meses • 1 Mês Grátis • R$ 22,50/mês)"),
    "120": (120.0, "R$ 120,00 (Pacote 6 Meses Desconto Gerente • Economia R$ 60,00)"),
    "130": (130.0, "R$ 130,00 (Pacote 6 Meses • Economia R$ 50,00 • R$ 21,67/mês)"),
    "150": (150.0, "R$ 150,00 (Pacote 8 Meses Desconto Gerente • Economia R$ 90,00)"),
    "160": (160.0, "R$ 160,00 (Pacote 8 Meses • R$ 20,00/mês • Economia R$ 80,00)"),
    "200": (200.0, "R$ 200,00 (Pacote 12 Meses Piso Gerente à Vista • Economia R$ 160,00)"),
    "220": (220.0, "R$ 220,00 (Pacote 12 Meses / 1 Ano • R$ 18,33/mês • Economia R$ 140,00)"),
    "240": (240.0, "R$ 240,00 (Pacote Anual Tabela Antiga — atualizado para R$ 220,00)"),
}


def negociar_gerente_marcos(pnome, nome, telefone, mensagem, texto_sem_acento, lead, apresentou_como_escalacao=False, modo_auditoria=False):
    """Conduz negociações e descontos de 2, 3, 4, 6, 8 e 12 meses (TV e App Rádio) como Gerente Marcos."""
    virgula_nome = f", {pnome}" if pnome else ""
    dados_extras = {}
    plano_salvo = str((lead or {}).get("plano_comercial") or "30")
    if plano_salvo not in PLANOS_IPTV:
        plano_salvo = "30"

    if any(p in texto_sem_acento for p in ["cartao", "credito", "debito", "parcel", "vezes", "boleto"]):
        if not modo_auditoria:
            disparar_alerta_cliente_quente(telefone, nome, f"GERENTE MARCOS: CLIENTE PEDIU CARTAO/PARCELAMENTO ({texto_sem_acento[:80]})")
            dados_extras["notificacao_jonas"] = (
                f"💳 *PEDIDO DE LINK CARTÃO/PARCELADO (GERENTE MARCOS):*\n"
                f"👤 Cliente: {nome} ({telefone})\n"
                f"💬 Mensagem: {(mensagem or '')[:140]}"
            )
        baloes = [
            f"Com certeza{virgula_nome}! Além do PIX com ativação na hora pela Camila, também liberamos link de cartão pelo Mercado Pago (ideal pro de 4, 6, 8 ou 12 meses).",
            "Já avisei o Jonas aqui agora mesmo pra te enviar o link certinho!"
        ]
        return baloes, dados_extras

    eh_pedido_pix = any(p in texto_sem_acento for p in [
        "pix", "chave", "pagar", "quero fechar", "vou querer", "manda a chave", "pode gerar", "fechado"
    ])
    eh_choro_desconto = any(p in texto_sem_acento for p in [
        "desconto", "promocao", "mais barato", "barato", "caro", "faz por", "abaixa",
        "melhora", "so tenho", "condicao", "negocia", "menos", "ta puxado"
    ])

    if eh_pedido_pix:
        if "200" in texto_sem_acento:
            chave_plano = "200"
        elif any(k in texto_sem_acento for k in ["1 ano", "anual", "12 meses", "um ano", "220"]):
            chave_plano = "200" if plano_salvo == "200" and "220" not in texto_sem_acento else "220"
        elif any(k in texto_sem_acento for k in ["8 meses", "oito meses", "160", "150"]):
            chave_plano = "150" if ("150" in texto_sem_acento or plano_salvo == "150") and "160" not in texto_sem_acento else "160"
        elif any(k in texto_sem_acento for k in ["6 meses", "semestral", "130", "120"]):
            chave_plano = "120" if ("120" in texto_sem_acento or plano_salvo == "120") and "130" not in texto_sem_acento else "130"
        elif any(k in texto_sem_acento for k in ["4 meses", "quatro meses", "quadrimestral", "90", "85"]):
            chave_plano = "85" if ("85" in texto_sem_acento or plano_salvo == "85") and "90" not in texto_sem_acento else "90"
        elif "65" in texto_sem_acento:
            chave_plano = "65"
        elif any(k in texto_sem_acento for k in ["3 meses", "trimestral", "70"]):
            chave_plano = "65" if plano_salvo == "65" and "70" not in texto_sem_acento else "70"
        elif any(k in texto_sem_acento for k in ["2 telas", "duas telas", "45"]):
            chave_plano = "45"
        elif any(k in texto_sem_acento for k in ["2 meses", "bimestral", "50"]):
            chave_plano = "45" if plano_salvo == "45" and "50" not in texto_sem_acento else "50"
        elif "25" in texto_sem_acento:
            chave_plano = "25"
        elif any(k in texto_sem_acento for k in ["1 mes", "mensal", "30"]):
            chave_plano = "30"
        else:
            chave_plano = plano_salvo

        valor_num, valor_str = PLANOS_IPTV[chave_plano]
        dias_neg = calcular_dias_por_valor_iptv(valor_num)
        dados_extras["plano_comercial"] = chave_plano
        dados_extras["valor_negociado"] = valor_num
        dados_extras["dias_negociados"] = dias_neg
        dados_extras["negociado_por"] = "Marcos"
        if not modo_auditoria:
            disparar_alerta_cliente_quente(telefone, nome, f"GERENTE MARCOS GEROU PIX {valor_str}", valor_num)
        baloes_pix = montar_bloco_pix(pnome, valor_str)
        baloes_pix.append(f"Assim que pagar, manda o print/comprovante aqui mesmo que a *Camila* já confere os *R$ {valor_num:.2f}* combinados e valida a ativação da sua lista VIP ({dias_neg} dias)!")
        return baloes_pix, dados_extras

    if eh_choro_desconto:
        if any(k in texto_sem_acento for k in ["1 ano", "anual", "12 meses", "um ano", "220"]) or plano_salvo == "220":
            dados_extras.update({"plano_comercial": "200", "valor_negociado": 200.0, "dias_negociados": 365, "negociado_por": "Marcos"})
            baloes = [
                f"Aqui é o *Marcos, gerente comercial*! No pacote de *12 Meses (1 Ano)* — que vale tanto pra TV quanto pro Aplicativo de Rádios PRO — vou liberar minha condição final pra você{virgula_nome}:",
                "No avulso (`12 x R$ 30`) daria *R$ 360,00*. De *R$ 220,00*, fecho com você no PIX à vista por *R$ 200,00 o ano inteiro* — são *R$ 160,00 de desconto* (*R$ 16,67 por mês*!).",
                "Posso gerar a chave PIX de *R$ 200,00* pra Camila conferir seu comprovante e ativar a lista VIP completa?"
            ]
        elif any(k in texto_sem_acento for k in ["8 meses", "oito meses", "160"]) or plano_salvo == "160":
            dados_extras.update({"plano_comercial": "150", "valor_negociado": 150.0, "dias_negociados": 240, "negociado_por": "Marcos"})
            baloes = [
                f"Fecho com você{virgula_nome}! No pacote de *8 Meses* (que no mensal daria R$ 240 e já está R$ 160), consigo baixar na alçada de gerente para *R$ 150,00* — são *R$ 90,00 de economia*!",
                "Quer a chave PIX de *R$ 150,00* agora pra Camila validar e liberar os 8 meses?"
            ]
        elif any(k in texto_sem_acento for k in ["6 meses", "semestral", "130"]) or plano_salvo == "130":
            dados_extras.update({"plano_comercial": "120", "valor_negociado": 120.0, "dias_negociados": 180, "negociado_por": "Marcos"})
            baloes = [
                f"Combinado{virgula_nome}! Nos *6 Meses* (que daria R$ 180 no avulso e está R$ 130), libero desconto de gerente para *R$ 120,00* (apenas *R$ 20,00/mês*, *2 meses grátis*)!",
                "Mando a chave PIX de *R$ 120,00* agora?"
            ]
        elif any(k in texto_sem_acento for k in ["4 meses", "quatro meses", "quadrimestral", "90"]) or plano_salvo == "90":
            dados_extras.update({"plano_comercial": "85", "valor_negociado": 85.0, "dias_negociados": 120, "negociado_por": "Marcos"})
            baloes = [
                f"Bora fechar{virgula_nome}! Nos *4 Meses* (que já tem 1 mês grátis por R$ 90), arredondo no desconto de gerente para *R$ 85,00* (economia de R$ 35,00)!",
                "Mando o PIX de *R$ 85,00* agora pra Camila conferir e liberar?"
            ]
        elif any(k in texto_sem_acento for k in ["3 meses", "trimestral", "70"]) or plano_salvo == "70":
            dados_extras.update({"plano_comercial": "65", "valor_negociado": 65.0, "dias_negociados": 90, "negociado_por": "Marcos"})
            baloes = [
                f"Tranquilo{virgula_nome}, aqui é o *gerente Marcos*! No pacote de *3 Meses* que daria R$ 90 e já está R$ 70, consigo fechar por *R$ 65,00* (economia de R$ 25,00)!",
                "Mando a chave PIX de *R$ 65,00* agora?"
            ]
        elif any(k in texto_sem_acento for k in ["2 meses", "bimestral", "50"]) or plano_salvo == "50":
            dados_extras.update({"plano_comercial": "45", "valor_negociado": 45.0, "dias_negociados": 60, "negociado_por": "Marcos"})
            baloes = [
                f"Aqui é o *Marcos, gerente*! Nos *2 Meses*, além dos R$ 50, consigo fechar com você hoje por *R$ 45,00* (ou pular direto pros *3 meses por R$ 65,00*!).",
                "Qual você prefere fechar no PIX agora: *2 meses por R$ 45* ou *3 meses por R$ 65*?"
            ]
        else:
            dados_extras.update({"plano_comercial": "25", "valor_negociado": 25.0, "dias_negociados": 30, "negociado_por": "Marcos"})
            baloes = [
                f"Pode deixar comigo{virgula_nome}! Aqui é o *Marcos, gerente comercial*. Para você entrar hoje na TV ou no App de Rádio PRO, consigo liberar o *1º mês promocional por R$ 25,00*!",
                "E nos pacotes maiores a economia cresce muito mais: *2m = R$ 50* | *3m = R$ 70* | *4m = R$ 90* | *6m = R$ 130* | *8m = R$ 160* | *12m = R$ 220*. Qual você quer garantir?"
            ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["1 ano", "anual", "12 meses", "um ano", "220"]):
        dados_extras.update({"plano_comercial": "220", "valor_negociado": 220.0, "dias_negociados": 365, "negociado_por": "Marcos"})
        baloes = [
            f"Excelente visão{virgula_nome}! No pacote de *12 Meses (1 Ano)* — válido para *TV Completa ou App Rádio PRO* — a vantagem é máxima:",
            "Pagando mês a mês (`12 x R$ 30`) daria *R$ 360,00*. No plano *Anual Completo* eu libero os 12 meses por *R$ 220,00* — sai a apenas *R$ 18,33/mês* (*R$ 140,00 de economia*!).",
            "Quer que eu gere a chave PIX oficial de *R$ 220,00* pra Camila conferir seu comprovante e ativar na hora?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["8 meses", "oito meses", "160"]):
        dados_extras.update({"plano_comercial": "160", "valor_negociado": 160.0, "dias_negociados": 240, "negociado_por": "Marcos"})
        baloes = [
            f"Ótima pedida{virgula_nome}! No pacote de *8 Meses* (TV ou App de Rádio PRO), no avulso daria R$ 240,00, mas na tabela promocional sai por *R$ 160,00* — fica apenas *R$ 20,00/mês* com *R$ 80,00 de economia*!",
            "Quer a chave PIX de *R$ 160,00* agora pra fechar os 8 meses?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["6 meses", "semestral", "130"]):
        dados_extras.update({"plano_comercial": "130", "valor_negociado": 130.0, "dias_negociados": 180, "negociado_por": "Marcos"})
        baloes = [
            f"Boa escolha{virgula_nome}! Nos *6 Meses (Semestral)* você paga *R$ 130,00* em vez de R$ 180,00 — são *R$ 50,00 de desconto* (*R$ 21,67/mês*)!",
            "Quer o PIX de *R$ 130,00* ou comparar com o de *8 meses (R$ 160)*?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["4 meses", "quatro meses", "quadrimestral", "90"]):
        dados_extras.update({"plano_comercial": "90", "valor_negociado": 90.0, "dias_negociados": 120, "negociado_por": "Marcos"})
        baloes = [
            f"O pacote de *4 Meses* vale muito a pena{virgula_nome}: você paga valor de 3 (`R$ 90,00`) e leva *4 meses completos* — sai *R$ 22,50/mês* (*1 mês inteiro grátis*, economia de R$ 30,00)!",
            "Posso mandar a chave PIX de *R$ 90,00* agora?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["3 meses", "trimestral", "70"]):
        dados_extras.update({"plano_comercial": "70", "valor_negociado": 70.0, "dias_negociados": 90, "negociado_por": "Marcos"})
        baloes = [
            f"Nos *3 Meses (Trimestral)*{virgula_nome}, em vez de R$ 90,00 você garante por *R$ 70,00* (*R$ 23,33/mês*, economia de R$ 20,00)! (E olha: por mais R$ 20 você já pega *4 meses a R$ 90*!).",
            "Quer o PIX de *R$ 70,00* ou prefere o de 4 meses?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["2 meses", "bimestral", "50"]):
        dados_extras.update({"plano_comercial": "50", "valor_negociado": 50.0, "dias_negociados": 60, "negociado_por": "Marcos"})
        baloes = [
            f"Nos *2 Meses* você já economiza R$ 10,00 logo de entrada{virgula_nome}: em vez de R$ 60,00, fecho por *R$ 50,00* (*R$ 25,00/mês*) — válido para TV ou Aplicativo de Rádio PRO!",
            "Quer a chave PIX de *R$ 50,00* agora?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["2 telas", "duas telas", "familia", "mais de uma tv", "45"]):
        dados_extras.update({"plano_comercial": "45", "valor_negociado": 45.0, "dias_negociados": 30, "negociado_por": "Marcos"})
        baloes = [
            f"Pra usar *2 telas simultâneas* no mês{virgula_nome}, em vez de R$ 60 fecho por *R$ 45,00*!",
            "Quer a chave PIX de *R$ 45,00* agora?"
        ]
        return baloes, dados_extras

    if any(k in texto_sem_acento for k in ["1 mes", "mensal", "30"]):
        dados_extras.update({"plano_comercial": "30", "valor_negociado": 30.0, "dias_negociados": 30, "negociado_por": "Marcos"})
        baloes = [
            f"No plano de *1 Mês* o valor de tabela é *R$ 30,00*{virgula_nome}.",
            "Mas olha quanto você economiza fechando mais meses (tanto pra *TV* quanto pro *App de Rádios*): *2m = R$ 50* | *3m = R$ 70* | *4m = R$ 90* | *6m = R$ 130* | *8m = R$ 160* | *12m = R$ 220*! Qual quer fechar?"
        ]
        return baloes, dados_extras

    intro = (
        f"A Camila me chamou aqui{virgula_nome}! Aqui é o *Marcos, gerente comercial*."
        if apresentou_como_escalacao
        else f"Opa{virgula_nome}! Tudo certo? Aqui é o *Marcos, gerente comercial da Central TV & Aplicativo de Rádios*."
    )
    baloes = [
        intro,
        (
            "Essa tabela oficial de descontos vale *tanto pro Aplicativo da TV quanto pro Aplicativo de Rádios PRO*:\n\n"
            "• *1 Mês (Tabela):* R$ 30,00\n"
            "• *2 Meses:* *R$ 50,00* (R$ 25,00/mês • economiza R$ 10)\n"
            "• *3 Meses:* *R$ 70,00* (R$ 23,33/mês • economiza R$ 20)\n"
            "• *4 Meses:* *R$ 90,00* (R$ 22,50/mês • *1 mês grátis!*)\n"
            "• *6 Meses:* *R$ 130,00* (R$ 21,67/mês • economiza R$ 50)\n"
            "• *8 Meses:* *R$ 160,00* (R$ 20,00/mês • economiza R$ 80)\n"
            "• *12 Meses (1 Ano):* *R$ 220,00* (R$ 18,33/mês • economiza R$ 140!)\n\n"
            "Depois que fecharmos o valor aqui e você fizer o PIX, a *Camila* já valida seu print e libera sua lista VIP completa na hora! Qual plano quer negociar?"
        )
    ]
    return baloes, dados_extras


def ativar_teste_2h_camila(pnome, nome, telefone, lead):
    """Entrega os 200 canais livres + gera credencial real de Teste 2 Horas no MongoDB."""
    virgula_nome = f", {pnome}" if pnome else ""
    dados_extras = {}
    if (lead or {}).get("teste_2h_concedido"):
        baloes = [
            f"Vi aqui que você já retirou um *Teste de 2 horas* recentemente neste número{virgula_nome} 😊",
            (
                f"Mas os *200 canais abertos + 40 rádios ao vivo* continuam 100% gratuitos no link:\n{LINK_PLAYER_IPTV}\n\n"
                "E se quiser liberar os *1.602 canais do pacote VIP completo (+1.402 extras)* hoje, o plano mensal é *R$ 30,00* ou posso chamar o *Gerente Marcos* para negociar 2 meses, 3 meses ou 1 Ano com desconto!"
            )
        ]
        return baloes, dados_extras

    usuario, senha, validade = gerar_credenciais_cinepro(
        telefone, nome, 0.0, "Teste Gratuito 2 Horas solicitado com a Camila", horas=2
    )
    dados_extras["teste_2h_concedido"] = True
    dados_extras["teste_iniciado_em"] = agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
    dados_extras["usuario_cinepro"] = usuario
    dados_extras["notificacao_jonas"] = (
        f"⏱️ *TESTE 2 HORAS GERADO PELA CAMILA!*\n"
        f"👤 Cliente: {nome} ({telefone})\n"
        f"🔑 Usuário: *{usuario}* | Senha: *{senha}*\n"
        f"⌛ Válido até: {validade}"
    )
    baloes = [
        f"Prontinho{virgula_nome}! Aqui é a Camila 😊 Separei seu *Teste Gratuito de 2 horas* (válido até {validade}) para você experimentar:",
        (
            f"Link direto: {LINK_PLAYER_IPTV}?u={usuario}&s={senha}\n"
            f"Usuário: {usuario}\n"
            f"Senha: {senha}\n\n"
            "E lembre que os *200 canais abertos + 40 rádios ao vivo* ficam sempre liberados de graça no mesmo endereço! "
            "Testa aí e me conta se gostou — se quiser fechar 1 mês (R$ 30) ou ver promoção de 2 meses, 3 meses e 1 Ano com o Gerente Marcos, é só avisar!"
        )
    ]
    return baloes, dados_extras


def processar_mensagem_inteligente(telefone, nome, mensagem, midia_url=None, tipo_midia="text", texto_comprovante="", canal="whatsapp"):
    texto = (mensagem or "").strip().lower()
    pnome = obter_primeiro_nome(nome)
    virgula_nome = f", {pnome}" if pnome else ""
    dados_extras = {}

    # 0. COMANDOS MESTRES DO JONAS PELO PRÓPRIO WHATSAPP (restrito ao WhatsApp + número oficial)
    tel_limpo = "".join(c for c in str(telefone) if c.isdigit())
    eh_jonas = (canal == "whatsapp") and tel_limpo.endswith("966707293")

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

    if eh_jonas and texto.startswith("#liberar"):
        partes = texto.split()
        tel_alvo = "".join(c for c in (partes[1] if len(partes) > 1 else "") if c.isdigit())
        if not tel_alvo:
            return (
                "MENU_INICIAL",
                "Controle Jonas Tech",
                ["Jonas, manda assim com o número junto: #liberar 5511999998888"],
                {}
            )
        lead_alvo = leads_col.find_one({"telefone": tel_alvo}) if leads_col is not None else None
        nome_alvo = (lead_alvo or {}).get("nome", "Cliente")
        pnome_alvo = obter_primeiro_nome(nome_alvo)
        usuario, senha, validade = gerar_credenciais_cinepro(tel_alvo, nome_alvo, 30.0, "Liberado manualmente pelo Jonas", dias=30)
        registrar_evento_email(
            "PAGAMENTO", nome_alvo, tel_alvo, 30.0,
            f"Liberação manual aprovada pelo Jonas • Usuário: {usuario}",
            "Acesso de 30 dias liberado."
        )
        msgs_cliente = [
            f"Opa{', ' + pnome_alvo if pnome_alvo else ''}! Tudo certinho, o Jonas acabou de confirmar seu pagamento aqui e já liberou o seu acesso! 🙌",
            f"Anota seus dados válidos até {validade}:\n\nUsuário: {usuario}\nSenha: {senha}\n\nLink direto: {LINK_PLAYER_IPTV}?u={usuario}&s={senha}",
            "Se abrir direto pelo link acima já entra liberado! Em outro aparelho ou TV, é só clicar em Entrar lá no topo e colocar esse usuário e senha."
        ]
        dados_extras["envio_extra_cliente"] = {"telefone": tel_alvo, "mensagens": msgs_cliente}
        return (
            "MENU_INICIAL",
            "Controle Jonas Tech",
            [f"Prontinho, Jonas! Gerei o usuário {usuario} e senha {senha} (válido até {validade}) e já enviei direto no WhatsApp do cliente! ✅"],
            dados_extras
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
    dados_extras["origem"] = "CENTRAL_IPTV_RADIOS"

    # Áudio recebido do cliente: pede gentilmente por texto mantendo o atendente do setor
    if tipo_midia == "audio":
        mapa_atendente_audio = {
            "SETOR_1_CINEPRO": "Camila",
            "SETOR_2_SUPORTE": "Lucas",
            "SETOR_3_COMERCIAL": "Marcos",
            "SETOR_4_JONAS_HUMANO": "Equipe do Jonas",
        }
        return (
            setor_atual,
            mapa_atendente_audio.get(setor_atual, "Atendimento Jonas Tech"),
            [f"Oi{virgula_nome}! Tô aqui na bancada agora com barulho e não consigo ouvir áudio, consegue me mandar por escrito rapidinho por favor? 😊"],
            dados_extras
        )

    # 2. DETECTOR INTELIGENTE DE COMPROVANTE PIX (OCR/PDF + BLINDAGEM)
    palavras_comprovante = [
        "comprovante", "paguei", "ta pago", "tá pago", "pix feito",
        "concluido", "concluído", "transferido", "mandei o pix", "fiz o pix"
    ]
    eh_pagamento_texto = any(p in texto for p in palavras_comprovante)
    eh_midia_comprovante = tipo_midia in ["image", "document"] and setor_atual != "SETOR_2_SUPORTE"
    tem_ocr_comprovante = bool((texto_comprovante or "").strip()) and setor_atual != "SETOR_2_SUPORTE"

    if eh_pagamento_texto and not eh_midia_comprovante and not tem_ocr_comprovante:
        valor_esp = (lead or {}).get("valor_negociado") or 30.0
        return (
            setor_atual,
            "Camila",
            [f"Show{virgula_nome}! Aqui é a *Camila*. Pode mandar a foto ou PDF do comprovante aqui que já confiro o valor combinado (*R$ {float(valor_esp):.2f}*) em nome de {TITULAR_CONTA} e libero sua Lista VIP na hora 😊"],
            dados_extras
        )

    if eh_midia_comprovante or tem_ocr_comprovante:
        plano_salvo_com = (lead or {}).get("plano_comercial", "30")
        valor_esperado = float((lead or {}).get("valor_negociado") or plano_salvo_com or 30.0)
        analise = analisar_comprovante_pix(texto_comprovante, texto, setor_atual, plano_salvo_com)
        if analise["ja_usado"]:
            registrar_auditoria_agente("Camila", "COMPROVANTE_REPETIDO", mensagem, 0.0, False, "Comprovante repetido bloqueado pela Camila.")
            dados_extras["notificacao_jonas"] = (
                f"⚠️ *ALERTA DE COMPROVANTE REPETIDO (CAMILA):*\n"
                f"👤 {nome} ({telefone}) enviou um comprovante já utilizado antes."
            )
            return (
                setor_atual,
                "Camila",
                [
                    f"Opa{virgula_nome}, aqui é a Camila! Esse comprovante já apareceu validado por aqui antes 🤔",
                    "Se você acabou de fazer um pagamento novo, manda a foto ou PDF certinho da transferência de hoje que já confiro e ativo na hora!"
                ],
                dados_extras
            )

        if analise["aprovado_automatico"]:
            registrar_comprovante_usado(analise["chave_unica"], telefone, analise["valor"])
            disparar_alerta_cliente_quente(telefone, nome, f"CAMILA VALIDOU PIX (R$ {analise['valor']:.2f})", analise["valor"])

            dias_liberados = calcular_dias_por_valor_iptv(analise["valor"])
            usuario, senha, validade = gerar_credenciais_cinepro(
                telefone, nome, analise["valor"], texto_comprovante, dias=dias_liberados
            )
            vip_ativos = len(_carregar_canais_vip_nuvem())
            abaixo_combinado = analise["valor"] + 1.0 < valor_esperado
            registrar_evento_email(
                "PAGAMENTO", nome, telefone, analise["valor"],
                f"Lista VIP ({dias_liberados} Dias) • Usuário {usuario}",
                f"Validado pela Camila ({'valor abaixo do combinado R$ ' + str(valor_esperado) if abaixo_combinado else 'integral'}) até {validade}."
            )
            dados_extras["status_pagamento"] = "APROVADO_PARCIAL" if abaixo_combinado else "APROVADO_AUTOMATICO"
            dados_extras["usuario_cinepro"] = usuario
            dados_extras["valor_pago"] = analise["valor"]
            dados_extras["notificacao_jonas"] = (
                f"💰 *VALIDAÇÃO DA CAMILA (ATIVAÇÃO VIP):*\n"
                f"👤 Cliente: {nome} ({telefone})\n"
                f"💵 Pago lido: R$ {analise['valor']:.2f} (Combinado: R$ {valor_esperado:.2f}) • {dias_liberados} dias\n"
                f"🔐 Usuário: *{usuario}* | Senha: *{senha}* (até {validade})"
            )
            if abaixo_combinado:
                registrar_auditoria_agente("Camila", "PAGAMENTO_PARCIAL", mensagem, 0.0, True, f"Pagou R$ {analise['valor']:.2f} de R$ {valor_esperado:.2f}; liberados {dias_liberados}d.")
                msg_validacao = (
                    f"Oi{virgula_nome}! Aqui é a *Camila*. Validei seu comprovante de *R$ {analise['valor']:.2f}* em nome de {TITULAR_CONTA}!\n\n"
                    f"Como o pacote combinado com o Gerente Marcos era *R$ {valor_esperado:.2f}*, liberei proporcionalmente *{dias_liberados} dias* no seu acesso enquanto o restante é conferido."
                )
            else:
                registrar_auditoria_agente("Camila", "PAGAMENTO_VALIDADO", mensagem, 0.0, True, f"Validou R$ {analise['valor']:.2f} ({dias_liberados}d) VIP.")
                msg_validacao = (
                    f"Perfeito{virgula_nome}! Aqui é a *Camila* 😊 Já conferi o seu print aqui certinho: pagamento de *R$ {analise['valor']:.2f}* em nome de {TITULAR_CONTA} validado com sucesso!"
                )
            info_vip = f"Lista VIP total ativa (*{200 + vip_ativos} canais/rádios*)" if vip_ativos > 0 else "acesso completo liberado (200 abertos/rádios + credenciais VIP ativas no cadastro)"
            return (
                "PAGAMENTO_RECEBIDO",
                "Camila",
                [
                    msg_validacao,
                    f"Validei a ativação do seu acesso ({info_vip}) por *{dias_liberados} dias* (até {validade})! Anota seus dados pra entrar na TV e no App de Rádios:\n\nUsuário: {usuario}\nSenha: {senha}\n\nLink direto: {LINK_PLAYER_IPTV}?u={usuario}&s={senha}",
                    "Tocando nesse link acima já entra liberado na hora! Se for abrir na Smart TV, clique em *Entrar* lá no topo e coloque esse usuário e senha."
                ],
                dados_extras
            )

        dados_extras["status_pagamento"] = "AGUARDANDO_CONFERENCIA_JONAS"
        registrar_auditoria_agente("Camila", "PAGAMENTO_EM_ANALISE", mensagem, 0.0, False, "Comprovante enviado para conferência manual.")
        dados_extras["notificacao_jonas"] = (
            f"⚠️ *COMPROVANTE PARA CONFERIR (CAMILA):*\n"
            f"👤 Cliente: {nome} ({telefone})\n"
            f"📄 Leitura parcial: {(texto_comprovante or 'imagem/PDF sem texto legível')[:120]}\n\n"
            f"👉 Caiu na conta? Responda aqui:\n*#liberar {telefone}*"
        )
        return (
            "PAGAMENTO_EM_ANALISE",
            "Camila",
            [
                f"Recebi seu comprovante aqui{virgula_nome}, sou a *Camila*! 🙏",
                f"Como alguns números não ficaram totalmente nítidos na leitura automática, já passei agora mesmo pro Jonas confirmar no {BANCO_RECEBEDOR} e validar sua ativação em instantes!"
            ],
            dados_extras
        )

    # 3. RESET NATURAL POR SAUDAÇÃO PURA OU VOLTAR
    saudacoes_puras = [
        "oi", "olá", "ola", "opa", "bom dia", "boa tarde", "boa noite",
        "e ai", "e aí", "tudo bem", "tudo bem?", "oi tudo bem",
        "menu", "voltar", "inicio", "início"
    ]
    if texto in saudacoes_puras:
        setor_atual = "MENU_INICIAL"

    # 4. DETECÇÃO PRECISA DE INTENÇÃO E TROCA DE ASSUNTO (FOCO 100% IPTV & RÁDIOS)
    texto_compacto = re.sub(r"\s+", " ", texto).strip()
    opc_limpa = texto_compacto.rstrip(".):-! ")
    eh_opc_1 = opc_limpa in ["1", "opcao 1", "opção 1"]
    eh_opc_2 = opc_limpa in ["2", "opcao 2", "opção 2"]
    eh_opc_3 = opc_limpa in ["3", "opcao 3", "opção 3"]
    eh_opc_4 = opc_limpa in ["4", "opcao 4", "opção 4"]

    texto_sem_acento = normalizar_giria_whatsapp(texto)
    eh_chamar_lucas = opc_limpa == "lucas" or any(p in texto_sem_acento for p in [
        "falar com lucas", "falar com o lucas", "chama o lucas", "chamar lucas",
        "passa pro lucas", "quero falar com lucas", "quero o lucas"
    ])
    eh_chamar_marcos = opc_limpa == "marcos" or any(p in texto_sem_acento for p in [
        "falar com marcos", "falar com o marcos", "chama o marcos", "chamar marcos",
        "passa pro marcos", "quero falar com marcos", "quero o marcos", "gerente", "falar com gerente"
    ])
    eh_chamar_camila = opc_limpa == "camila" or any(p in texto_sem_acento for p in [
        "falar com camila", "falar com a camila", "chama a camila", "chamar camila",
        "passa pra camila", "quero falar com camila", "quero a camila"
    ])

    eh_intencao_humano = eh_opc_4 or opc_limpa == "jonas" or any(p in texto_sem_acento for p in [
        "falar com jonas", "falar com o jonas", "chama o jonas", "atendente humano", "falar com humano", "falar com dono"
    ])
    eh_escalacao_gerente = (
        eh_opc_3
        or eh_chamar_marcos
        or bool(re.search(r"\b(25|45|50|65|70|85|90|120|130|150|160|200|220|240)\b", texto_sem_acento))
        or any(p in texto_sem_acento for p in [
            "desconto", "promocao", "mais barato", "negocia", "caro", "faz por", "abaixa", "melhora", "condicao",
            "2 meses", "3 meses", "4 meses", "quatro meses", "6 meses", "8 meses", "oito meses",
            "trimestral", "quadrimestral", "semestral", "1 ano", "anual", "um ano",
            "2 telas", "duas telas", "planos", "pacotes", "tabela"
        ])
    )
    eh_intencao_suporte = eh_opc_2 or eh_chamar_lucas or any(p in texto_sem_acento for p in [
        "suporte", "tecnico", "defeito", "erro", "formatar", "pc lento", "computador lento",
        "travando", "engasgando", "oscilando", "tela preta", "sem som", "fora do ar", "canal caiu",
        "parou", "nao funciona", "nao pega", "nao abre", "nao entra", "nao carrega",
        "nao baixa", "nao instala", "nao conecta", "nao consigo", "nao tem navegador", "sem navegador",
        "tv antiga", "tv comum", "modelo antigo", "sem internet", "sem wifi", "sem wi-fi",
        "travou", "caiu", "sumiu", "sem sinal", "colocar na tv", "coloca na tv", "botar na tv",
        "instalar na tv", "como coloca", "todos os canais", "um canal", "um so"
    ])
    eh_intencao_tv = eh_opc_1 or eh_chamar_camila or any(p in texto_sem_acento for p in [
        "tv", "iptv", "cinepro", "canais", "radio", "radios", "app da radio", "aplicativo da radio", "aberta",
        "teste", "testar", "2h", "2 horas", "duas horas", "degustacao", "gratuito", "gratis", "800", "200",
        "assinar", "quero fechar", "quanto custa", "valor", "preco", "mensal", "30"
    ])
    eh_pedido_explicito_canais_tv = eh_opc_1 or eh_chamar_camila or any(p in texto_sem_acento for p in [
        "canais", "tv aberta", "central gratuita", "central de tv", "cinepro",
        "radio", "radios", "quero testar a tv", "link da tv", "quero abrir a central", "teste de 2"
    ])

    resposta_anterior_lead = (lead or {}).get("resposta", "")
    lucas_ja_atendeu = (
        setor_atual == "SETOR_2_SUPORTE"
        or (lead or {}).get("atendente_responsavel") == "Lucas"
        or "Lucas" in resposta_anterior_lead
    )

    if eh_intencao_humano or eh_chamar_lucas or eh_chamar_marcos or eh_chamar_camila:
        setor_atual = "MENU_INICIAL"
    elif setor_atual == "SETOR_1_CINEPRO" and eh_intencao_suporte and not eh_escalacao_gerente:
        setor_atual = "MENU_INICIAL"
    elif setor_atual == "SETOR_2_SUPORTE":
        if eh_escalacao_gerente or (eh_pedido_explicito_canais_tv and not eh_intencao_suporte):
            setor_atual = "MENU_INICIAL"
    elif setor_atual == "SETOR_3_COMERCIAL":
        if eh_intencao_suporte and not eh_escalacao_gerente:
            setor_atual = "MENU_INICIAL"
        elif eh_pedido_explicito_canais_tv and not eh_escalacao_gerente and not any(p in texto_sem_acento for p in ["pix", "fechar", "pagar", "comprar"]):
            setor_atual = "MENU_INICIAL"

    # 5. ROTEAMENTO CONVERSACIONAL RESOLUTIVO (100% IPTV & RÁDIOS)
    if setor_atual == "MENU_INICIAL":
        if eh_intencao_humano:
            novo_setor = "SETOR_4_JONAS_HUMANO"
            atendente = "Equipe do Jonas"
            dados_extras["avisou_aguardo_humano"] = False
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE SOLICITOU ATENDIMENTO HUMANO COM O JONAS")
            baloes = [
                f"Pode deixar{virgula_nome}! Já dei um toque no celular pessoal do Jonas pra ele assumir nossa conversa aqui.",
                "Se quiser, já pode ir mandando sua dúvida por escrito que assim que ele pegar no aparelho já te responde direto, combinado?"
            ]
        elif eh_intencao_suporte and not eh_escalacao_gerente:
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas"
            baloes, notif = diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante, resposta_anterior_lead, lucas_ja_atendeu)
            if notif:
                dados_extras["notificacao_jonas"] = notif
        elif eh_escalacao_gerente:
            novo_setor = "SETOR_3_COMERCIAL"
            atendente = "Marcos"
            baloes, extras_marcos = negociar_gerente_marcos(pnome, nome, telefone, mensagem, texto_sem_acento, lead, apresentou_como_escalacao=False)
            dados_extras.update(extras_marcos)
        elif any(p in texto_sem_acento for p in ["pc", "computador", "notebook", "lento", "windows", "ajuda", "conserto"]):
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas"
            baloes, notif = diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante, resposta_anterior_lead, lucas_ja_atendeu)
            if notif:
                dados_extras["notificacao_jonas"] = notif
        elif eh_intencao_tv or any(p in texto_sem_acento for p in ["futebol", "filme", "serie", "jogo", "ouvir"]):
            novo_setor = "SETOR_1_CINEPRO"
            atendente = "Camila"
            if any(p in texto_sem_acento for p in ["teste", "testar", "2h", "2 horas", "duas horas", "degustacao"]):
                baloes, extras_2h = ativar_teste_2h_camila(pnome, nome, telefone, lead)
                dados_extras.update(extras_2h)
            elif any(p in texto_sem_acento for p in ["radio", "radios", "musica", "fm", "sertanejo"]):
                baloes = [
                    f"Oi{virgula_nome}! Aqui é a Camila 😊 Temos *40 rádios ao vivo gratuitas* (junto com os *200 canais de TV Aberta e Notícias*)!",
                    f"É só tocar nesse link aqui e clicar na aba *📻 Rádios & Música*:\n{LINK_PLAYER_IPTV}\n\nSe quiser também fazer um *Teste de 2 horas* do pacote VIP completo (*1.602 canais ao vivo*) ou saber os planos, é só pedir!"
                ]
            else:
                dados_extras["teste_iniciado_em"] = agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
                baloes = [
                    f"Oi{virgula_nome}! Tudo bom? Aqui é a Camila 😊 Separei nossa *Central CinePro TV & Rádios* para você:",
                    (
                        f"📺 *200 Canais Abertos + 40 Rádios ao vivo GRÁTIS* direto no navegador:\n{LINK_PLAYER_IPTV}\n\n"
                        "⏱️ Quer testar tudo antes de assinar? Posso liberar agora mesmo um *Teste Gratuito de 2 horas* do pacote VIP completo (*1.602 canais auditados* — R$ 30,00/mês)!\n"
                        "É só me pedir *teste 2h*, *rádios* ou perguntar os valores!"
                    )
                ]
        else:
            novo_setor = "MENU_INICIAL"
            atendente = "Recepção Jonas Tech"
            baloes = obter_recepcao_natural(pnome)

    elif setor_atual == "SETOR_1_CINEPRO":
        if eh_escalacao_gerente:
            novo_setor = "SETOR_3_COMERCIAL"
            atendente = "Marcos"
            baloes_gerente, extras_marcos = negociar_gerente_marcos(
                pnome, nome, telefone, mensagem, texto_sem_acento, lead, apresentou_como_escalacao=True
            )
            dados_extras.update(extras_marcos)
            baloes = [
                f"Olha{virgula_nome}, esse tipo de desconto / condição especial em pacotes maiores eu não consigo liberar sozinha aqui, mas já chamei o meu gerente *Marcos* agora mesmo pra conversar com você!"
            ] + baloes_gerente
        else:
            atendente = "Camila"
            novo_setor = "SETOR_1_CINEPRO"
            if any(p in texto_sem_acento for p in ["teste", "testar", "2h", "2 horas", "duas horas", "degustacao"]):
                baloes, extras_2h = ativar_teste_2h_camila(pnome, nome, telefone, lead)
                dados_extras.update(extras_2h)
            elif any(p in texto_sem_acento for p in ["pix", "pagar", "quero fechar", "quero assinar", "manda a chave", "chave"]):
                dados_extras["plano_comercial"] = "30"
                dados_extras["valor_negociado"] = 30.0
                disparar_alerta_cliente_quente(telefone, nome, "CAMILA: CLIENTE PEDIU PIX MENSAL R$ 30,00", 30.0)
                baloes = montar_bloco_pix(pnome, PLANOS_IPTV["30"][1])
            elif any(p in texto_sem_acento for p in ["quanto e", "quanto custa", "valor", "preco", "mensal", "assinar", "comprar", "30", "800"]):
                baloes = [
                    f"Funciona assim{virgula_nome}: os *200 canais livres + 40 rádios* já são totalmente gratuitos no nosso link!",
                    (
                        f"Agora, se você quiser o *Pacote Completo (TV Lista VIP + Aplicativo de Rádios PRO)*, o plano mensal de tabela comigo é *R$ 30,00 por mês* (ou você pode pedir *teste 2h* para testar antes).\n\n"
                        "Se quiser ver descontos para *2, 3, 4, 6, 8 ou 12 meses*, me avisa que eu chamo o *Gerente Marcos* na hora!"
                    )
                ]
            elif any(p in texto_sem_acento for p in ["radio", "radios", "musica", "fm", "sertanejo"]):
                baloes = [
                    f"Temos *40 rádios ao vivo gratuitas* dentro do mesmo link{virgula_nome}! 📻",
                    f"Abra {LINK_PLAYER_IPTV} e toque na categoria *📻 Rádios & Música* — funciona liso no celular, computador ou Smart TV!"
                ]
            elif "roku" in texto_sem_acento:
                baloes = [
                    f"Na *Roku TV* é bem tranquilo{virgula_nome}! Como ela não traz navegador aberto para digitar endereços, o jeito certo é abrir o nosso link no celular e clicar em *Transmitir / Espelhar Tela* (Smart View ou AirPlay) para jogar na TV.",
                    f"Link para abrir no celular:\n{LINK_PLAYER_IPTV}"
                ]
            elif any(p in texto_sem_acento for p in ["samsung", "lg", "tcl", "philco", "aoc", "tv box", "box", "fire", "android"]):
                baloes = [
                    f"Nesse modelo é bem rápido{virgula_nome}! Abra o aplicativo *Internet / Navegador / Browser* da sua TV ou TV Box e digite o link:\n{LINK_PLAYER_IPTV}",
                    "Depois é só salvar nos favoritos da TV para entrar com 1 clique sempre que quiser assistir!"
                ]
            elif any(p in texto_sem_acento for p in ["smart", "como instala", "colocar na tv"]):
                baloes = [
                    "Na Smart TV ou TV Box é bem simples! Dá pra abrir direto pelo navegador da própria TV usando o nosso link.",
                    "Qual é a marca da sua TV aí (Samsung, LG, Roku ou TV Box)? Me fala que te explico certinho como colocar!"
                ]
            elif any(p in texto_sem_acento for p in ["globo", "sbt", "record", "band", "sportv", "premiere", "netflix", "futebol", "jogo", "fechado"]):
                baloes = [
                    f"Boa pergunta{virgula_nome}! Os *200 canais gratuitos + 40 rádios* já trazem TV Aberta e Notícias de graça no link.",
                    f"Para liberar a grade VIP com mais *+1.402 canais extras auditados* (filmes, séries, esportes livres, infantis e TVs regionais — *1.602 canais ao todo*), peça um *Teste grátis de 2 horas* ou assine por *R$ 30,00/mês*!\nLink: {LINK_PLAYER_IPTV}"
                ]
            elif any(p in texto_sem_acento for p in ["abriu", "funcionou", "top", "bom", "gostei", "rodou", "show", "otimo", "sim", "deu certo"]):
                baloes = [
                    f"Que massa{virgula_nome}, fico feliz que rodou liso aí! 😄",
                    "Se quiser experimentar os *1.602 canais do pacote VIP completo* por *2 horas grátis* ou chamar o *Gerente Marcos* pra ver promoção de 2 meses, 3 meses ou 1 Ano, é só falar!"
                ]
            else:
                baloes = gerar_resposta_fallback_inteligente("SETOR_1_CINEPRO", pnome, mensagem)

    elif setor_atual == "SETOR_2_SUPORTE":
        atendente = "Lucas"
        novo_setor = "SETOR_2_SUPORTE"
        baloes, notif = diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante, resposta_anterior_lead, True)
        if notif:
            dados_extras["notificacao_jonas"] = notif

    elif setor_atual == "SETOR_3_COMERCIAL":
        atendente = "Marcos"
        novo_setor = "SETOR_3_COMERCIAL"
        baloes, extras_marcos = negociar_gerente_marcos(
            pnome, nome, telefone, mensagem, texto_sem_acento, lead, apresentou_como_escalacao=False
        )
        dados_extras.update(extras_marcos)

    elif setor_atual == "SETOR_4_JONAS_HUMANO":
        atendente = "Equipe do Jonas"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        if (lead or {}).get("avisou_aguardo_humano"):
            return novo_setor, "Aguardando Jonas", [], {"aguardando_humano": True}
        dados_extras["avisou_aguardo_humano"] = True
        baloes = ["Anotei aqui pra ele ver assim que pegar no celular, fica tranquilo! 👍"]

    else:
        novo_setor = "MENU_INICIAL"
        atendente = "Recepção Jonas Tech"
        baloes = gerar_resposta_fallback_inteligente("MENU_INICIAL", pnome, mensagem)

    return novo_setor, atendente, baloes, dados_extras


@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "online",
        "servico": "Central Humana & Relatórios 24/7 - Jonas Tech Solutions",
        "versao": "6.0_AUTOMACOES_MERCADOPAGO_FALLBACK",
        "banco": "MongoDB Atlas Conectado",
        "recursos_ativos": [
            "1. Atendimento 100% Natural com Fallback Contextual",
            "2. Camila: PIX Blindado + OCR/PDF + API Mercado Pago + Login 30 Dias",
            "3. Lucas: Diagnóstico Suporte TI + Relatório E-mail",
            "4. Marcos: Consultoria Comercial + PDV R$ 150 / Combo R$ 350",
            "5. Keep-Alive Anti-Sleep Ativo 24/7",
            "6. Automação de E-mail via SMTP Gmail Seguro"
        ],
        "timestamp": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/api/relatorio-email", methods=["GET"])
def api_relatorio_email():
    hoje = agora_brasilia().strftime("%Y-%m-%d")
    eventos_hoje = []
    if eventos_email_col is not None:
        try:
            eventos_hoje = list(eventos_email_col.find({"data_dia": hoje}, {"_id": 0}))
        except Exception as e:
            print(f"[ERRO LER EVENTOS EMAIL]: {e}")

    pagamentos = [e for e in eventos_hoje if e.get("tipo") == "PAGAMENTO"]
    suportes = [e for e in eventos_hoje if e.get("tipo") == "SUPORTE_TECNICO"]
    total_whatsapp_dia = sum(float(e.get("valor") or 0.0) for e in pagamentos)

    total_pdv_dia = 0.0
    total_geral_historico_pdv = 0.0
    if vendas_pdv_col is not None:
        try:
            for v in vendas_pdv_col.find({}, {"_id": 0, "total_liquido": 1, "total": 1, "data_hora": 1}):
                val = float(v.get("total_liquido") or v.get("total") or 0.0)
                total_geral_historico_pdv += val
                if str(v.get("data_hora") or "").startswith(hoje):
                    total_pdv_dia += val
        except Exception as e:
            print(f"[ERRO LER VENDAS PDV]: {e}")

    return jsonify({
        "data_dia": hoje,
        "gerado_em": agora_brasilia().strftime("%d/%m/%Y às %H:%M:%S"),
        "total_whatsapp_dia": round(total_whatsapp_dia, 2),
        "qtd_pagamentos_dia": len(pagamentos),
        "total_pdv_dia": round(total_pdv_dia, 2),
        "total_geral_historico_pdv": round(total_geral_historico_pdv, 2),
        "total_acumulado_dia": round(total_whatsapp_dia + total_pdv_dia, 2),
        "pagamentos": pagamentos,
        "suportes": suportes,
        "pendentes_envio": [e for e in eventos_hoje if not e.get("enviado_email")]
    }), 200


@app.route("/api/relatorio-email/marcar-enviado", methods=["POST"])
def api_relatorio_marcar_enviado():
    dados = request.get_json(silent=True) or {}
    ids = dados.get("ids") or []
    if ids and eventos_email_col is not None:
        try:
            eventos_email_col.update_many({"id_evento": {"$in": ids}}, {"$set": {"enviado_email": True}})
        except Exception as e:
            return jsonify({"ok": False, "erro": str(e)}), 500
    return jsonify({"ok": True, "marcados": len(ids)}), 200


@app.route("/api/cinepro/login", methods=["POST", "OPTIONS"])
def api_cinepro_login():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    dados = request.get_json(silent=True) or {}
    usuario = (dados.get("usuario") or "").strip().lower()
    senha = (dados.get("senha") or "").strip()
    if not usuario or not senha:
        return jsonify({"ok": False, "erro": "Informe seu usuário e senha."}), 400
    if assinantes_col is None:
        return jsonify({"ok": False, "erro": "Banco temporariamente indisponível."}), 500
    doc = assinantes_col.find_one({"usuario": usuario, "senha": senha})
    if not doc or doc.get("status") != "ATIVO":
        return jsonify({"ok": False, "erro": "Usuário ou senha inválidos."}), 401
    agora_ms = int(datetime.utcnow().timestamp() * 1000)
    expira_ts = int(doc.get("expira_ts") or 0)
    if expira_ts and agora_ms > expira_ts:
        return jsonify({"ok": False, "erro": "Seu período de acesso venceu. Renove no WhatsApp ou Chat Online!"}), 403
    return jsonify({
        "ok": True,
        "usuario": usuario,
        "nome": doc.get("nome", "Assinante"),
        "expira_em": doc.get("expira_em", "30 dias"),
        "expira_ts": expira_ts
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
    texto_comprovante = dados.get("texto_comprovante") or ""

    if not mensagem and tipo_midia == "text" and not texto_comprovante:
        return jsonify({"erro": "Nenhuma mensagem encontrada no payload"}), 400

    t0_proc = time.perf_counter()
    novo_setor, atendente, lista_baloes, extras = processar_mensagem_inteligente(
        telefone, nome, mensagem, midia_url, tipo_midia, texto_comprovante
    )
    ms_proc = (time.perf_counter() - t0_proc) * 1000
    registrar_auditoria_agente(atendente, novo_setor, mensagem, ms_proc, sucesso=True)
    resposta_consolidada = "\n\n".join(lista_baloes)

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
            for k, v in extras.items():
                if k not in ["notificacao_jonas", "envio_extra_cliente"]:
                    update_data[k] = v
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
        "notificacao_jonas": extras.get("notificacao_jonas"),
        "envio_extra_cliente": extras.get("envio_extra_cliente"),
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


# ==============================================================================
# ROTAS DO SISTEMA COMERCIAL PDV & ESTOQUE 100% NA NUVEM (MONGODB ATLAS)
# ==============================================================================

@app.route("/pdv", methods=["GET"])
def rota_pdv_interface_nuvem():
    """Serve a interface completa do PDV direto da nuvem para celular, tablet ou PC."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interface_pdv.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Interface PDV em atualização", 404


@app.route("/api/produtos", methods=["GET"])
def api_pdv_listar_produtos():
    """Lista catálogo de produtos direto do MongoDB Atlas."""
    try:
        busca = (request.args.get("busca") or "").strip()
        filtro = {}
        if busca:
            filtro = {"$or": [
                {"nome": {"$regex": busca, "$options": "i"}},
                {"sku": {"$regex": busca, "$options": "i"}},
                {"codigo_barras": {"$regex": busca, "$options": "i"}}
            ]}
        docs = list(col_produtos.find(filtro, {"_id": 0}).limit(150)) if col_produtos is not None else []
        resultado = []
        for d in docs:
            resultado.append({
                "codigo_barras": d.get("sku") or d.get("codigo_barras"),
                "sku": d.get("sku") or d.get("codigo_barras"),
                "nome": d.get("nome"),
                "preco_venda": float(d.get("preco_venda") or 0.0),
                "preco_custo": float(d.get("preco_custo") or 0.0),
                "estoque_atual": float(d.get("quantidade_estoque") or d.get("estoque_atual") or 0.0),
                "estoque_minimo": float(d.get("estoque_minimo_alerta") or d.get("estoque_minimo") or 5.0),
                "unidade": d.get("unidade", "UN"),
                "categoria_nome": d.get("categoria", "Geral"),
                "margem_lucro": float(d.get("margem_lucro_percentual") or 0.0)
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/produtos/<codigo>", methods=["GET"])
def api_pdv_buscar_produto_codigo(codigo):
    """Busca produto individual pelo código de barras ou SKU no MongoDB Atlas."""
    try:
        if col_produtos is None:
            return jsonify({"erro": "Banco de dados indisponível"}), 503
        doc = col_produtos.find_one({"$or": [{"sku": codigo}, {"codigo_barras": codigo}]}, {"_id": 0})
        if not doc:
            return jsonify({"erro": "Produto não encontrado"}), 404
        return jsonify({
            "codigo_barras": doc.get("sku") or doc.get("codigo_barras"),
            "sku": doc.get("sku") or doc.get("codigo_barras"),
            "nome": doc.get("nome"),
            "preco_venda": float(doc.get("preco_venda") or 0.0),
            "preco_custo": float(doc.get("preco_custo") or 0.0),
            "estoque_atual": float(doc.get("quantidade_estoque") or doc.get("estoque_atual") or 0.0),
            "unidade": doc.get("unidade", "UN")
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/produtos", methods=["POST"])
def api_pdv_cadastrar_produto():
    """Cadastra ou atualiza produto no MongoDB Atlas."""
    try:
        dados = request.json or {}
        sku = str(dados.get("codigo_barras") or dados.get("sku", "")).strip()
        nome = str(dados.get("nome", "")).strip()
        if not sku or not nome:
            return jsonify({"erro": "Código e Nome são obrigatórios"}), 400

        pv = float(dados.get("preco_venda", 0.0))
        pc = float(dados.get("preco_custo", 0.0))
        margem = round(((pv - pc) / pv) * 100, 1) if pv > 0 else 0.0
        doc = {
            "sku": sku,
            "codigo_barras": sku,
            "nome": nome,
            "preco_venda": pv,
            "preco_custo": pc,
            "margem_lucro_percentual": margem,
            "quantidade_estoque": float(dados.get("estoque_inicial") or dados.get("quantidade_estoque") or 10.0),
            "estoque_minimo_alerta": float(dados.get("estoque_minimo") or 5.0),
            "unidade": dados.get("unidade", "UN"),
            "categoria": dados.get("categoria", "Comercial"),
            "atualizado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
        }
        col_produtos.update_one({"$or": [{"sku": sku}, {"codigo_barras": sku}]}, {"$set": doc}, upsert=True)
        return jsonify({"sucesso": True, "produto": doc}), 201
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/venda", methods=["POST"])
def api_pdv_registrar_venda():
    """Registra venda no Atlas, dá baixa no estoque, aplica desconto e gerencia fiado."""
    try:
        dados = request.json or {}
        itens = dados.get("itens") or []
        if not itens:
            return jsonify({"erro": "O carrinho está vazio"}), 400

        forma_pgto = dados.get("forma_pagamento", "DINHEIRO").upper()
        cliente_nome = (dados.get("cliente_nome") or "Consumidor Balcão").strip()
        cliente_cpf = (dados.get("cliente_cpf") or "").strip()
        desconto_valor = float(dados.get("desconto_valor", 0.0))

        subtotal_bruto = 0.0
        itens_formatados = []

        for item in itens:
            cod = str(item.get("codigo_barras") or item.get("sku", ""))
            qtd = float(item.get("quantidade", 1))
            preco_un = float(item.get("preco_unitario", 0))
            subtotal = round(qtd * preco_un, 2)
            subtotal_bruto += subtotal

            itens_formatados.append({
                "codigo_barras": cod,
                "nome": item.get("nome"),
                "quantidade": qtd,
                "preco_unitario": preco_un,
                "subtotal": subtotal
            })

            # Dá baixa imediata no estoque no Atlas
            if col_produtos is not None:
                col_produtos.update_one(
                    {"$or": [{"sku": cod}, {"codigo_barras": cod}]},
                    {"$inc": {"quantidade_estoque": -qtd}}
                )

        total_liquido = max(0.0, round(subtotal_bruto - desconto_valor, 2))
        cod_venda = f"VD-{int(time.time())}"
        data_hora = agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
        valor_pago = float(dados.get("valor_pago") or total_liquido)
        troco = max(0.0, round(valor_pago - total_liquido, 2)) if forma_pgto == "DINHEIRO" else 0.0

        # Se a venda for no FIADO / A PRAZO, lança débito automático na conta do cliente
        if forma_pgto in ["FIADO", "A_PRAZO", "PRAZO"] and col_clientes is not None and cliente_cpf:
            col_clientes.update_one(
                {"cpf_cnpj": cliente_cpf},
                {"$inc": {"saldo_devedor": total_liquido}}
            )

        doc_venda = {
            "codigo_venda": cod_venda,
            "data_hora": data_hora,
            "cliente_nome": cliente_nome,
            "cliente_cpf": cliente_cpf,
            "subtotal_bruto": round(subtotal_bruto, 2),
            "desconto_valor": round(desconto_valor, 2),
            "total_liquido": total_liquido,
            "forma_pagamento": forma_pgto,
            "valor_pago": valor_pago,
            "troco": troco,
            "itens": itens_formatados,
            "status": "CONCLUIDA"
        }

        if col_vendas is not None:
            col_vendas.insert_one(doc_venda)

        # Registra automaticamente no relatório de e-mail diário do Jonas
        registrar_evento_email(
            "VENDA_PDV", cliente_nome, f"({cliente_cpf or 'Balcão'})", total_liquido,
            f"Venda #{cod_venda} ({len(itens)} itens)",
            f"Pagamento em {forma_pgto} no PDV Nuvem"
        )

        doc_venda.pop("_id", None)
        return jsonify(doc_venda), 201
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/caixa/status", methods=["GET"])
def api_pdv_caixa_status():
    """Retorna faturamento e resumo de vendas do dia no MongoDB Atlas."""
    try:
        hoje_str = agora_brasilia().strftime("%d/%m/%Y")
        vendas = list(col_vendas.find({"data_hora": {"$regex": f"^{hoje_str}"}}, {"_id": 0})) if col_vendas is not None else []
        total_dinheiro = sum(v.get("total_liquido", 0) for v in vendas if v.get("forma_pagamento") == "DINHEIRO")
        total_pix = sum(v.get("total_liquido", 0) for v in vendas if v.get("forma_pagamento") == "PIX")
        total_debito = sum(v.get("total_liquido", 0) for v in vendas if "DEBITO" in v.get("forma_pagamento", ""))
        total_credito = sum(v.get("total_liquido", 0) for v in vendas if "CREDITO" in v.get("forma_pagamento", "") or "CARTAO" in v.get("forma_pagamento", ""))
        total_geral = sum(v.get("total_liquido", 0) for v in vendas)

        return jsonify({
            "sessao_id": 1,
            "aberto_em": f"{hoje_str} 08:00:00",
            "saldo_inicial": 100.0,
            "total_vendas": round(total_geral, 2),
            "total_dinheiro": round(total_dinheiro, 2),
            "total_pix": round(total_pix, 2),
            "total_cartao_debito": round(total_debito, 2),
            "total_cartao_credito": round(total_credito, 2),
            "qtd_vendas": len(vendas),
            "status": "ABERTO"
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/caixa/fechar", methods=["POST"])
def api_pdv_caixa_fechar():
    """Fecha o caixa e salva no MongoDB Atlas."""
    try:
        hoje_str = agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
        doc_fechamento = {
            "fechado_em": hoje_str,
            "operador": "Jonas Mendonça",
            "status": "FECHADO_COM_SUCESSO"
        }
        if col_fechamentos is not None:
            col_fechamentos.insert_one(doc_fechamento)
        return jsonify({"sucesso": True, "fechamento": doc_fechamento}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/pix/gerar", methods=["POST"])
def api_pdv_pix_gerar():
    """Gera QR Code PIX dinâmico com chave oficial do Mercado Pago."""
    try:
        dados = request.json or {}
        valor = float(dados.get("valor", 0.01))
        payload = gerar_payload_pix(CHAVE_PIX_OFICIAL, TITULAR_CONTA, CIDADE_RECEBEDOR, valor)
        url_qr = gerar_url_qrcode_instantaneo(payload, 300)
        return jsonify({
            "payload_copia_cola": payload,
            "qrcode_url": url_qr,
            "chave_pix": CHAVE_PIX_OFICIAL,
            "titular": TITULAR_CONTA,
            "valor": valor
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500




# ==============================================================================
# MÓDULOS EXPANDIDOS ERP NUVEM: CINEPRO TV, BREAK-EVEN, CRM E FROTAS/SEGUROS
# ==============================================================================

@app.route("/tv", methods=["GET"])
@app.route("/cinepro", methods=["GET"])
@app.route("/player", methods=["GET"])
def rota_cinepro_player_nuvem():
    """Serve o Player Oficial do CinePro TV direto da Nuvem no Render sem 404."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cinepro_player.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Player CinePro em atualização", 404


@app.route("/tv.html", methods=["GET"])
@app.route("/tv-samsung", methods=["GET"])
def rota_cinepro_tv_samsung_leve():
    """Serve o Modo Smart TV Leve (ES5 puro) compatível com TVs Samsung e TV Box antigas."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Modo Smart TV Leve em atualização", 404


def _carregar_canais_vip_nuvem():
    """Carrega lista VIP opcional (canais_vip.json ou VIP_M3U_URL) mantendo apenas canais reais configurados."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    arq_vip = os.path.join(pasta, "canais_vip.json")
    if os.path.exists(arq_vip):
        try:
            with open(arq_vip, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    return dados
        except Exception as e:
            print(f"[ERRO LER CANAIS VIP]: {e}")
    return []


@app.route("/canais.json", methods=["GET"])
def rota_canais_json_nuvem():
    """Entrega o catálogo com 200 canais públicos e rádios selecionados direto da Nuvem."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canais.json")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "application/json; charset=utf-8"}
    return jsonify([]), 404


@app.route("/api/status_servidor", methods=["GET"])
def api_status_servidor_cinepro():
    """Informa ao player CinePro o status real da grade VIP na nuvem."""
    canais_vip = _carregar_canais_vip_nuvem()
    return jsonify({
        "ativo": True,
        "modo": "VIP_NUVEM" if canais_vip else "GRATUITO_200",
        "docker": False,
        "vip_nuvem": bool(canais_vip),
        "requer_chave": True,
        "qtd_vip_extras": len(canais_vip),
        "timestamp": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/api/canais_vip", methods=["GET"])
def api_canais_vip_cinepro():
    """Libera canais VIP adicionais mediante chave/usuário ativo no MongoDB."""
    chave = (request.args.get("chave") or "").strip().lower()
    canais_vip = _carregar_canais_vip_nuvem()
    if not canais_vip:
        return jsonify({"ok": True, "canais": [], "aviso": "Grade VIP em sincronização"}), 200
    if not chave or assinantes_col is None:
        return jsonify({"ok": False, "erro": "Informe sua chave de assinante ou teste 2h."}), 401
    doc = assinantes_col.find_one({"usuario": chave, "status": "ATIVO"})
    if not doc:
        return jsonify({"ok": False, "erro": "Código VIP inválido ou vencido."}), 401
    agora_ms = int(datetime.utcnow().timestamp() * 1000)
    if int(doc.get("expira_ts") or 0) and agora_ms > int(doc.get("expira_ts")):
        return jsonify({"ok": False, "erro": "Acesso expirado. Renove pelo Chat Online ou WhatsApp!"}), 401
    return jsonify({"ok": True, "canais": canais_vip}), 200


# ==============================================================================
# CONTROLE REMOTO DA TV VIA QR CODE NA NUVEM (/controle + /api/controle/*)
# ==============================================================================
_CONTROLE_TV_LOCK = threading.Lock()
_CONTROLE_TV_SALAS = {}


def _normalizar_codigo_tv(raw: str) -> str:
    return re.sub(r"[^A-Z0-9_-]", "", (raw or "").strip().upper())[:24]


def _limpar_salas_antigas():
    agora = time.time()
    expiradas = [k for k, v in _CONTROLE_TV_SALAS.items() if agora - float(v.get("atualizado_em") or 0) > 7200]
    for k in expiradas:
        _CONTROLE_TV_SALAS.pop(k, None)


@app.route("/controle", methods=["GET"])
@app.route("/controle.html", methods=["GET"])
def rota_controle_remoto_tv():
    """Serve o controle remoto mobile acionado pelo QR Code da TV."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controle.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Controle remoto em atualização", 404


@app.route("/api/controle/enviar", methods=["POST", "GET"])
def api_controle_enviar_nuvem():
    """Recebe comandos do celular e entrega em tempo real para a TV pareada."""
    dados = request.get_json(silent=True) or {}
    codigo = _normalizar_codigo_tv(dados.get("tv") or request.args.get("tv") or "")
    cmd = str(dados.get("cmd") or request.args.get("cmd") or "").strip()[:40]
    val = dados.get("val") if "val" in dados else request.args.get("val", "")
    if not codigo or not cmd:
        return jsonify({"ok": False, "erro": "Informe o código da TV e o comando."}), 400
    agora = time.time()
    with _CONTROLE_TV_LOCK:
        _limpar_salas_antigas()
        sala = _CONTROLE_TV_SALAS.setdefault(codigo, {"cmds": [], "status": {}, "atualizado_em": agora, "pareado_em": 0.0})
        sala["cmds"].append({"cmd": cmd, "val": "" if val is None else str(val)[:160], "ts": agora})
        if len(sala["cmds"]) > 30:
            sala["cmds"] = sala["cmds"][-30:]
        sala["pareado_em"] = agora
        sala["atualizado_em"] = agora
    return jsonify({"ok": True, "tv": codigo, "cmd": cmd}), 200


@app.route("/api/controle/ouvir", methods=["GET"])
def api_controle_ouvir_nuvem():
    """Retorna e consome os comandos enviados pelo celular para a TV informada."""
    codigo = _normalizar_codigo_tv(request.args.get("tv") or "")
    if not codigo:
        return jsonify({"ok": False, "comandos": [], "pareado": False}), 400
    agora = time.time()
    with _CONTROLE_TV_LOCK:
        _limpar_salas_antigas()
        sala = _CONTROLE_TV_SALAS.setdefault(codigo, {"cmds": [], "status": {}, "atualizado_em": agora, "pareado_em": 0.0})
        cmds = list(sala.get("cmds") or [])
        sala["cmds"] = []
        sala["atualizado_em"] = agora
        pareado = (agora - float(sala.get("pareado_em") or 0)) < 900
    return jsonify({"ok": True, "comandos": cmds, "pareado": pareado}), 200


@app.route("/api/controle/status", methods=["GET", "POST"])
def api_controle_status_nuvem():
    """Sincroniza qual canal está passando na TV para mostrar no controle do celular."""
    if request.method == "POST":
        dados = request.get_json(silent=True) or {}
        codigo = _normalizar_codigo_tv(dados.get("tv") or "")
        if not codigo:
            return jsonify({"ok": False}), 400
        agora = time.time()
        with _CONTROLE_TV_LOCK:
            sala = _CONTROLE_TV_SALAS.setdefault(codigo, {"cmds": [], "status": {}, "atualizado_em": agora, "pareado_em": 0.0})
            sala["status"] = {
                "canal_numero": dados.get("canal_numero") or "",
                "canal_nome": str(dados.get("canal_nome") or "")[:90],
                "epg_atual": str(dados.get("epg_atual") or "")[:120],
                "epg_proximo": str(dados.get("epg_proximo") or "")[:120],
            }
            sala["atualizado_em"] = agora
        return jsonify({"ok": True}), 200

    codigo = _normalizar_codigo_tv(request.args.get("tv") or "")
    if not codigo:
        return jsonify({"ok": False, "canal_nome": "Aguardando código da TV..."}), 400
    with _CONTROLE_TV_LOCK:
        sala = _CONTROLE_TV_SALAS.get(codigo) or {}
        st = dict(sala.get("status") or {})
        st["ok"] = True
        st["tv"] = codigo
        st["pareado"] = bool(sala.get("pareado_em"))
    return jsonify(st), 200


@app.route("/auditor", methods=["GET"])
def rota_painel_auditor_ao_vivo():
    """Serve o Quadro ao Vivo do Auditor dos 3 Agentes + Latência & Conexão."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auditor_ao_vivo.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Painel do Auditor em atualização", 404


@app.route("/api/auditor/ping", methods=["GET"])
def api_auditor_ping():
    """Responde instantaneamente para o navegador medir a latência da própria conexão."""
    resp = jsonify({
        "ok": True,
        "servidor": "online",
        "horario": agora_brasilia().strftime("%H:%M:%S.%f")[:-3]
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp, 200


@app.route("/api/auditor/status", methods=["GET"])
def api_auditor_status():
    """Retorna o relatório mais recente do Auditor e do quadro de conexão."""
    if _ESTADO_AUDITOR.get("ultima_auditoria") is None:
        return jsonify(executar_auditoria_3_agentes(forcar_rede=True)), 200
    snap = dict(_ESTADO_AUDITOR["ultima_auditoria"])
    snap["rede"] = obter_diagnostico_conexao_rapido()
    snap["ultimos_eventos"] = _ESTADO_AUDITOR["ultimos_eventos"]
    ag_snap = dict(snap.get("agentes") or {})
    for nome_ag in ["Camila", "Lucas", "Marcos"]:
        if nome_ag in ag_snap:
            ag_snap[nome_ag] = {**ag_snap[nome_ag], **_ESTADO_AUDITOR["agentes"][nome_ag]}
    snap["agentes"] = ag_snap
    return jsonify(snap), 200


@app.route("/api/auditor/executar", methods=["POST", "GET"])
def api_auditor_executar():
    """Executa agora auditoria ao vivo dos 3 agentes, MongoDB e streams."""
    relatorio = executar_auditoria_3_agentes(forcar_rede=True)
    return jsonify(relatorio), 200


# ==============================================================================
# BANCO DE DADOS DE CUSTOS, PONTO DE EQUILÍBRIO & PLANO DE ESCALA (/escala)
# ==============================================================================

CUSTOS_PADRAO_ECOSSISTEMA = [
    {
        "codigo": "NET_FIXA",
        "nome": "Internet Fixa",
        "categoria": "Fixo Pessoal",
        "tipo": "FIXO",
        "valor_atual": 70.0,
        "valor_escala": 70.0,
        "fixo_sistema": True,
        "observacao": "Informado por você (R$ 70,00/mês)"
    },
    {
        "codigo": "CEL_MOVEL",
        "nome": "Telefone Móvel (WhatsApp)",
        "categoria": "Fixo Pessoal",
        "tipo": "FIXO",
        "valor_atual": 43.0,
        "valor_escala": 43.0,
        "fixo_sistema": True,
        "observacao": "Uso direto no aparelho celular (R$ 43,00/mês)"
    },
    {
        "codigo": "ANTIGRAVITY_PLUS",
        "nome": "Assinatura Antigravity (Plus)",
        "categoria": "Ferramentas IA",
        "tipo": "FIXO",
        "valor_atual": 100.0,
        "valor_escala": 100.0,
        "fixo_sistema": True,
        "observacao": "Criação/manutenção (zero custo de IA por mensagem dos clientes)"
    },
    {
        "codigo": "RENDER_WEB",
        "nome": "Render Web Service",
        "categoria": "Infraestrutura Nuvem",
        "tipo": "FIXO",
        "valor_atual": 0.0,
        "valor_escala": 39.0,
        "fixo_sistema": True,
        "observacao": "Free hoje -> Starter US$ 7 (~R$ 39) sempre ligado + 8 threads"
    },
    {
        "codigo": "CLOUDFLARE_PROXY",
        "nome": "Cloudflare Workers Proxy",
        "categoria": "Infraestrutura Nuvem",
        "tipo": "FIXO",
        "valor_atual": 0.0,
        "valor_escala": 28.0,
        "fixo_sistema": True,
        "observacao": "Free 100k req/dia hoje -> Paid US$ 5 (~R$ 28) 10M req/mês"
    },
    {
        "codigo": "MONGO_ATLAS",
        "nome": "MongoDB Atlas (Banco de Dados)",
        "categoria": "Infraestrutura Nuvem",
        "tipo": "FIXO",
        "valor_atual": 0.0,
        "valor_escala": 56.0,
        "fixo_sistema": True,
        "observacao": "M0 Free 512MB hoje -> Flex a partir de US$ 8-10 (~R$ 56)"
    },
    {
        "codigo": "VPS_WHATSAPP",
        "nome": "VPS WhatsApp 24h Sem PC",
        "categoria": "Infraestrutura Nuvem",
        "tipo": "FIXO",
        "valor_atual": 0.0,
        "valor_escala": 50.0,
        "fixo_sistema": True,
        "observacao": "Opcional para deixar WhatsApp automático ligado sem PC"
    },
    {
        "codigo": "LISTA_PAGA_VIP",
        "nome": "Lista Paga VIP (Fornecedor por Cliente)",
        "categoria": "Lista & Conteúdo",
        "tipo": "VARIAVEL_CLIENTE",
        "valor_atual": 0.0,
        "valor_escala": 7.0,
        "fixo_sistema": True,
        "observacao": "Custo unitário mensal por cliente VIP pago (edite com seu valor real)"
    },
]

METAS_ESCALA_PADRAO = [
    {
        "fase": 1,
        "codigo": "FASE_1",
        "titulo": "Fase 1 • Pagar Contas Fixas (Equilíbrio)",
        "alvo_clientes": 9,
        "nuvem_extra": 0.0,
        "descricao": "Cobrir 100% dos R$ 213,00 atuais (Internet + Celular + Antigravity Plus)."
    },
    {
        "fase": 2,
        "codigo": "FASE_2",
        "titulo": "Fase 2 • Caixa para Destravar Teto de 40",
        "alvo_clientes": 40,
        "nuvem_extra": 67.0,
        "descricao": "Separar R$ 67/mês do próprio lucro para Render Starter + Cloudflare Paid e quebrar o limite de 40 pessoas."
    },
    {
        "fase": 3,
        "codigo": "FASE_3",
        "titulo": "Fase 3 • Operação 24h Independente de PC",
        "alvo_clientes": 150,
        "nuvem_extra": 173.0,
        "descricao": "Adicionar MongoDB Flex + VPS para WhatsApp automático 24h (receita bruta R$ 3.750/mês a ticket R$ 25)."
    },
    {
        "fase": 4,
        "codigo": "FASE_4",
        "titulo": "Fase 4 • Escala Profissional (500+ Clientes)",
        "alvo_clientes": 500,
        "nuvem_extra": 394.0,
        "descricao": "Render Standard 2GB RAM + Atlas Flex Teto + Workers + VPS (receita bruta R$ 12.500/mês)."
    },
]


def _garantir_seeds_escala():
    """Garante custos e metas iniciais no MongoDB Atlas sem sobrescrever edições do Jonas."""
    if col_custos_escala is not None and col_custos_escala.count_documents({}) == 0:
        agora_str = agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
        col_custos_escala.insert_many([{**c, "atualizado_em": agora_str} for c in CUSTOS_PADRAO_ECOSSISTEMA])
    if col_metas_escala is not None and col_metas_escala.count_documents({}) == 0:
        col_metas_escala.insert_many([dict(m) for m in METAS_ESCALA_PADRAO])


@app.route("/escala", methods=["GET"])
def rota_painel_escala_custos():
    """Serve o painel privado de Banco de Custos, Lucro Líquido e Plano de Escala."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plano_escala.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Painel de Escala em atualização", 404


@app.route("/api/escala/resumo", methods=["GET"])
def api_escala_resumo():
    """Retorna custos do MongoDB Atlas, assinantes ativos reais, ponto de equilíbrio e projeções de escala."""
    try:
        _garantir_seeds_escala()
        ticket_medio = max(5.0, float(request.args.get("ticket", 25.0)))
        custos = (
            list(col_custos_escala.find({}, {"_id": 0}))
            if col_custos_escala is not None
            else list(CUSTOS_PADRAO_ECOSSISTEMA)
        )
        metas = (
            list(col_metas_escala.find({}, {"_id": 0}).sort("fase", 1))
            if col_metas_escala is not None
            else list(METAS_ESCALA_PADRAO)
        )

        fixos = [c for c in custos if c.get("tipo") == "FIXO"]
        variaveis = [c for c in custos if c.get("tipo") != "FIXO"]
        custo_fixo_atual = round(sum(float(c.get("valor_atual") or 0.0) for c in fixos), 2)
        custo_fixo_escala = round(sum(float(c.get("valor_escala") or 0.0) for c in fixos), 2)
        custo_var_atual = round(sum(float(c.get("valor_atual") or 0.0) for c in variaveis), 2)
        custo_var_escala = round(sum(float(c.get("valor_escala") or 0.0) for c in variaveis), 2)

        agora_ms = int(datetime.utcnow().timestamp() * 1000)
        assinantes_ativos = 0
        testes_2h_ativos = 0
        if assinantes_col is not None:
            for doc in assinantes_col.find({"status": "ATIVO"}, {"_id": 0, "expira_ts": 1, "tipo_plano": 1}):
                exp = int(doc.get("expira_ts") or 0)
                if not exp or exp > agora_ms:
                    if doc.get("tipo_plano") == "TESTE_2H":
                        testes_2h_ativos += 1
                    else:
                        assinantes_ativos += 1

        receita_pagamentos_mes = 0.0
        mes_prefixo = agora_brasilia().strftime("%Y-%m")
        if eventos_email_col is not None:
            for ev in eventos_email_col.find({"tipo": "PAGAMENTO"}, {"_id": 0, "valor": 1, "data_dia": 1}):
                if str(ev.get("data_dia") or "").startswith(mes_prefixo):
                    receita_pagamentos_mes += float(ev.get("valor") or 0.0)

        margem_unitaria = max(1.0, round(ticket_medio - custo_var_atual, 2))
        ponto_eq_clientes = math.ceil(custo_fixo_atual / margem_unitaria) if custo_fixo_atual > 0 else 0
        ponto_eq_receita = round(ponto_eq_clientes * ticket_medio, 2)

        receita_recorrente_est = round(assinantes_ativos * ticket_medio, 2)
        lucro_estimado_atual = round(receita_recorrente_est - custo_fixo_atual - (assinantes_ativos * custo_var_atual), 2)

        cenarios = []
        for qtd in [9, 40, 100, 150, 250, 500, 1000]:
            nuvem_ref = 0.0 if qtd <= 40 else (67.0 if qtd <= 120 else (173.0 if qtd <= 250 else 394.0))
            base_fixa_ref = 213.0 + nuvem_ref
            bruto = round(qtd * ticket_medio, 2)
            lucro_propria = round(bruto - base_fixa_ref, 2)
            lucro_lista_paga = round(bruto - base_fixa_ref - (qtd * (custo_var_escala or 7.0)), 2)
            cenarios.append({
                "clientes": qtd,
                "nuvem_estimada": nuvem_ref,
                "custo_fixo_total": base_fixa_ref,
                "receita_bruta": bruto,
                "lucro_lista_propria": lucro_propria,
                "lucro_lista_paga": lucro_lista_paga,
            })

        return jsonify({
            "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
            "ticket_medio": ticket_medio,
            "custo_fixo_atual": custo_fixo_atual,
            "custo_fixo_escala": custo_fixo_escala,
            "custo_var_atual": custo_var_atual,
            "custo_var_escala": custo_var_escala,
            "margem_unitaria": margem_unitaria,
            "ponto_equilibrio_clientes": ponto_eq_clientes,
            "ponto_equilibrio_receita": ponto_eq_receita,
            "assinantes_ativos": assinantes_ativos,
            "testes_2h_ativos": testes_2h_ativos,
            "receita_pagamentos_mes": round(receita_pagamentos_mes, 2),
            "receita_recorrente_est": receita_recorrente_est,
            "lucro_estimado_atual": lucro_estimado_atual,
            "custos": custos,
            "metas": metas,
            "cenarios": cenarios,
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/escala/custo", methods=["POST", "OPTIONS"])
def api_escala_salvar_custo():
    """Cria ou atualiza um custo operacional no banco MongoDB Atlas."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        if col_custos_escala is None:
            return jsonify({"erro": "Banco de dados indisponível."}), 503
        dados = request.get_json(silent=True) or {}
        nome = str(dados.get("nome") or "").strip()[:80]
        if not nome:
            return jsonify({"erro": "Nome do custo é obrigatório."}), 400
        codigo = re.sub(r"[^A-Z0-9_]", "_", str(dados.get("codigo") or nome).strip().upper())[:32]
        tipo = "VARIAVEL_CLIENTE" if dados.get("tipo") == "VARIAVEL_CLIENTE" else "FIXO"
        valor_atual = max(0.0, float(dados.get("valor_atual") or 0.0))
        valor_escala = max(0.0, float(dados.get("valor_escala") if dados.get("valor_escala") is not None else valor_atual))
        doc_atual = col_custos_escala.find_one({"codigo": codigo}) or {}
        doc = {
            "codigo": codigo,
            "nome": nome,
            "categoria": str(dados.get("categoria") or doc_atual.get("categoria") or "Operacional").strip()[:40],
            "tipo": tipo,
            "valor_atual": round(valor_atual, 2),
            "valor_escala": round(valor_escala, 2),
            "fixo_sistema": bool(doc_atual.get("fixo_sistema", False)),
            "observacao": str(dados.get("observacao") or doc_atual.get("observacao") or "").strip()[:140],
            "atualizado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
        }
        col_custos_escala.update_one({"codigo": codigo}, {"$set": doc}, upsert=True)
        return jsonify({"sucesso": True, "custo": doc}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/escala/custo/<codigo>", methods=["DELETE", "OPTIONS"])
def api_escala_remover_custo(codigo):
    """Remove um item de custo customizado do banco MongoDB Atlas."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        if col_custos_escala is None:
            return jsonify({"erro": "Banco de dados indisponível."}), 503
        cod = re.sub(r"[^A-Z0-9_]", "_", str(codigo or "").upper())
        existente = col_custos_escala.find_one({"codigo": cod})
        if not existente:
            return jsonify({"erro": "Custo não encontrado."}), 404
        if existente.get("fixo_sistema"):
            return jsonify({"erro": "Custos base do ecossistema não são excluídos — ajuste o valor para 0,00."}), 400
        col_custos_escala.delete_one({"codigo": cod})
        return jsonify({"sucesso": True}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/financeiro/metricas", methods=["GET"])
def api_financeiro_metricas():
    """Calcula investimento em estoque, custos fixos, faturamento e Ponto de Equilíbrio."""
    try:
        prods = list(col_produtos.find({}, {"_id": 0})) if col_produtos is not None else []
        valor_custo_estoque = sum(float(p.get("quantidade_estoque") or p.get("estoque_atual") or 0.0) * float(p.get("preco_custo") or (float(p.get("preco_venda", 0.0)) * 0.6)) for p in prods)
        valor_venda_estoque = sum(float(p.get("quantidade_estoque") or p.get("estoque_atual") or 0.0) * float(p.get("preco_venda") or 0.0) for p in prods)
        lucro_projetado_estoque = max(0.0, valor_venda_estoque - valor_custo_estoque)
        total_itens_estoque = sum(float(p.get("quantidade_estoque") or p.get("estoque_atual") or 0.0) for p in prods)

        custos = list(col_custos.find({}, {"_id": 0})) if col_custos is not None else []
        total_custos_fixos = sum(float(c.get("valor_mensal") or 0.0) for c in custos)

        vendas = list(col_vendas.find({}, {"_id": 0})) if col_vendas is not None else []
        mes_atual_str = agora_brasilia().strftime("/%m/%Y")
        vendas_mes = [v for v in vendas if mes_atual_str in str(v.get("data_hora", ""))]
        faturamento_mes = sum(float(v.get("total_liquido") or 0.0) for v in vendas_mes)
        faturamento_total_acumulado = sum(float(v.get("total_liquido") or 0.0) for v in vendas)
        qtd_vendas_mes = len(vendas_mes)
        ticket_medio = round(faturamento_mes / qtd_vendas_mes, 2) if qtd_vendas_mes > 0 else 0.0

        margem_contribuicao_pct = 40.0
        ponto_equilibrio_mensal = round(total_custos_fixos / (margem_contribuicao_pct / 100.0), 2) if total_custos_fixos > 0 else 0.0
        meta_diaria_break_even = round(ponto_equilibrio_mensal / 26.0, 2) if ponto_equilibrio_mensal > 0 else 0.0
        
        lucro_bruto_mes = faturamento_mes * (margem_contribuicao_pct / 100.0)
        lucro_liquido_real = round(lucro_bruto_mes - total_custos_fixos, 2)
        progresso_pct = min(100.0, round((faturamento_mes / ponto_equilibrio_mensal * 100.0), 1)) if ponto_equilibrio_mensal > 0 else 100.0

        return jsonify({
            "valor_investido_estoque": round(valor_custo_estoque, 2),
            "valor_venda_estoque": round(valor_venda_estoque, 2),
            "lucro_projetado_estoque": round(lucro_projetado_estoque, 2),
            "total_itens_estoque": int(total_itens_estoque),
            "total_custos_fixos": round(total_custos_fixos, 2),
            "faturamento_mes": round(faturamento_mes, 2),
            "faturamento_total_acumulado": round(faturamento_total_acumulado, 2),
            "qtd_vendas_mes": qtd_vendas_mes,
            "ticket_medio": ticket_medio,
            "margem_contribuicao_pct": margem_contribuicao_pct,
            "ponto_equilibrio_mensal": ponto_equilibrio_mensal,
            "meta_diaria_break_even": meta_diaria_break_even,
            "lucro_liquido_real": lucro_liquido_real,
            "progresso_break_even_pct": progresso_pct,
            "mes_referencia": agora_brasilia().strftime("%m/%Y")
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/financeiro/custos-fixos", methods=["GET", "POST"])
def api_financeiro_custos():
    try:
        if request.method == "POST":
            dados = request.json or {}
            categoria = dados.get("categoria", "Geral")
            descricao = dados.get("descricao", "Despesa Fixa").strip()
            valor = float(dados.get("valor_mensal", 0.0))
            vencimento = int(dados.get("vencimento_dia", 10))
            doc = {
                "categoria": categoria,
                "descricao": descricao,
                "valor_mensal": valor,
                "vencimento_dia": vencimento,
                "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
            }
            if col_custos is not None and descricao:
                col_custos.update_one({"descricao": descricao}, {"$set": doc}, upsert=True)
            return jsonify({"sucesso": True, "custo": doc}), 201

        custos = list(col_custos.find({}, {"_id": 0})) if col_custos is not None else []
        return jsonify(custos), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/financeiro/custos-fixos/<descricao>", methods=["DELETE"])
def api_financeiro_deletar_custo(descricao):
    try:
        if col_custos is not None:
            col_custos.delete_one({"descricao": descricao})
        return jsonify({"sucesso": True}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/clientes", methods=["GET", "POST"])
def api_crm_clientes():
    """Gerencia cadastro de clientes, limites de crédito e fiado seguro."""
    try:
        if request.method == "POST":
            dados = request.json or {}
            cpf_cnpj = dados.get("cpf_cnpj", "").strip()
            if not cpf_cnpj:
                return jsonify({"erro": "CPF ou CNPJ é obrigatório"}), 400
            doc = {
                "nome": dados.get("nome", "Cliente Sem Nome").strip(),
                "cpf_cnpj": cpf_cnpj,
                "whatsapp": dados.get("whatsapp", "").strip(),
                "endereco": dados.get("endereco", "").strip(),
                "limite_credito": float(dados.get("limite_credito", 1000.0)),
                "saldo_devedor": float(dados.get("saldo_devedor", 0.0)),
                "status": dados.get("status", "ATIVO"),
                "observacoes": dados.get("observacoes", "").strip(),
                "cadastrado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
            }
            if col_clientes is not None:
                col_clientes.update_one({"cpf_cnpj": cpf_cnpj}, {"$set": doc}, upsert=True)
            return jsonify({"sucesso": True, "cliente": doc}), 201

        busca = (request.args.get("busca") or "").strip()
        filtro = {}
        if busca:
            filtro = {"$or": [
                {"nome": {"$regex": busca, "$options": "i"}},
                {"cpf_cnpj": {"$regex": busca, "$options": "i"}},
                {"whatsapp": {"$regex": busca, "$options": "i"}}
            ]}
        clientes = list(col_clientes.find(filtro, {"_id": 0}).sort("nome", 1)) if col_clientes is not None else []
        return jsonify(clientes), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/clientes/movimentar-saldo", methods=["POST"])
def api_crm_movimentar_saldo():
    """Lança compra a prazo (fiado) ou registra recebimento de dívida."""
    try:
        dados = request.json or {}
        cpf_cnpj = (dados.get("cpf_cnpj") or "").strip()
        tipo = dados.get("tipo")
        valor = float(dados.get("valor", 0.0))
        if col_clientes is not None and cpf_cnpj:
            fator = valor if tipo == "debito" else -valor
            col_clientes.update_one({"cpf_cnpj": cpf_cnpj}, {"$inc": {"saldo_devedor": fator}})
            cliente_atual = col_clientes.find_one({"cpf_cnpj": cpf_cnpj}, {"_id": 0})
            return jsonify({"sucesso": True, "cliente": cliente_atual}), 200
        return jsonify({"erro": "Cliente não localizado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


STATUS_VEICULO_VALIDOS = {"DISPONIVEL", "ALUGADO", "MANUTENCAO"}
FORMAS_PAGAMENTO_VALIDAS = {"PIX", "DINHEIRO", "CARTAO_DEBITO", "CARTAO_CREDITO", "FIADO"}


def _obter_segredo_frotas():
    """Obtém segredo HMAC compartilhado entre processos sem senha fixa no código."""
    seg_env = os.getenv("FROTA_AUTH_SECRET", "").strip()
    if seg_env:
        return seg_env
    if config_col is not None:
        try:
            doc = config_col.find_one({"chave": "frota_hmac_segredo"})
            if doc and doc.get("valor"):
                return doc["valor"]
            novo = hashlib.sha256(os.urandom(32)).hexdigest()
            config_col.update_one(
                {"chave": "frota_hmac_segredo"},
                {"$set": {"valor": novo, "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")}},
                upsert=True
            )
            return novo
        except Exception:
            pass
    return hashlib.sha256(URI.encode("utf-8")).hexdigest()


def _obter_pin_hash_frotas():
    """Retorna (hash_sha256_pin, eh_pin_padrao) lendo de variável de ambiente ou Atlas."""
    pin_env = os.getenv("PIN_FROTAS", "").strip()
    if pin_env:
        return hashlib.sha256(pin_env.encode("utf-8")).hexdigest(), False
    if config_col is not None:
        try:
            doc = config_col.find_one({"chave": "pin_operador_frotas"})
            if doc and doc.get("pin_hash"):
                return doc["pin_hash"], bool(doc.get("pin_padrao", False))
            pin_inicial_hash = hashlib.sha256("2026".encode("utf-8")).hexdigest()
            config_col.update_one(
                {"chave": "pin_operador_frotas"},
                {"$set": {"pin_hash": pin_inicial_hash, "pin_padrao": True, "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")}},
                upsert=True
            )
            return pin_inicial_hash, True
        except Exception:
            pass
    return hashlib.sha256("2026".encode("utf-8")).hexdigest(), True


def _gerar_token_frotas(operador="Jonas Mendonça", validade_seg=43200):
    exp = int(time.time()) + validade_seg
    payload = f"{exp}|{operador}"
    segredo = _obter_segredo_frotas()
    assinatura = hmac.new(segredo.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{exp}|{operador}|{assinatura}"


def _validar_token_frotas(token):
    if not token or not isinstance(token, str):
        return False, None
    partes = token.split("|")
    if len(partes) != 3:
        return False, None
    exp_str, operador, assinatura = partes
    try:
        exp = int(exp_str)
    except ValueError:
        return False, None
    if exp < int(time.time()):
        return False, None
    segredo = _obter_segredo_frotas()
    esperada = hmac.new(segredo.encode("utf-8"), f"{exp}|{operador}".encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(assinatura, esperada):
        return True, operador
    return False, None


def _extrair_token_requisicao():
    tok = (request.headers.get("X-Frota-Token") or "").strip()
    if tok:
        return tok
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def exigir_auth_frotas(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({"status": "ok"}), 200
        ok, operador = _validar_token_frotas(_extrair_token_requisicao())
        if not ok:
            return jsonify({
                "erro": "Acesso restrito ao módulo de Frotas. Informe o PIN do operador para desbloquear.",
                "codigo": "AUTH_FROTAS_OBRIGATORIA"
            }), 401
        return fn(*args, **kwargs)
    return wrapper


def _validar_placa(placa_bruta):
    limpa = re.sub(r"[^A-Z0-9]", "", (placa_bruta or "").strip().upper())
    if not limpa:
        return None, "Placa é obrigatória."
    if not re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$", limpa):
        return None, "Formato de placa inválido. Use o padrão ABC1234 ou Mercosul BRA2E19."
    return limpa, None


def _parse_numero(valor, nome, minimo=0.0, maximo=None, inteiro=False):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, f"Campo '{nome}' é obrigatório."
    try:
        num = int(float(valor)) if inteiro else float(valor)
    except (ValueError, TypeError):
        return None, f"Campo '{nome}' deve ser numérico válido."
    if not math.isfinite(num):
        return None, f"Campo '{nome}' contém valor numérico inválido."
    if minimo is not None and num < minimo:
        return None, f"Campo '{nome}' não pode ser menor que {minimo}."
    if maximo is not None and num > maximo:
        return None, f"Campo '{nome}' não pode ser maior que {maximo}."
    return num, None


def _validar_data_br(data_str):
    texto = (data_str or "").strip()
    if not texto:
        return None, "Data de vigência é obrigatória (DD/MM/AAAA)."
    try:
        datetime.strptime(texto, "%d/%m/%Y")
        return texto, None
    except ValueError:
        return None, "Data inválida. Use o formato DD/MM/AAAA (ex: 31/12/2026)."


@app.route("/api/frotas/status-pin", methods=["GET", "OPTIONS"])
def api_frotas_status_pin():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    _, eh_padrao = _obter_pin_hash_frotas()
    ok, _ = _validar_token_frotas(_extrair_token_requisicao())
    return jsonify({"autenticado": ok, "pin_padrao": eh_padrao}), 200


@app.route("/api/frotas/autenticar", methods=["POST", "OPTIONS"])
def api_frotas_autenticar():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    dados = request.get_json(silent=True) or {}
    pin = str(dados.get("pin") or "").strip()
    if not pin:
        return jsonify({"erro": "Informe o PIN do operador."}), 400
    pin_hash_correto, eh_padrao = _obter_pin_hash_frotas()
    pin_informado_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(pin_informado_hash, pin_hash_correto):
        return jsonify({"erro": "PIN incorreto."}), 401
    token = _gerar_token_frotas("Jonas Mendonça")
    return jsonify({"sucesso": True, "token": token, "pin_padrao": eh_padrao}), 200


@app.route("/api/frotas/alterar-pin", methods=["POST", "OPTIONS"])
@exigir_auth_frotas
def api_frotas_alterar_pin():
    if os.getenv("PIN_FROTAS", "").strip():
        return jsonify({"erro": "O PIN está travado pela variável de ambiente PIN_FROTAS no servidor."}), 400
    dados = request.get_json(silent=True) or {}
    pin_atual = str(dados.get("pin_atual") or "").strip()
    novo_pin = str(dados.get("novo_pin") or "").strip()
    if len(novo_pin) < 4:
        return jsonify({"erro": "O novo PIN deve ter pelo menos 4 caracteres."}), 400
    pin_hash_correto, _ = _obter_pin_hash_frotas()
    if not hmac.compare_digest(hashlib.sha256(pin_atual.encode("utf-8")).hexdigest(), pin_hash_correto):
        return jsonify({"erro": "PIN atual não confere."}), 401
    if config_col is not None:
        novo_hash = hashlib.sha256(novo_pin.encode("utf-8")).hexdigest()
        config_col.update_one(
            {"chave": "pin_operador_frotas"},
            {"$set": {"pin_hash": novo_hash, "pin_padrao": False, "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")}},
            upsert=True
        )
    return jsonify({"sucesso": True, "mensagem": "PIN de segurança alterado com sucesso!"}), 200


@app.route("/api/frotas/veiculos", methods=["GET", "POST", "OPTIONS"])
@exigir_auth_frotas
def api_frotas_veiculos():
    """Gerencia veículos da locadora com validação estrita e telemetria."""
    try:
        if col_veiculos is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503

        if request.method == "POST":
            dados = request.get_json(silent=True) or {}
            placa, err = _validar_placa(dados.get("placa"))
            if err:
                return jsonify({"erro": err}), 400

            modelo = (dados.get("modelo") or "").strip()
            if not modelo:
                return jsonify({"erro": "Modelo do veículo é obrigatório."}), 400

            ano, err = _parse_numero(dados.get("ano", 2024), "ano", minimo=1980, maximo=2030, inteiro=True)
            if err:
                return jsonify({"erro": err}), 400

            km, err = _parse_numero(dados.get("km", 0.0), "km", minimo=0.0)
            if err:
                return jsonify({"erro": err}), 400

            diaria, err = _parse_numero(dados.get("diaria_valor", 150.0), "diaria_valor", minimo=0.01)
            if err:
                return jsonify({"erro": err}), 400

            status = (dados.get("status") or "DISPONIVEL").strip().upper()
            if status not in STATUS_VEICULO_VALIDOS:
                return jsonify({"erro": "Status inválido. Use DISPONIVEL, ALUGADO ou MANUTENCAO."}), 400

            existente = col_veiculos.find_one({"placa": placa})
            if existente and dados.get("modo") != "editar":
                return jsonify({"erro": f"Já existe um veículo cadastrado com a placa {placa}. Use Editar para atualizar."}), 409

            gps_in = dados.get("gps") if isinstance(dados.get("gps"), dict) else {}
            lat, err_lat = _parse_numero(gps_in.get("lat", -23.5505), "latitude", minimo=-90.0, maximo=90.0)
            lng, err_lng = _parse_numero(gps_in.get("lng", -46.6333), "longitude", minimo=-180.0, maximo=180.0)
            if err_lat or err_lng:
                return jsonify({"erro": err_lat or err_lng}), 400

            doc = {
                "placa": placa,
                "modelo": modelo,
                "ano": ano,
                "categoria": (dados.get("categoria") or "Passeio").strip() or "Passeio",
                "km": round(km, 1),
                "status": status,
                "diaria_valor": round(diaria, 2),
                "ignicao": bool(existente.get("ignicao", False)) if existente else bool(dados.get("ignicao", False)),
                "bloqueado": bool(existente.get("bloqueado", False)) if existente else bool(dados.get("bloqueado", False)),
                "rastreador_id": (dados.get("rastreador_id") or (existente.get("rastreador_id") if existente else f"SAT-{random.randint(1000, 9999)}")).strip().upper(),
                "gps": {
                    "lat": lat,
                    "lng": lng,
                    "endereco": (gps_in.get("endereco") or "São Paulo - SP (Pátio Central)").strip()
                },
                "atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
            }
            col_veiculos.update_one({"placa": placa}, {"$set": doc}, upsert=True)
            return jsonify({"sucesso": True, "veiculo": doc}), 201

        veiculos = list(col_veiculos.find({}, {"_id": 0}))
        return jsonify(veiculos), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/frotas/veiculos/<placa>", methods=["PUT", "DELETE", "OPTIONS"])
@exigir_auth_frotas
def api_frotas_veiculo_unico(placa):
    """Atualiza ou exclui um veículo específico pela placa."""
    try:
        if col_veiculos is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503
        placa_limpa, err = _validar_placa(placa)
        if err:
            return jsonify({"erro": err}), 400

        veiculo = col_veiculos.find_one({"placa": placa_limpa})
        if not veiculo:
            return jsonify({"erro": "Veículo não encontrado."}), 404

        if request.method == "DELETE":
            if veiculo.get("status") == "ALUGADO":
                return jsonify({"erro": "Não é possível excluir um veículo em locação ativa. Registre a devolução antes."}), 400
            col_veiculos.delete_one({"placa": placa_limpa})
            return jsonify({"sucesso": True, "mensagem": f"Veículo {placa_limpa} removido da frota."}), 200

        dados = request.get_json(silent=True) or {}
        atualizacoes = {"atualizado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")}

        if "modelo" in dados:
            modelo = (dados.get("modelo") or "").strip()
            if not modelo:
                return jsonify({"erro": "Modelo não pode ficar vazio."}), 400
            atualizacoes["modelo"] = modelo
        if "ano" in dados:
            ano, err = _parse_numero(dados.get("ano"), "ano", minimo=1980, maximo=2030, inteiro=True)
            if err:
                return jsonify({"erro": err}), 400
            atualizacoes["ano"] = ano
        if "categoria" in dados:
            atualizacoes["categoria"] = (dados.get("categoria") or "Passeio").strip() or "Passeio"
        if "km" in dados:
            km, err = _parse_numero(dados.get("km"), "km", minimo=0.0)
            if err:
                return jsonify({"erro": err}), 400
            atualizacoes["km"] = round(km, 1)
        if "diaria_valor" in dados:
            diaria, err = _parse_numero(dados.get("diaria_valor"), "diaria_valor", minimo=0.01)
            if err:
                return jsonify({"erro": err}), 400
            atualizacoes["diaria_valor"] = round(diaria, 2)
        if "rastreador_id" in dados:
            atualizacoes["rastreador_id"] = (dados.get("rastreador_id") or "").strip().upper()
        if "status" in dados:
            st = (dados.get("status") or "").strip().upper()
            if st not in STATUS_VEICULO_VALIDOS:
                return jsonify({"erro": "Status inválido. Use DISPONIVEL, ALUGADO ou MANUTENCAO."}), 400
            if veiculo.get("locacao_atual") and st != "ALUGADO":
                return jsonify({"erro": "Veículo possui locação ativa. Use o botão Devolver para encerrar a locação."}), 400
            atualizacoes["status"] = st
        if isinstance(dados.get("gps"), dict):
            gps_in = dados["gps"]
            lat, err_lat = _parse_numero(gps_in.get("lat", veiculo.get("gps", {}).get("lat", -23.5505)), "latitude", minimo=-90.0, maximo=90.0)
            lng, err_lng = _parse_numero(gps_in.get("lng", veiculo.get("gps", {}).get("lng", -46.6333)), "longitude", minimo=-180.0, maximo=180.0)
            if err_lat or err_lng:
                return jsonify({"erro": err_lat or err_lng}), 400
            atualizacoes["gps"] = {
                "lat": lat,
                "lng": lng,
                "endereco": (gps_in.get("endereco") or veiculo.get("gps", {}).get("endereco", "São Paulo - SP")).strip()
            }

        col_veiculos.update_one({"placa": placa_limpa}, {"$set": atualizacoes})
        veiculo_atualizado = col_veiculos.find_one({"placa": placa_limpa}, {"_id": 0})
        return jsonify({"sucesso": True, "veiculo": veiculo_atualizado}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/frotas/bloqueio", methods=["POST", "OPTIONS"])
@exigir_auth_frotas
def api_frotas_comando_bloqueio():
    """Envia comando simulado de bloqueio ou liberação sem ligar o motor sozinho."""
    try:
        if col_veiculos is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503
        dados = request.get_json(silent=True) or {}
        placa_bruta = (dados.get("placa") or "").strip().upper()
        if not placa_bruta:
            return jsonify({"erro": "Placa não informada"}), 400
        placa = re.sub(r"[^A-Z0-9]", "", placa_bruta)

        veiculo = col_veiculos.find_one({"placa": placa})
        if not veiculo:
            return jsonify({"erro": "Veículo não encontrado"}), 404

        novo_status_bloqueio = not bool(veiculo.get("bloqueado", False))
        # Bloquear corta ignição; desbloquear apenas libera a partida sem ligar o motor
        nova_ignicao = False if novo_status_bloqueio else bool(veiculo.get("ignicao", False))

        _, operador = _validar_token_frotas(_extrair_token_requisicao())
        comando_reg = {
            "tipo": "BLOQUEIO_REMOTO" if novo_status_bloqueio else "DESBLOQUEIO_REMOTO",
            "data_hora": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
            "operador": operador or "Jonas Mendonça",
            "status_telemetria": "COMANDO_REGISTRADO_SIMULADO"
        }

        col_veiculos.update_one(
            {"placa": placa},
            {
                "$set": {
                    "bloqueado": novo_status_bloqueio,
                    "ignicao": nova_ignicao,
                    "ultimo_comando": comando_reg,
                    "atualizado_em": comando_reg["data_hora"]
                },
                "$push": {
                    "historico_comandos": {"$each": [comando_reg], "$slice": -10}
                }
            }
        )
        msg_acao = (
            "BLOQUEADO (Ignição cortada no registro)"
            if novo_status_bloqueio
            else "DESBLOQUEADO (Partida liberada; ignição mantida desligada até uso da chave)"
        )
        return jsonify({
            "sucesso": True,
            "placa": placa,
            "bloqueado": novo_status_bloqueio,
            "ignicao": nova_ignicao,
            "ultimo_comando": comando_reg,
            "mensagem": f"Comando registrado! Veículo {placa} {msg_acao}."
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/frotas/locacao", methods=["POST", "OPTIONS"])
@exigir_auth_frotas
def api_frotas_locacao():
    """Registra aluguel ou devolução de veículo integrando caixa (PDV) e CRM (Fiado)."""
    try:
        if col_veiculos is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503
        dados = request.get_json(silent=True) or {}
        acao = (dados.get("acao") or "").strip().lower()
        placa, err = _validar_placa(dados.get("placa"))
        if err:
            return jsonify({"erro": err}), 400

        veiculo = col_veiculos.find_one({"placa": placa})
        if not veiculo:
            return jsonify({"erro": "Veículo não encontrado."}), 404

        agora_str = agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")

        if acao == "alugar":
            if veiculo.get("status") != "DISPONIVEL":
                return jsonify({"erro": f"Veículo {placa} não está disponível (status atual: {veiculo.get('status')})."}), 400
            if veiculo.get("bloqueado"):
                return jsonify({"erro": f"Veículo {placa} está bloqueado. Desbloqueie antes de liberar a locação."}), 400

            dias, err = _parse_numero(dados.get("dias", 1), "dias", minimo=1, maximo=365, inteiro=True)
            if err:
                return jsonify({"erro": err}), 400

            desconto, err = _parse_numero(dados.get("desconto_valor", 0.0), "desconto_valor", minimo=0.0)
            if err:
                return jsonify({"erro": err}), 400

            cliente_nome = (dados.get("cliente_nome") or "").strip()
            cliente_cpf = (dados.get("cliente_cpf") or "").strip()
            if not cliente_nome and cliente_cpf and col_clientes is not None:
                cli = col_clientes.find_one({"cpf_cnpj": cliente_cpf})
                if cli:
                    cliente_nome = cli.get("nome", "")
            if not cliente_nome:
                return jsonify({"erro": "Informe ou selecione o cliente da locação."}), 400

            forma_pgto = (dados.get("forma_pagamento") or "PIX").strip().upper()
            if forma_pgto not in FORMAS_PAGAMENTO_VALIDAS:
                return jsonify({"erro": "Forma de pagamento inválida."}), 400

            diaria = float(veiculo.get("diaria_valor") or 150.0)
            subtotal = round(dias * diaria, 2)
            if desconto > subtotal:
                return jsonify({"erro": "Desconto não pode ser maior que o subtotal da locação."}), 400
            total_liquido = round(subtotal - desconto, 2)

            if forma_pgto == "FIADO":
                if not cliente_cpf or col_clientes is None:
                    return jsonify({"erro": "Selecione um cliente cadastrado com CPF/CNPJ para lançar locação no Fiado."}), 400
                cli_doc = col_clientes.find_one({"cpf_cnpj": cliente_cpf})
                if not cli_doc:
                    return jsonify({"erro": "Cliente não encontrado no CRM para crédito Fiado."}), 404
                limite = float(cli_doc.get("limite_credito") or 0.0)
                saldo_atual = float(cli_doc.get("saldo_devedor") or 0.0)
                if saldo_atual + total_liquido > limite:
                    return jsonify({"erro": f"Limite de crédito insuficiente no CRM (Disponível: R$ {max(0.0, limite - saldo_atual):.2f})."}), 400
                col_clientes.update_one({"cpf_cnpj": cliente_cpf}, {"$inc": {"saldo_devedor": total_liquido}})

            cod_venda = f"LOC-{int(time.time())}"
            doc_venda = {
                "codigo_venda": cod_venda,
                "data_hora": agora_str,
                "cliente_nome": cliente_nome,
                "cliente_cpf": cliente_cpf,
                "subtotal_bruto": subtotal,
                "desconto_valor": desconto,
                "total_liquido": total_liquido,
                "forma_pagamento": forma_pgto,
                "valor_pago": total_liquido,
                "troco": 0.0,
                "origem": "LOCADORA_FROTAS",
                "itens": [{
                    "codigo_barras": f"LOC-{placa}",
                    "nome": f"Locação {veiculo.get('modelo')} ({placa}) - {dias} dia(s)",
                    "quantidade": dias,
                    "preco_unitario": diaria,
                    "subtotal": subtotal
                }],
                "status": "CONCLUIDA"
            }
            if col_vendas is not None:
                col_vendas.insert_one(doc_venda)

            data_prevista = (dados.get("data_prevista_retorno") or "").strip() or (agora_brasilia() + timedelta(days=dias)).strftime("%d/%m/%Y")
            locacao_info = {
                "codigo_locacao": cod_venda,
                "cliente_nome": cliente_nome,
                "cliente_cpf": cliente_cpf,
                "dias_contratados": dias,
                "diaria_valor": diaria,
                "total_contratado": total_liquido,
                "forma_pagamento": forma_pgto,
                "km_saida": float(veiculo.get("km") or 0.0),
                "data_saida": agora_str,
                "data_prevista_retorno": data_prevista,
                "observacoes": (dados.get("observacoes") or "").strip()
            }
            col_veiculos.update_one(
                {"placa": placa},
                {"$set": {"status": "ALUGADO", "locacao_atual": locacao_info, "atualizado_em": agora_str}}
            )

            registrar_evento_email(
                "LOCACAO_FROTA", cliente_nome, f"({cliente_cpf or 'S/Doc'})", total_liquido,
                f"Locação {placa} ({dias}d) - #{cod_venda}",
                f"Veículo {veiculo.get('modelo')} alugado via {forma_pgto}"
            )
            return jsonify({
                "sucesso": True,
                "mensagem": f"Locação #{cod_venda} iniciada para {cliente_nome}! Valor de R$ {total_liquido:.2f} lançado no Caixa/PDV.",
                "locacao": locacao_info
            }), 201

        if acao == "devolver":
            if veiculo.get("status") != "ALUGADO":
                return jsonify({"erro": f"Veículo {placa} não está marcado como ALUGADO."}), 400

            km_atual = float(veiculo.get("km") or 0.0)
            km_final, err = _parse_numero(dados.get("km_final", km_atual), "km_final", minimo=km_atual)
            if err:
                return jsonify({"erro": err}), 400

            diarias_extras, err = _parse_numero(dados.get("diarias_extras", 0), "diarias_extras", minimo=0, maximo=180, inteiro=True)
            if err:
                return jsonify({"erro": err}), 400

            taxa_extra, err = _parse_numero(dados.get("taxa_extra", 0.0), "taxa_extra", minimo=0.0)
            if err:
                return jsonify({"erro": err}), 400

            diaria = float(veiculo.get("diaria_valor") or 150.0)
            valor_extras = round((diarias_extras * diaria) + taxa_extra, 2)
            loc_atual = veiculo.get("locacao_atual") or {}
            cliente_nome = loc_atual.get("cliente_nome") or "Locatário"
            cliente_cpf = loc_atual.get("cliente_cpf") or ""

            cod_extra = None
            if valor_extras > 0:
                forma_extra = (dados.get("forma_pagamento_extra") or "PIX").strip().upper()
                if forma_extra not in FORMAS_PAGAMENTO_VALIDAS:
                    return jsonify({"erro": "Forma de pagamento do acerto extra inválida."}), 400
                if forma_extra == "FIADO":
                    if not cliente_cpf or col_clientes is None:
                        return jsonify({"erro": "Sem CPF/CNPJ vinculado na locação para lançar acerto extra no Fiado."}), 400
                    cli_doc = col_clientes.find_one({"cpf_cnpj": cliente_cpf})
                    if not cli_doc:
                        return jsonify({"erro": "Cliente não localizado no CRM."}), 404
                    limite = float(cli_doc.get("limite_credito") or 0.0)
                    saldo_atual = float(cli_doc.get("saldo_devedor") or 0.0)
                    if saldo_atual + valor_extras > limite:
                        return jsonify({"erro": f"Limite no CRM excedido para acerto extra (Disponível: R$ {max(0.0, limite - saldo_atual):.2f})."}), 400
                    col_clientes.update_one({"cpf_cnpj": cliente_cpf}, {"$inc": {"saldo_devedor": valor_extras}})

                cod_extra = f"DEV-{int(time.time())}"
                itens_extra = []
                if diarias_extras > 0:
                    itens_extra.append({
                        "codigo_barras": f"EXT-{placa}",
                        "nome": f"Diária(s) Extra(s) {placa} ({diarias_extras}d)",
                        "quantidade": diarias_extras,
                        "preco_unitario": diaria,
                        "subtotal": round(diarias_extras * diaria, 2)
                    })
                if taxa_extra > 0:
                    itens_extra.append({
                        "codigo_barras": f"TAX-{placa}",
                        "nome": f"Combustível / Taxa Devolução ({placa})",
                        "quantidade": 1,
                        "preco_unitario": taxa_extra,
                        "subtotal": round(taxa_extra, 2)
                    })
                if col_vendas is not None:
                    col_vendas.insert_one({
                        "codigo_venda": cod_extra,
                        "data_hora": agora_str,
                        "cliente_nome": cliente_nome,
                        "cliente_cpf": cliente_cpf,
                        "subtotal_bruto": valor_extras,
                        "desconto_valor": 0.0,
                        "total_liquido": valor_extras,
                        "forma_pagamento": forma_extra,
                        "valor_pago": valor_extras,
                        "troco": 0.0,
                        "origem": "LOCADORA_DEVOLUCAO",
                        "itens": itens_extra,
                        "status": "CONCLUIDA"
                    })

            km_rodado = round(km_final - km_atual, 1)
            col_veiculos.update_one(
                {"placa": placa},
                {
                    "$set": {
                        "status": "DISPONIVEL",
                        "km": round(km_final, 1),
                        "atualizado_em": agora_str,
                        "ultima_devolucao": {
                            "data_hora": agora_str,
                            "cliente_nome": cliente_nome,
                            "km_rodado": km_rodado,
                            "valor_extras": valor_extras,
                            "codigo_acerto": cod_extra
                        }
                    },
                    "$unset": {"locacao_atual": ""}
                }
            )
            return jsonify({
                "sucesso": True,
                "km_rodado": km_rodado,
                "valor_extras": valor_extras,
                "mensagem": f"Veículo {placa} devolvido ao pátio (+{km_rodado:.0f} km)." + (f" Acerto extra de R$ {valor_extras:.2f} lançado no Caixa." if valor_extras > 0 else "")
            }), 200

        return jsonify({"erro": "Ação inválida. Use 'alugar' ou 'devolver'."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/seguros/apolices", methods=["GET", "POST", "OPTIONS"])
@exigir_auth_frotas
def api_seguros_apolices():
    """Gerencia contratos de locação e apólices de seguro veicular com validação completa."""
    try:
        if col_apolices is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503

        if request.method == "POST":
            dados = request.get_json(silent=True) or {}
            placa, err = _validar_placa(dados.get("veiculo_placa"))
            if err:
                return jsonify({"erro": err}), 400

            if col_veiculos is not None and not col_veiculos.find_one({"placa": placa}):
                return jsonify({"erro": f"Veículo {placa} não encontrado na frota. Cadastre o carro primeiro."}), 404

            cliente_nome = (dados.get("cliente_nome") or "").strip()
            if not cliente_nome:
                return jsonify({"erro": "Nome do cliente segurado/locatário é obrigatório."}), 400

            franquia, err = _parse_numero(dados.get("franquia", 2000.0), "franquia", minimo=0.0)
            if err:
                return jsonify({"erro": err}), 400

            valor_mensal, err = _parse_numero(dados.get("valor_mensal"), "valor_mensal", minimo=0.01)
            if err:
                return jsonify({"erro": err}), 400

            vigencia_fim, err = _validar_data_br(dados.get("vigencia_fim"))
            if err:
                return jsonify({"erro": err}), 400

            num = re.sub(r"\s+", "", (dados.get("numero_apolice") or "").strip().upper()) or f"APOL-{agora_brasilia().strftime('%Y')}-{random.randint(1000, 9999)}"
            if col_apolices.find_one({"numero_apolice": num}) and dados.get("modo") != "editar":
                return jsonify({"erro": f"Já existe uma apólice com o número {num}."}), 409

            doc = {
                "numero_apolice": num,
                "veiculo_placa": placa,
                "cliente_nome": cliente_nome,
                "tipo": (dados.get("tipo") or "Locação com Seguro Total").strip(),
                "franquia": round(franquia, 2),
                "valor_mensal": round(valor_mensal, 2),
                "vigencia_fim": vigencia_fim,
                "seguradora": (dados.get("seguradora") or "Porto Seguro Corporativo").strip(),
                "status": (dados.get("status") or "ATIVA").strip().upper(),
                "cadastrado_em": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
            }
            col_apolices.update_one({"numero_apolice": num}, {"$set": doc}, upsert=True)
            return jsonify({"sucesso": True, "apolice": doc}), 201

        apolices = list(col_apolices.find({}, {"_id": 0}))
        return jsonify(apolices), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/seguros/apolices/<numero>", methods=["DELETE", "OPTIONS"])
@exigir_auth_frotas
def api_seguros_deletar_apolice(numero):
    try:
        if col_apolices is None:
            return jsonify({"erro": "Banco de dados temporariamente indisponível."}), 503
        num_limpo = (numero or "").strip().upper()
        res = col_apolices.delete_one({"numero_apolice": num_limpo})
        if res.deleted_count == 0:
            return jsonify({"erro": "Apólice não encontrada."}), 404
        return jsonify({"sucesso": True, "mensagem": f"Apólice {num_limpo} removida."}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ==============================================================================
# CHAT DE ATENDIMENTO PRÓPRIO 24H NA NUVEM (SEM PC LIGADO / SEM QR CODE)
# ==============================================================================

def _montar_extras_chat_web(baloes, novo_setor, extras):
    """Enriquece os balões do robô com QR Code PIX e atalhos visuais no chat web."""
    texto_junto = "\n".join(baloes or [])
    resultado = {}

    if CHAVE_PIX_OFICIAL in texto_junto:
        valor_pix = 30.0
        m_val = re.search(r"R\$\s*(\d+(?:[,\.]\d{2})?)", texto_junto)
        if m_val:
            try:
                valor_pix = float(m_val.group(1).replace(",", "."))
            except ValueError:
                valor_pix = 30.0
        payload_pix = gerar_payload_pix(CHAVE_PIX_OFICIAL, TITULAR_CONTA, CIDADE_RECEBEDOR, valor_pix)
        resultado["pix_card"] = {
            "chave_pix": CHAVE_PIX_OFICIAL,
            "titular": TITULAR_CONTA,
            "valor": valor_pix,
            "payload_copia_cola": payload_pix,
            "qrcode_url": gerar_url_qrcode_instantaneo(payload_pix, 240)
        }

    m_user = re.search(r"Usuário:\s*([^\s\n]+)", texto_junto)
    m_pass = re.search(r"Senha:\s*([^\s\n]+)", texto_junto)
    m_link = re.search(r"(https://agente-whatsapp-jonas\.onrender\.com/tv[^\s\n]*)", texto_junto)
    if m_link or (m_user and m_pass):
        resultado["acesso_tv"] = {
            "usuario": m_user.group(1) if m_user else "",
            "senha": m_pass.group(1) if m_pass else "",
            "link": m_link.group(1) if m_link else LINK_PLAYER_IPTV
        }

    if novo_setor in ["SETOR_4_JONAS_HUMANO", "PAGAMENTO_EM_ANALISE"] or extras.get("ignorado"):
        dig_whats = "".join(c for c in WHATSAPP_HUMANO if c.isdigit())
        resultado["link_humano"] = f"https://wa.me/55{dig_whats}?text=" + urllib.parse.quote("Olá, Jonas! Vim pelo Atendimento Online 24h.")

    return resultado


def _salvar_historico_chat_web(sessao_id, nome_user, msg_user, autor_bot, baloes_bot, extras_rich):
    """Salva turno do chat web no MongoDB Atlas para restaurar ao recarregar."""
    if col_chat_web is None or not sessao_id:
        return
    try:
        hora_str = agora_brasilia().strftime("%H:%M")
        ts = time.time()
        docs = [{
            "sessao_id": sessao_id,
            "origem": "user",
            "autor": nome_user or "Cliente Online",
            "texto": msg_user,
            "hora": hora_str,
            "ts": ts,
            "extras": {}
        }]
        for idx, b in enumerate(baloes_bot):
            eh_ultimo = (idx == len(baloes_bot) - 1)
            docs.append({
                "sessao_id": sessao_id,
                "origem": "bot",
                "autor": autor_bot or "Jonas Tech",
                "texto": b,
                "hora": hora_str,
                "ts": ts + (idx + 1) * 0.01,
                "extras": extras_rich if eh_ultimo else {}
            })
        col_chat_web.insert_many(docs)
    except Exception as e:
        print(f"[ERRO HISTORICO CHAT WEB]: {e}")


def _executar_turno_chat_web(sessao_id, nome, telefone_raw, mensagem_user, msg_exibicao_historico, tipo_midia="text", texto_comprovante=""):
    tel_digitos = "".join(c for c in str(telefone_raw or "") if c.isdigit())
    identificador = tel_digitos if len(tel_digitos) >= 10 else f"web_{sessao_id}"
    if len(tel_digitos) == 10 or len(tel_digitos) == 11:
        identificador = "55" + tel_digitos

    t0_web = time.perf_counter()
    novo_setor, atendente, baloes, extras = processar_mensagem_inteligente(
        identificador, nome, mensagem_user, midia_url=None, tipo_midia=tipo_midia, texto_comprovante=texto_comprovante, canal="web"
    )
    ms_web = (time.perf_counter() - t0_web) * 1000
    registrar_auditoria_agente(atendente, novo_setor, msg_exibicao_historico, ms_web, sucesso=True)

    if extras.get("ignorado"):
        atendente = "Equipe do Jonas"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        baloes = [
            "O atendimento automático geral está pausado momentaneamente, mas você pode chamar o Jonas diretamente no WhatsApp pelo botão abaixo!"
        ]
    elif extras.get("aguardando_humano") or not baloes:
        atendente = "Equipe do Jonas"
        novo_setor = "SETOR_4_JONAS_HUMANO"
        baloes = [
            "Seu recado já está na fila prioritária do Jonas! Você também pode falar com ele direto no WhatsApp abaixo ou digitar *menu* para voltar aos atendentes."
        ]

    if leads_col is not None:
        try:
            update_data = {
                "nome": nome,
                "setor_atual": novo_setor,
                "atendente_responsavel": atendente,
                "ultima_mensagem": msg_exibicao_historico,
                "resposta": "\n\n".join(baloes),
                "canal": "CHAT_WEB_NUVEM",
                "status": "EM_ATENDIMENTO_HUMANO",
                "atualizado_em": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S")
            }
            for k, v in extras.items():
                if k not in ["notificacao_jonas", "envio_extra_cliente"]:
                    update_data[k] = v
            leads_col.update_one({"telefone": identificador}, {"$set": update_data}, upsert=True)
        except Exception as e:
            print(f"[ERRO LEAD CHAT WEB]: {e}")

    extras_rich = _montar_extras_chat_web(baloes, novo_setor, extras)
    _salvar_historico_chat_web(sessao_id, nome, msg_exibicao_historico, atendente, baloes, extras_rich)

    return {
        "sucesso": True,
        "setor": novo_setor,
        "atendente": atendente,
        "baloes": baloes,
        "pix_card": extras_rich.get("pix_card"),
        "acesso_tv": extras_rich.get("acesso_tv"),
        "link_humano": extras_rich.get("link_humano")
    }


@app.route("/atendimento", methods=["GET"])
@app.route("/chat", methods=["GET"])
def rota_atendimento_web_nuvem():
    """Serve o Chat de Atendimento Online 24h direto do Render sem PC ligado."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atendimento_nuvem.html")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Atendimento Online em atualização", 404


@app.route("/api/atendimento/historico", methods=["GET"])
def api_atendimento_historico():
    sessao_id = (request.args.get("sessao_id") or "").strip()
    if not sessao_id or col_chat_web is None:
        return jsonify({"mensagens": []}), 200
    try:
        msgs = list(col_chat_web.find({"sessao_id": sessao_id}, {"_id": 0}).sort("ts", 1).limit(50))
        return jsonify({"mensagens": msgs}), 200
    except Exception as e:
        return jsonify({"mensagens": [], "erro": str(e)}), 500


@app.route("/api/atendimento/mensagem", methods=["POST", "OPTIONS"])
def api_atendimento_mensagem():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        dados = request.get_json(silent=True) or {}
        sessao_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(dados.get("sessao_id") or "").strip())[:64]
        mensagem = str(dados.get("mensagem") or "").strip()
        nome = str(dados.get("nome") or "Cliente Online").strip()[:60]
        telefone = str(dados.get("telefone") or "").strip()[:25]

        if not sessao_id:
            return jsonify({"erro": "Sessão inválida."}), 400
        if not mensagem:
            return jsonify({"erro": "Digite uma mensagem para enviar."}), 400

        resposta = _executar_turno_chat_web(sessao_id, nome, telefone, mensagem, mensagem, tipo_midia="text")
        return jsonify(resposta), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/atendimento/comprovante", methods=["POST", "OPTIONS"])
def api_atendimento_comprovante():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        if request.is_json:
            dados = request.get_json(silent=True) or {}
            sessao_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(dados.get("sessao_id") or "").strip())[:64]
            nome = str(dados.get("nome") or "Cliente Online").strip()[:60]
            telefone = str(dados.get("telefone") or "").strip()[:25]
            texto_comp = str(dados.get("texto_comprovante") or "").strip()
            nome_arq = ""
        else:
            sessao_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(request.form.get("sessao_id") or "").strip())[:64]
            nome = str(request.form.get("nome") or "Cliente Online").strip()[:60]
            telefone = str(request.form.get("telefone") or "").strip()[:25]
            texto_comp = str(request.form.get("texto_comprovante") or "").strip()
            arq = request.files.get("arquivo")
            nome_arq = arq.filename if arq else ""
            if arq:
                raw_bytes = arq.read(1024 * 1024 * 2)  # Limite seguro 2MB
                if nome_arq.lower().endswith(".txt"):
                    texto_comp = (texto_comp + "\n" + raw_bytes.decode("utf-8", errors="ignore")).strip()
                elif nome_arq.lower().endswith(".pdf"):
                    trechos = re.findall(rb"[A-Za-z0-9\s\.\,\-\:\/\$R]{5,}", raw_bytes)
                    extra_pdf = " ".join(t.decode("latin-1", errors="ignore") for t in trechos[:120])
                    texto_comp = (texto_comp + "\n" + extra_pdf[:1000]).strip()

        if not sessao_id:
            return jsonify({"erro": "Sessão inválida."}), 400
        if not texto_comp and not nome_arq:
            return jsonify({"erro": "Informe o texto do comprovante ou anexe um arquivo."}), 400

        resumo_usuario = f"📎 Comprovante: {nome_arq} {texto_comp[:120]}".strip()
        resposta = _executar_turno_chat_web(
            sessao_id,
            nome,
            telefone,
            texto_comp or "comprovante",
            resumo_usuario,
            tipo_midia="image",
            texto_comprovante=texto_comp
        )
        return jsonify(resposta), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


def inicializar_seeds_erp():
    """Popula dados iniciais de demonstração caso as novas coleções estejam vazias."""
    try:
        if col_custos is not None and col_custos.count_documents({}) == 0:
            col_custos.insert_many([
                {"categoria": "Espaço Físico", "descricao": "Aluguel Ponto Comercial", "valor_mensal": 1800.0, "vencimento_dia": 10},
                {"categoria": "Utilidades", "descricao": "Energia Elétrica Comercial", "valor_mensal": 380.0, "vencimento_dia": 15},
                {"categoria": "Comunicação", "descricao": "Internet Fibra + Telefonia", "valor_mensal": 160.0, "vencimento_dia": 5},
                {"categoria": "Pessoal", "descricao": "Pró-Labore & Equipe", "valor_mensal": 3200.0, "vencimento_dia": 5},
                {"categoria": "Sistemas", "descricao": "Sistemas de Nuvem & Gateway", "valor_mensal": 150.0, "vencimento_dia": 20}
            ])
            print("[NUVEM] Seed de custos fixos criado com sucesso!")

        if col_clientes is not None and col_clientes.count_documents({}) == 0:
            col_clientes.insert_many([
                {"nome": "Marcos Silveira Transporte ME", "cpf_cnpj": "34.567.890/0001-12", "whatsapp": "11987654321", "endereco": "Av. Paulista, 1000 - SP", "limite_credito": 5000.0, "saldo_devedor": 450.0, "status": "ATIVO", "observacoes": "Cliente frotista, paga sempre dia 10", "cadastrado_em": "20/11/2026 10:00:00"},
                {"nome": "Camila Fernandes de Oliveira", "cpf_cnpj": "321.654.987-00", "whatsapp": "11976543210", "endereco": "Rua Augusta, 450 - SP", "limite_credito": 1200.0, "saldo_devedor": 0.0, "status": "ATIVO", "observacoes": "Cliente VIP de acessórios e CinePro TV", "cadastrado_em": "22/11/2026 14:30:00"},
                {"nome": "Carlos Eduardo Locações", "cpf_cnpj": "12.345.678/0001-90", "whatsapp": "11965432109", "endereco": "Av. Rebouças, 1200 - SP", "limite_credito": 10000.0, "saldo_devedor": 1200.0, "status": "ATIVO", "observacoes": "Contrato mensal de locação de 2 utilitários", "cadastrado_em": "25/11/2026 09:15:00"}
            ])
            print("[NUVEM] Seed de clientes CRM criado com sucesso!")

        if col_veiculos is not None and col_veiculos.count_documents({}) == 0:
            col_veiculos.insert_many([
                {"placa": "BRA2E19", "modelo": "Fiat Fiorino 1.4 Hard Working", "ano": 2024, "categoria": "Utilitário / Carga", "km": 34200.0, "status": "ALUGADO", "diaria_valor": 160.0, "ignicao": True, "bloqueado": False, "rastreador_id": "SAT-9842", "gps": {"lat": -23.5505, "lng": -46.6333, "endereco": "Marginal Tietê, km 14 - São Paulo/SP"}, "atualizado_em": "28/11/2026 08:00:00"},
                {"placa": "SKY4J88", "modelo": "Renault Master Chassi Baú", "ano": 2025, "categoria": "Caminhão Leve", "km": 18500.0, "status": "DISPONIVEL", "diaria_valor": 280.0, "ignicao": False, "bloqueado": False, "rastreador_id": "SAT-7711", "gps": {"lat": -23.5329, "lng": -46.6395, "endereco": "Pátio Central - Garagem Matriz SP"}, "atualizado_em": "28/11/2026 08:00:00"},
                {"placa": "JON9M26", "modelo": "Chevrolet Onix Plus Turbo", "ano": 2024, "categoria": "Passeio / Executivo", "km": 22100.0, "status": "ALUGADO", "diaria_valor": 140.0, "ignicao": True, "bloqueado": False, "rastreador_id": "SAT-4509", "gps": {"lat": -23.5868, "lng": -46.6828, "endereco": "Av. Brigadeiro Faria Lima, 2000 - SP"}, "atualizado_em": "28/11/2026 08:00:00"}
            ])
            print("[NUVEM] Seed de frota veicular criado com sucesso!")

        if col_apolices is not None and col_apolices.count_documents({}) == 0:
            col_apolices.insert_many([
                {"numero_apolice": "APOL-2026-0081", "veiculo_placa": "BRA2E19", "cliente_nome": "Marcos Silveira Transporte ME", "tipo": "Locação com Seguro Total + Rastreador", "franquia": 2500.0, "valor_mensal": 3200.0, "vigencia_fim": "15/12/2026", "seguradora": "Porto Seguro Corporativo", "status": "ATIVA", "cadastrado_em": "15/11/2026 11:00:00"},
                {"numero_apolice": "APOL-2026-0094", "veiculo_placa": "JON9M26", "cliente_nome": "Carlos Eduardo Locações", "tipo": "Seguro de Frota Contra Terceiros + Furto", "franquia": 1800.0, "valor_mensal": 2400.0, "vigencia_fim": "20/01/2027", "seguradora": "Tokio Marine Frotas", "status": "ATIVA", "cadastrado_em": "20/11/2026 15:40:00"}
            ])
            print("[NUVEM] Seed de apólices e seguros criado com sucesso!")
    except Exception as e:
        print(f"[ERRO AO INICIALIZAR SEEDS ERP] {e}")


# Executa seed de inicialização ERP e Banco de Custos/Escala
try:
    inicializar_seeds_erp()
    _garantir_seeds_escala()
except Exception:
    pass


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
