# Agente Comercial de WhatsApp 24/7 (Custo Zero)
Desenvolvido por **Jonas Skynet • Jonas Tech Solutions**

Agente inteligente de WhatsApp para atendimento automático de clientes e fechamento de vendas de sistemas e serviços digitais.

## 🚀 Tecnologias Integradas
- **Python 3.11 + Flask + Gunicorn**: API REST e Webhook leve e performático.
- **Docker**: Empacotamento em contêiner pronto para nuvem.
- **MongoDB Atlas**: Banco de dados NoSQL na AWS (São Paulo) para armazenamento de leads e conversas.
- **GitHub**: Controle de versão e automação de deploy contínuo.

## 📦 Estrutura de Arquivos
- `main.py`: Servidor Webhook com lógica de classificação de intenção e resposta comercial.
- `Dockerfile`: Configuração de contêiner para deploy na nuvem.
- `requirements.txt`: Dependências do projeto.

## ⚙️ Variáveis de Ambiente
- `MONGO_USER`: Usuário do MongoDB Atlas
- `MONGO_PASS`: Senha do banco
- `MONGO_CLUSTER`: Endereço do cluster Atlas
- `PORT`: Porta de execução (Padrão: 8080)
