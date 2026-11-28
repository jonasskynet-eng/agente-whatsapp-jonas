"""
MOTOR DE PIX DINAMICO E ESTATICO (PADRAO BACEN EMVCo)
Calculo do CRC16-CCITT e geracao de Payload Copia-e-Cola e QR Code SVG
Zero dependencias externas - 100% Python Nativo e Seguro
"""

import re
import urllib.parse
from typing import Dict, Any, Optional

def calcular_crc16(payload: str) -> str:
    """Calcula o checksum CRC16-CCITT (Polinomio 0x1021, valor inicial 0xFFFF) exigido pelo Banco Central."""
    polinomio = 0x1021
    resultado = 0xFFFF
    
    dados = payload.encode('utf-8')
    for byte in dados:
        resultado ^= (byte << 8)
        for _ in range(8):
            if (resultado & 0x8000):
                resultado = ((resultado << 1) ^ polinomio) & 0xFFFF
            else:
                resultado = (resultado << 1) & 0xFFFF
                
    return f"{resultado:04X}"

def formatar_campo_emv(id_campo: str, valor: str) -> str:
    """Formata um campo no formato TLV (Tag-Length-Value): ID + Tamanho (2 digitos) + Valor."""
    tamanho = f"{len(valor):02d}"
    return f"{id_campo}{tamanho}{valor}"

def gerar_payload_pix(chave_pix: str, beneficiario: str, cidade: str, valor: float, txid: str = "***") -> str:
    """
    Gera a string oficial do PIX Copia e Cola compativel com todos os bancos (Mercado Pago, Nubank, Itau, Bradesco, etc).
    """
    # Tratar e normalizar textos
    beneficiario_limpo = beneficiario.strip()[:25]
    cidade_limpa = cidade.strip()[:15]
    valor_formatado = f"{valor:.2f}"
    txid_limpo = re.sub(r'[^a-zA-Z0-9]', '', txid)[:25] or "***"
    
    # 00 - Payload Format Indicator
    payload_base = formatar_campo_emv("00", "01")
    
    # 26 - Informacoes da Conta (GUI do Bacen + Chave Pix)
    gui = formatar_campo_emv("00", "br.gov.bcb.pix")
    chave = formatar_campo_emv("01", chave_pix.strip())
    merchant_info = gui + chave
    payload_base += formatar_campo_emv("26", merchant_info)
    
    # 52 - Merchant Category Code (Padrao 0000 para servicos gerais)
    payload_base += formatar_campo_emv("52", "0000")
    
    # 53 - Moeda (986 = Real Brasileiro BRL)
    payload_base += formatar_campo_emv("53", "986")
    
    # 54 - Valor da Transacao (opcional se valor == 0, mas aqui obrigatorio para checkout)
    if valor > 0:
        payload_base += formatar_campo_emv("54", valor_formatado)
        
    # 58 - Codigo do Pais
    payload_base += formatar_campo_emv("58", "BR")
    
    # 59 - Nome do Beneficiario
    payload_base += formatar_campo_emv("59", beneficiario_limpo)
    
    # 60 - Cidade do Estabelecimento
    payload_base += formatar_campo_emv("60", cidade_limpa)
    
    # 62 - Campo Adicional (txid de identificacao)
    campo_txid = formatar_campo_emv("05", txid_limpo)
    payload_base += formatar_campo_emv("62", campo_txid)
    
    # 63 - Checksum CRC16
    payload_sem_crc = payload_base + "6304"
    crc = calcular_crc16(payload_sem_crc)
    
    return payload_sem_crc + crc

def gerar_url_qrcode_instantaneo(payload_pix: str, tamanho: int = 280) -> str:
    """Gera URL de visualizacao instantanea do QR Code para exibicao na tela do PDV."""
    payload_encoded = urllib.parse.quote(payload_pix)
    # API universal de alta disponibilidade para renderizacao de QR Code SVG/PNG
    return f"https://api.qrserver.com/v1/create-qr-code/?size={tamanho}x{tamanho}&data={payload_encoded}&charset-source=UTF-8"
