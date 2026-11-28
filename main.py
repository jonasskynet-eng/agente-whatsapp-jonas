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
import json
import os
import random
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
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
    assinantes_col = db["assinantes_cinepro"]
    comprovantes_col = db["comprovantes_validados"]
    eventos_email_col = db["eventos_relatorio_email"]
    vendas_pdv_col = db["historico_vendas"]
    print("[NUVEM] Conexão com MongoDB Atlas validada com sucesso!")
except Exception as e:
    print(f"[ERRO MONGODB NUVEM] {e}")
    leads_col = None
    alertas_col = None
    config_col = None
    assinantes_col = None
    comprovantes_col = None
    eventos_email_col = None
    vendas_pdv_col = None


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


def gerar_credenciais_cinepro(telefone, nome, valor_pago=30.0, resumo_comprovante=""):
    """Gera usuário único e senha de 6 dígitos e grava no MongoDB por 30 dias."""
    pnome_limpo = re.sub(r"[^a-z0-9]", "", normalizar_ascii(obter_primeiro_nome(nome)).lower())
    base_nome = pnome_limpo[:10] if pnome_limpo else "cliente"
    digitos_tel = "".join(c for c in str(telefone or "") if c.isdigit())
    ultimos4 = digitos_tel[-4:] if len(digitos_tel) >= 4 else str(random.randint(1000, 9999))
    usuario = f"{base_nome}{ultimos4}"
    senha = str(random.randint(100000, 999999))

    agora = agora_brasilia()
    expira_dt = agora + timedelta(days=30)
    expira_ts = int((datetime.utcnow() + timedelta(days=30)).timestamp() * 1000)

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

    return usuario, senha, expira_dt.strftime("%d/%m/%Y")


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


def analisar_comprovante_pix(texto_ocr, texto_msg, setor_atual):
    """Analisa texto extraído de imagem/PDF de comprovante PIX e evita reuso."""
    combinado = f"{texto_ocr or ''} {texto_msg or ''}".lower()
    combinado_ascii = normalizar_ascii(combinado)

    tem_titular_jonas = any(k in combinado_ascii for k in ["jonas", "mendonca", "324588e6"])
    tem_sinal_pix = any(k in combinado_ascii for k in [
        "pix", "comprovante", "transfer", "pagamento", "valor",
        "r$", "conclu", "realizado", "enviado", "mercado pago", "autentica"
    ])

    valor_detectado = 150.0 if setor_atual == "SETOR_3_COMERCIAL" else 30.0
    m_valor = re.search(r"(?:r\$\s*|\b)(350|250|150|30)(?:[,\.]00)?\b", combinado_ascii)
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
        "Aqui é da equipe do Jonas! Me conta, como posso te ajudar hoje? "
        "Você tá procurando o teste grátis da TV, nosso sistema de caixa e estoque ou precisa de ajuda técnica pro computador?"
    )
    return [abertura, corpo]


def diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante):
    """Retorna (baloes, notificacao_jonas) para o Lucas resolver problemas reais e registrar no relatório."""
    virgula_nome = f", {pnome}" if pnome else ""
    texto = (mensagem or "").strip().lower()
    notificacao = None

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

    if any(p in texto for p in ["travando", "engasgando", "oscilando", "carregando", "bolinha", "internet", "rede", "wifi", "wi-fi", "lenta", "rota", "dns"]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação de troca para Wi-Fi 5G / cabo e reinício de 30s no roteador para renovar DNS."
        )
        baloes = [
            f"Vamos resolver essa oscilação agora{virgula_nome}! Aqui é o Lucas, do suporte.",
            "Quase sempre que dá essas engasgadas à noite é rota congestionada da operadora ou interferência no Wi-Fi comum. Tenta conectar na rede 5G do seu roteador (ou cabo na TV) e tira o roteador da tomada por uns 30 segundos pra renovar o DNS.",
            "Me fala também: tá travando em todos os canais ou em um específico? E você tá assistindo na Smart TV, TV Box ou celular?"
        ]
        return baloes, notificacao

    if any(p in texto for p in ["canal", "canais", "fora do ar", "sem som", "mudo", "tela preta", "não abre", "nao abre", "0:00", "sumiu", "sinal"]):
        notificacao = f"🛠️ *CHAMADO DE CANAL/SINAL (LUCAS):*\n👤 {nome} ({telefone})\n💬 Relato: {(mensagem or '')[:160]}"
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação de desbloqueio de áudio/play (0:00), troca de canal para renovar sinal e alerta de grade enviado."
        )
        baloes = [
            f"Opa{virgula_nome}, Lucas aqui! Já tô verificando a grade pra você.",
            "Se a imagem abriu parada em 0:00 ou sem som, toca no botão de ativar o som no meio da tela que destrava na hora. Se foi só um canal que não entrou, muda pro canal vizinho e volta pra renovar o sinal.",
            "Qual é o nome ou número exato do canal que deu isso aí? Já deixei o Jonas avisado aqui na bancada pra checar a rota dele!"
        ]
        return baloes, notificacao

    if any(p in texto for p in ["samsung", "lg", "roku", "tv box", "box", "fire", "smart"]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Orientação de limpeza de cache da Smart TV / TV Box e reinício elétrico de 20 segundos."
        )
        baloes = [
            "Em Smart TV e TV Box, quando pesa a memória do aparelho, o segredo é limpar o cache do navegador nas configurações da TV e desligar ela da tomada por uns 20 segundos.",
            "Me diz a marca certinha do seu aparelho e o que apareceu na tela que te guio passo a passo!"
        ]
        return baloes, notificacao

    if any(p in texto for p in ["pc", "computador", "notebook", "windows", "formatar", "pdv", "caixa", "impressora", "leitor"]):
        registrar_evento_email(
            "SUPORTE_TECNICO", nome, telefone, 0.0,
            mensagem[:180],
            "Triagem técnica iniciada para Windows / Sistema PDV Caixa (impressora, leitor ou desempenho)."
        )
        baloes = [
            f"Tranquilo{virgula_nome}, vamos organizar isso! Aqui é o Lucas.",
            "Me conta só um detalhe pra eu separar a ferramenta certa: o problema é lentidão no Windows ou algum erro dentro do Sistema de Caixa (impressora, leitor ou banco)? Se aparecer mensagem na tela, pode mandar foto por aqui!"
        ]
        return baloes, notificacao

    registrar_evento_email(
        "SUPORTE_TECNICO", nome, telefone, 0.0,
        mensagem[:180],
        "Atendimento técnico inicial aberto pelo Lucas aguardando detalhes/foto do cliente."
    )
    baloes = [
        f"Fala{virgula_nome}! Tudo tranquilo? Aqui é o Lucas, cuido da parte técnica.",
        "Me conta o que tá acontecendo aí: é algum canal oscilando, configuração na TV ou algo no computador? Pode me explicar do seu jeito ou mandar foto da tela que já vejo pra você!"
    ]
    return baloes, notificacao


def gerar_resposta_fallback_inteligente(setor, pnome, mensagem_usuario):
    """
    Gera resposta humana e contextual quando o cliente envia mensagens
    que fogem do padrão das palavras-chave exatas, mantendo a persona de cada setor.
    """
    virgula_nome = f", {pnome}" if pnome else ""
    texto_limpo = normalizar_ascii((mensagem_usuario or "").lower())

    # Dúvidas de Aparelhos / Compatibilidade
    if any(k in texto_limpo for k in ["roku", "fire stick", "firestick", "smart", "samsung", "lg", "tcl", "celular", "iphone", "computador", "notebook", "tv box", "box", "aparelho"]):
        if setor == "SETOR_1_CINEPRO":
            return [
                f"Funciona sim com excelente qualidade{virgula_nome}! 📺",
                "O CinePro roda perfeitamente em Smart TVs (Samsung, LG, TCL, Android TV), TV Box, Fire Stick, celular e computador através de um aplicativo super leve.",
                "Quer que eu te mande o teste grátis de 2 horas agora pra você ver funcionando aí na sua tela?"
            ]
        else:
            return [
                f"Com certeza{virgula_nome}! Todos os nossos sistemas são otimizados pra rodar super leves sem travar a sua máquina.",
                "Você prefere conhecer o sistema PDV pra comércio ou os nossos planos de canais e filmes na TV?"
            ]

    # Dúvidas de Pagamento / Cartão / Parcelamento
    if any(k in texto_limpo for k in ["cartao", "credito", "debito", "parcel", "vezes", "boleto", "dinheiro"]):
        return [
            f"Trabalhamos preferencialmente com PIX{virgula_nome}, que ativa na hora com confirmação automática!",
            "Se você precisar de link de cartão ou parcelamento, eu anoto aqui e o Jonas te envia o link do Mercado Pago em seguida, tudo bem?\n\nQuer que eu já prepare a sua ativação?"
        ]

    # Dúvidas sobre Internet / Modo Offline
    if any(k in texto_limpo for k in ["sem internet", "caiu a net", "offline", "precisa de net"]):
        if setor == "SETOR_3_COMERCIAL":
            return [
                f"Essa é uma das maiores vantagens do nosso PDV{virgula_nome}:",
                "Ele roda direto no seu computador local! Se a internet cair, o seu caixa continua vendendo e registrando o estoque normalmente sem parar a sua loja. Quando a rede volta, ele sincroniza tudo.",
                "Quer que eu te mande a chave PIX de R$ 150 pra já liberar a sua licença vitalícia?"
            ]

    # Cumprimentos e gírias informais
    if any(k in texto_limpo for k in ["salve", "tranquilo", "beleza", "e ai", "fala ai", "opa tudo bem", "opa"]):
        return [
            f"Opa{virgula_nome}, tudo tranquilo por aqui e com você? 🚀",
            "Como posso te ajudar hoje? Temos o teste grátis da CinePro TV por 2 horas e também os nossos sistemas comerciais para comércio e suporte técnico!"
        ]

    # Fallback contextual por setor
    if setor == "SETOR_1_CINEPRO":
        return [
            f"Entendi perfeitamente o que você precisa{virgula_nome}! 😊",
            "Aqui no CinePro TV você tem mais de 4.000 canais abertos e fechados, além de todos os lançamentos de filmes e séries por apenas R$ 30 mensais, sem fidelidade.",
            "Posso já gerar o seu teste de 2 horas pra você experimentar sem pagar nada?"
        ]
    elif setor == "SETOR_2_SUPORTE":
        return [
            f"Compreendi o seu relato{virgula_nome}. Sou o Lucas do suporte técnico especializado.",
            "Para eu te orientar com precisão: o problema está acontecendo na conexão de rede (Wi-Fi), em algum canal específico ou no aplicativo da sua TV?"
        ]
    elif setor == "SETOR_3_COMERCIAL":
        return [
            f"Perfeito{virgula_nome}! Sou o Marcos do comercial da Jonas Tech.",
            "Nós desenvolvemos o Sistema PDV Frente de Caixa (pagamento único de R$ 150, sem mensalidades) e o Combo de Modernização completo.",
            "Me conta um pouco do seu comércio ou da sua ideia pra eu te indicar a melhor opção!"
        ]

    return obter_recepcao_natural(pnome)


def processar_mensagem_inteligente(telefone, nome, mensagem, midia_url=None, tipo_midia="text", texto_comprovante=""):
    texto = (mensagem or "").strip().lower()
    pnome = obter_primeiro_nome(nome)
    virgula_nome = f", {pnome}" if pnome else ""
    dados_extras = {}

    # 0. COMANDOS MESTRES DO JONAS PELO PRÓPRIO WHATSAPP
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
        usuario, senha, validade = gerar_credenciais_cinepro(tel_alvo, nome_alvo, 30.0, "Liberado manualmente pelo Jonas")
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
    dados_extras["origem"] = "VITRINE_COMERCIAL"

    # Áudio recebido do cliente: pede gentilmente por texto sem parecer robô
    if tipo_midia == "audio":
        return (
            setor_atual,
            "Atendimento Jonas Tech",
            [f"Oi{virgula_nome}! Tô na bancada aqui agora com barulho e não consigo ouvir áudio, consegue me mandar por escrito rapidinho por favor? 😊"],
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
        return (
            setor_atual,
            "Camila" if setor_atual != "SETOR_3_COMERCIAL" else "Marcos",
            [f"Show{virgula_nome}! Me manda aqui a foto ou o PDF do comprovante rapidinho pra eu confirmar a transferência em nome de {TITULAR_CONTA} e já liberar pra você na hora 😊"],
            dados_extras
        )

    if eh_midia_comprovante or tem_ocr_comprovante:
        analise = analisar_comprovante_pix(texto_comprovante, texto, setor_atual)
        if analise["ja_usado"]:
            dados_extras["notificacao_jonas"] = (
                f"⚠️ *ALERTA DE COMPROVANTE REPETIDO!*\n"
                f"👤 {nome} ({telefone}) enviou um comprovante já utilizado antes."
            )
            return (
                setor_atual,
                "Validação Financeira",
                [
                    f"Opa{virgula_nome}, esse comprovante já apareceu validado por aqui antes! 🤔",
                    "Se você acabou de fazer um pagamento novo, manda a foto ou PDF certinho da transferência de hoje que já confiro pra você!"
                ],
                dados_extras
            )

        if analise["aprovado_automatico"]:
            registrar_comprovante_usado(analise["chave_unica"], telefone, analise["valor"])
            disparar_alerta_cliente_quente(telefone, nome, f"PAGAMENTO PIX VALIDADO (R$ {analise['valor']:.2f})", analise["valor"])

            if setor_atual == "SETOR_3_COMERCIAL" or analise["valor"] >= 150:
                codigo_lic = f"JT-{random.randint(10000, 99999)}"
                registrar_evento_email(
                    "PAGAMENTO", nome, telefone, analise["valor"],
                    f"Comercial / Sistemas • Código {codigo_lic}",
                    "Pagamento confirmado automaticamente pelo Marcos."
                )
                dados_extras["status_pagamento"] = "APROVADO_AUTOMATICO"
                dados_extras["valor_pago"] = analise["valor"]
                dados_extras["notificacao_jonas"] = (
                    f"💼 *PAGAMENTO CONFIRMADO PELO MARCOS!*\n"
                    f"👤 Cliente: {nome} ({telefone})\n"
                    f"💵 Valor lido: R$ {analise['valor']:.2f}\n"
                    f"🔑 Código gerado: *{codigo_lic}*"
                )
                return (
                    "PAGAMENTO_RECEBIDO",
                    "Marcos",
                    [
                        f"Perfeito{virgula_nome}! Acabei de conferir seu comprovante aqui em nome de {TITULAR_CONTA}, pagamento confirmado certinho! Muito obrigado pela parceria 🤝",
                        f"Seu código de ativação comercial é {codigo_lic}. Já avisei o Jonas no celular dele agora mesmo pra te entregar os arquivos e acompanhar a sua instalação!"
                    ],
                    dados_extras
                )

            usuario, senha, validade = gerar_credenciais_cinepro(telefone, nome, analise["valor"], texto_comprovante)
            registrar_evento_email(
                "PAGAMENTO", nome, telefone, analise["valor"],
                f"Assinatura 30 Dias • Usuário {usuario}",
                "Comprovante validado pela Camila e login liberado."
            )
            dados_extras["status_pagamento"] = "APROVADO_AUTOMATICO"
            dados_extras["usuario_cinepro"] = usuario
            dados_extras["notificacao_jonas"] = (
                f"💰 *PAGAMENTO CONFIRMADO PELA CAMILA!*\n"
                f"👤 Cliente: {nome} ({telefone})\n"
                f"💵 Valor lido: R$ {analise['valor']:.2f}\n"
                f"🔐 Acesso liberado até {validade}:\n"
                f"• Usuário: *{usuario}*\n"
                f"• Senha: *{senha}*"
            )
            return (
                "PAGAMENTO_RECEBIDO",
                "Camila",
                [
                    f"Oi{virgula_nome}! Acabei de conferir seu comprovante aqui em nome de {TITULAR_CONTA}, pagamento confirmado certinho! Muito obrigada pela confiança 😊",
                    f"Já deixei seu acesso completo liberado até {validade}! Anota seus dados pra entrar:\n\nUsuário: {usuario}\nSenha: {senha}\n\nLink direto: {LINK_PLAYER_IPTV}?u={usuario}&s={senha}",
                    "Tocando nesse link acima já entra liberado na hora! Se for abrir na TV ou em outro aparelho, é só clicar em Entrar lá no topo da tela e colocar esse usuário e senha, tá bom? Qualquer coisa me chama!"
                ],
                dados_extras
            )

        dados_extras["status_pagamento"] = "AGUARDANDO_CONFERENCIA_JONAS"
        dados_extras["notificacao_jonas"] = (
            f"⚠️ *COMPROVANTE PARA CONFERIR!*\n"
            f"👤 Cliente: {nome} ({telefone})\n"
            f"📄 Leitura parcial: {(texto_comprovante or 'imagem/PDF sem texto legível')[:120]}\n\n"
            f"👉 Caiu na conta? Responda aqui:\n*#liberar {telefone}*"
        )
        return (
            "PAGAMENTO_EM_ANALISE",
            "Camila" if setor_atual != "SETOR_3_COMERCIAL" else "Marcos",
            [
                f"Recebi seu arquivo aqui{virgula_nome}! 🙏",
                f"Como alguns dados da imagem não ficaram nítidos pra leitura automática, já encaminhei agora mesmo pro Jonas confirmar no {BANCO_RECEBEDOR} e te liberar o acesso em instantes!"
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

    # 4. TROCA INTELIGENTE DE ASSUNTO NO MEIO DA CONVERSA
    if any(p in texto for p in ["falar com jonas", "falar com o jonas", "chama o jonas", "atendente humano", "falar com humano"]):
        setor_atual = "MENU_INICIAL"
    elif setor_atual == "SETOR_1_CINEPRO" and any(p in texto for p in ["travando", "engasgando", "oscilando", "tela preta", "sem som", "fora do ar", "canal caiu", "suporte", "pdv", "sistema de caixa", "estoque", "150", "pc lento", "formatar"]):
        setor_atual = "MENU_INICIAL"

    # 5. ROTEAMENTO CONVERSACIONAL RESOLUTIVO
    if setor_atual == "MENU_INICIAL":
        if any(p in texto for p in ["2", "suporte", "tecnico", "técnico", "defeito", "erro", "formatar", "pc", "computador", "notebook", "lento", "windows", "ajuda", "conserto", "travando", "engasgando", "oscilando", "fora do ar", "tela preta", "sem som"]):
            novo_setor = "SETOR_2_SUPORTE"
            atendente = "Lucas"
            baloes, notif = diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante)
            if notif:
                dados_extras["notificacao_jonas"] = notif
        elif any(p in texto for p in ["1", "tv", "iptv", "cinepro", "teste", "testar", "futebol", "canais", "filme", "série", "serie", "jogo", "pacote vip"]):
            novo_setor = "SETOR_1_CINEPRO"
            atendente = "Camila"
            agora = agora_brasilia()
            dados_extras["teste_iniciado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_15min"] = (agora + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            dados_extras["horario_regua_expira"] = (agora + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            baloes = [
                f"Oi{virgula_nome}! Tudo bom? Aqui é a Camila 😊 Já deixei liberado seu teste grátis de 2 horas pra você ver a qualidade!",
                f"É só tocar nesse link aqui pra abrir:\n{LINK_PLAYER_IPTV}\n\nPega direto no celular, computador ou Smart TV, com filmes novos e jogos ao vivo. Abre aí rapidinho e me conta se rodou lisinho!"
            ]
        elif any(p in texto for p in ["3", "venda", "comercial", "comprar", "preco", "preço", "sistema", "pdv", "caixa", "estoque", "150", "quanto custa", "valor", "tabela", "robô", "robo", "mercadinho", "loja", "comercio", "comércio", "orçamento", "orcamento", "serviços", "servicos", "sistemas"]):
            novo_setor = "SETOR_3_COMERCIAL"
            atendente = "Marcos"
            baloes = [
                f"Opa{virgula_nome}! Tudo bem? Aqui é o Marcos, trabalho na parte comercial junto com o Jonas.",
                "Me conta rapidinho o que você tá buscando melhorar hoje pra eu te indicar o caminho certo: é sistema de caixa e estoque sem mensalidade pro seu comércio (R$ 150), deixar computador lento voando de novo ou colocar atendimento automático no WhatsApp?"
            ]
        elif any(p in texto for p in ["4", "jonas", "humano", "pessoa", "dono"]):
            novo_setor = "SETOR_4_JONAS_HUMANO"
            atendente = "Equipe do Jonas"
            dados_extras["avisou_aguardo_humano"] = False
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE SOLICITOU ATENDIMENTO HUMANO COM O JONAS")
            baloes = [
                f"Pode deixar{virgula_nome}! Já dei um toque no celular pessoal do Jonas pra ele assumir nossa conversa aqui.",
                "Se quiser, já pode ir mandando sua dúvida por escrito que assim que ele pegar no aparelho já te responde direto, combinado?"
            ]
        else:
            novo_setor = "MENU_INICIAL"
            atendente = "Recepção Jonas Tech"
            baloes = obter_recepcao_natural(pnome)

    elif setor_atual == "SETOR_1_CINEPRO":
        atendente = "Camila"
        novo_setor = "SETOR_1_CINEPRO"
        if any(p in texto for p in ["pix", "pagar", "comprar", "assinar", "quero fechar", "quero assinar", "ativar", "chave", "mensal", "quanto é", "quanto custa", "valor"]):
            disparar_alerta_cliente_quente(telefone, nome, "CLIENTE PEDIU PIX CINEPRO R$ 30", 30.0)
            baloes = montar_bloco_pix(pnome, "R$ 30,00 (acesso completo de 30 dias)")
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
        else:
            baloes = gerar_resposta_fallback_inteligente("SETOR_1_CINEPRO", pnome, mensagem)

    elif setor_atual == "SETOR_2_SUPORTE":
        atendente = "Lucas"
        novo_setor = "SETOR_2_SUPORTE"
        baloes, notif = diagnosticar_suporte_lucas(pnome, nome, telefone, mensagem, tipo_midia, texto_comprovante)
        if notif:
            dados_extras["notificacao_jonas"] = notif

    elif setor_atual == "SETOR_3_COMERCIAL":
        atendente = "Marcos"
        novo_setor = "SETOR_3_COMERCIAL"
        if any(p in texto for p in ["pix", "chave", "pagar", "comprar", "fechar", "manda a chave", "quero fechar", "vou querer"]):
            if any(k in texto for k in ["combo", "350"]):
                valor_num, valor_str = 350.0, "R$ 350,00 (Combo Modernização 3 em 1)"
            elif any(k in texto for k in ["250", "whatsapp", "robo", "robô", "atendimento"]):
                valor_num, valor_str = 250.0, "R$ 250,00 (Automação de WhatsApp)"
            else:
                valor_num, valor_str = 150.0, "R$ 150,00 (taxa única, sem mensalidade)"
            disparar_alerta_cliente_quente(telefone, nome, f"CLIENTE PEDIU PIX COMERCIAL {valor_str}", valor_num)
            baloes = montar_bloco_pix(pnome, valor_str)
        elif any(p in texto for p in ["loja", "mercado", "mercadinho", "adega", "bar", "lanchonete", "comercio", "comércio", "estoque", "caderno", "planilha", "caixa", "pdv"]):
            baloes = [
                f"Olha que economia boa dá pra fazer aí{virgula_nome}: quem sai do caderno ou de sistema com mensalidade pro nosso PDV Frente de Caixa economiza mais de R$ 1.200 no ano, porque você paga R$ 150 uma única vez e fica seu pra sempre!",
                "Ele já controla entrada e saída de estoque na hora, aceita leitor de código de barras e mostra o PIX na tela. E se o computador do balcão estiver lento, consigo juntar PDV + Otimização completa da máquina num pacote especial.\n\nPrefere fechar só o PDV de R$ 150 hoje ou quer ver a condição do pacote completo?"
            ]
        elif any(p in texto for p in ["combo", "pacote", "proposta", "melhoria", "desconto", "tudo", "completo"]):
            baloes = [
                f"Montei a nossa melhor proposta de modernização pra você{virgula_nome}:",
                "Fazendo separado sairia R$ 550 (PDV R$ 150 + Windows Boost PRO R$ 150 + Automação WhatsApp R$ 250). Fechando o Combo Modernização 3 em 1 hoje, consigo validar pra você por R$ 350 pagamento único — economia de R$ 200 na hora!",
                "Quer que eu já valide essa condição de R$ 350 e te mande a chave PIX oficial?"
            ]
        else:
            baloes = gerar_resposta_fallback_inteligente("SETOR_3_COMERCIAL", pnome, mensagem)

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
        return jsonify({"ok": False, "erro": "Seu período de 30 dias venceu. Renove no WhatsApp!"}), 403
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

    novo_setor, atendente, lista_baloes, extras = processar_mensagem_inteligente(
        telefone, nome, mensagem, midia_url, tipo_midia, texto_comprovante
    )
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


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
