# Fornece Já — marketplace B2B (Flask + SQLite)

## Como rodar
    pip install -r requirements.txt
    python app.py
Abra http://localhost:5000 (no celular, use o IP do seu computador na mesma rede).

Contas de teste (senha 123456): fornecedor@demo.com e empresa@demo.com

## Estrutura
- app.py: API (login com senha em hash, sessão, produtos, favoritos, chat, pedidos, painel) e banco SQLite (fornece.db, criado sozinho)
- static/index.html + static/app.js: o app mobile, conversando com a API
- static/logo-*.png, static/icone.png: logos (fundo removido) feitos a partir das suas imagens

## Antes de publicar
Defina SECRET_KEY no ambiente, rode com gunicorn atrás de HTTPS e troque debug=True.
