"""Fornece Já — backend Flask + SQLite.  Rode: python app.py  (http://localhost:5000)"""
import os, sqlite3
from functools import wraps
from flask import Flask, g, jsonify, request, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "fornece.db")
app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, tipo TEXT NOT NULL CHECK(tipo IN('f','e')),
    empresa TEXT NOT NULL, cnpj TEXT, documento TEXT, documento_tipo TEXT NOT NULL DEFAULT 'cnpj',
    telefone TEXT, email TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, categoria TEXT, cidade TEXT);
CREATE TABLE IF NOT EXISTS produtos(id INTEGER PRIMARY KEY, fornecedor_id INTEGER NOT NULL REFERENCES users(id),
  nome TEXT NOT NULL, preco REAL NOT NULL, unidade TEXT DEFAULT 'un', qtd_min INTEGER DEFAULT 1, categoria TEXT,
  descricao TEXT, icone TEXT DEFAULT 'box', views INTEGER DEFAULT 0, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS favoritos(user_id INTEGER, produto_id INTEGER, PRIMARY KEY(user_id,produto_id));
CREATE TABLE IF NOT EXISTS mensagens(id INTEGER PRIMARY KEY, de_id INTEGER, para_id INTEGER, texto TEXT NOT NULL, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pedidos(id INTEGER PRIMARY KEY, produto_id INTEGER, empresario_id INTEGER, qtd INTEGER,
  status TEXT DEFAULT 'Em negociação', criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
"""
STATUS = ["Em negociação", "Aguardando envio", "Enviado", "Recusado"]


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d:
        d.close()


def q(sql, a=(), one=False):
    r = db().execute(sql, a).fetchall()
    r = [dict(x) for x in r]
    return (r[0] if r else None) if one else r


def run(sql, a=()):
    c = db().execute(sql, a)
    db().commit()
    return c.lastrowid


def init_db():
    c = sqlite3.connect(DB)
    cols = [r[1] for r in c.execute("PRAGMA table_info(produtos)")]
    if "emoji" in cols:  # banco da versão anterior (emojis): recria com o catálogo novo
        c.executescript("DROP TABLE produtos;DROP TABLE favoritos;DROP TABLE mensagens;DROP TABLE pedidos;DROP TABLE users;")
    c.executescript(SCHEMA)
    user_cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
    if "documento" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN documento TEXT")
    if "documento_tipo" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN documento_tipo TEXT NOT NULL DEFAULT 'cnpj'")
    c.execute("UPDATE users SET documento=cnpj WHERE documento IS NULL AND cnpj IS NOT NULL")
    c.commit()
    if not c.execute("SELECT 1 FROM users").fetchone():
        h = generate_password_hash("123456")
        us = [("f", "Distribuidora Campo Forte", "a@seed.local", "Alimentos", "Campinas, SP"), ("f", "Café do Vale", "b@seed.local", "Alimentos", "Poços de Caldas, MG"),
              ("f", "Limpa Mais Atacado", "c@seed.local", "Limpeza", "Curitiba, PR"), ("f", "Malha Sul Confecções", "d@seed.local", "Roupas", "Blumenau, SC"),
              ("f", "Volt Atacado", "e@seed.local", "Eletrônicos", "São Paulo, SP"),
              ("f", "Fornecedor Demo", "fornecedor@demo.com", "Alimentos", "São Paulo, SP"), ("e", "Empresa Demo", "empresa@demo.com", "Restaurante", "São Paulo, SP")]
        for t, n, e, cat, cid in us:
            c.execute("INSERT INTO users(tipo,empresa,email,senha,categoria,cidade) VALUES(?,?,?,?,?,?)", (t, n, e, h, cat, cid))
        ps = [(1, "Arroz Agulhinha Tipo 1 – 5 kg", 142.00, "fardo", 5, "Alimentos", "Fardo com 6 pacotes de 5 kg (30 kg). Grãos soltos, ideal para restaurantes e mercados.", "sack"),
              (1, "Feijão Carioca Tipo 1 – 1 kg", 58.00, "fardo", 10, "Alimentos", "Fardo com 10 pacotes de 1 kg. Safra recente, baixo índice de grãos quebrados.", "sack"),
              (1, "Óleo de Soja 900 ml", 128.00, "caixa", 3, "Alimentos", "Caixa com 20 garrafas de 900 ml. Refinado, validade mínima de 8 meses.", "droplet"),
              (2, "Café Torrado e Moído 500 g", 310.00, "caixa", 2, "Alimentos", "Caixa com 20 pacotes a vácuo de 500 g. Torra média, 100% arábica.", "coffee"),
              (1, "Milho Verde em Conserva 170 g", 62.00, "caixa", 4, "Alimentos", "Caixa com 24 latas de 170 g. Grãos selecionados, pronto para uso.", "can"),
              (3, "Detergente Líquido Neutro 500 ml", 54.00, "caixa", 5, "Limpeza", "Caixa com 24 frascos de 500 ml. Neutro, biodegradável.", "bottle"),
              (3, "Desinfetante Floral 5 L", 24.90, "galão", 12, "Limpeza", "Galão de 5 litros, concentrado. Rende até 1:10 de diluição.", "bottle"),
              (3, "Saco de Lixo 100 L Reforçado", 69.00, "pacote", 6, "Limpeza", "Pacote com 100 sacos pretos de 100 litros, resistente a 20 kg.", "bag"),
              (4, "Camiseta Algodão Penteado", 19.90, "peça", 30, "Roupas", "Malha 30.1 penteada, lisa, tamanhos P ao GG. Ótima para estampa.", "shirt"),
              (4, "Camisa Polo Uniforme", 38.00, "peça", 20, "Roupas", "Piquet com gola e punhos, cores sob consulta, bordado opcional.", "shirt"),
              (5, "Carregador USB-C 20 W", 14.50, "unidade", 50, "Eletrônicos", "Carregador de parede com carga rápida, bivolt, 1 ano de garantia.", "plug"),
              (5, "Lâmpada LED 9 W Bivolt", 215.00, "caixa", 2, "Eletrônicos", "Caixa com 50 lâmpadas E27, luz branca 6500 K, vida útil de 15 mil horas.", "bulb"),
              (5, "Pilha Alcalina AA", 96.00, "caixa", 2, "Eletrônicos", "Caixa com 48 pilhas AA, validade de 5 anos.", "battery")]
        c.executemany("INSERT INTO produtos(fornecedor_id,nome,preco,unidade,qtd_min,categoria,descricao,icone) VALUES(?,?,?,?,?,?,?,?)", ps)
        c.commit()
    c.close()


def auth(tipo=None):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session:
                return jsonify(erro="Faça login para continuar."), 401
            if tipo and session.get("tipo") != tipo:
                return jsonify(erro="Ação permitida apenas para " + ("fornecedores." if tipo == "f" else "empresários.")), 403
            return f(*a, **k)
        return w
    return deco


def body():
    return request.get_json(silent=True) or {}


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/register")
def register():
    d = body()
    emp, em, sn = (d.get("empresa") or "").strip(), (d.get("email") or "").strip().lower(), d.get("senha") or ""
    if d.get("tipo") not in ("f", "e") or not emp or "@" not in em:
        return jsonify(erro="Preencha seu nome ou nome da empresa e um e-mail válido."), 400
    if len(sn) < 6:
        return jsonify(erro="A senha precisa ter ao menos 6 caracteres."), 400
    if q("SELECT 1 FROM users WHERE email=?", (em,), one=True):
        return jsonify(erro="Este e-mail já está cadastrado."), 409
    documento_tipo = d.get("documento_tipo", "cnpj")
    documento = "".join(ch for ch in str(d.get("documento") or d.get("cnpj") or "") if ch.isdigit())
    if d["tipo"] == "e":
        tamanho = {"cpf": 11, "cnpj": 14}.get(documento_tipo)
        if tamanho is None or len(documento) != tamanho:
            return jsonify(erro=f"Informe um {'CPF' if documento_tipo == 'cpf' else 'CNPJ'} válido."), 400
    else:
        documento_tipo = "cnpj"
        documento = "".join(ch for ch in str(d.get("cnpj") or "") if ch.isdigit())
    uid = run("INSERT INTO users(tipo,empresa,cnpj,documento,documento_tipo,telefone,email,senha,categoria,cidade) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (d["tipo"], emp, documento if documento_tipo == "cnpj" else None, documento or None, documento_tipo,
               d.get("telefone"), em, generate_password_hash(sn), d.get("categoria"), d.get("cidade")))
    session.update(uid=uid, tipo=d["tipo"])
    return jsonify(id=uid, tipo=d["tipo"], empresa=emp)


@app.post("/api/login")
def login():
    d = body()
    u = q("SELECT * FROM users WHERE email=?", ((d.get("email") or "").strip().lower(),), one=True)
    if not u or not check_password_hash(u["senha"], d.get("senha") or ""):
        return jsonify(erro="E-mail ou senha incorretos."), 401
    session.update(uid=u["id"], tipo=u["tipo"])
    return jsonify(id=u["id"], tipo=u["tipo"], empresa=u["empresa"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if "uid" not in session:
        return jsonify(None)
    return jsonify(q("SELECT id,tipo,empresa,email,categoria FROM users WHERE id=?", (session["uid"],), one=True))


PSQL = """SELECT p.*,u.empresa AS fornecedor,u.cidade,
  (SELECT COUNT(*) FROM favoritos f WHERE f.produto_id=p.id AND f.user_id=?) AS fav FROM produtos p JOIN users u ON u.id=p.fornecedor_id"""


@app.get("/api/produtos")
@auth()
def produtos():
    cat, t = request.args.get("cat", "Todos"), "%" + request.args.get("q", "") + "%"
    sql, a = PSQL + " WHERE (p.nome LIKE ? OR u.empresa LIKE ? OR IFNULL(u.cidade,'') LIKE ?)", [session["uid"], t, t, t]
    if cat != "Todos":
        sql += " AND p.categoria=?"; a.append(cat)
    if request.args.get("meus"):
        sql += " AND p.fornecedor_id=?"; a.append(session["uid"])
    return jsonify(q(sql + " ORDER BY p.id DESC", a))


@app.get("/api/produtos/<int:i>")
@auth()
def produto(i):
    run("UPDATE produtos SET views=views+1 WHERE id=?", (i,))
    p = q(PSQL + " WHERE p.id=?", (session["uid"], i), one=True)
    return (jsonify(p), 200) if p else (jsonify(erro="Produto não encontrado."), 404)


@app.post("/api/produtos")
@auth("f")
def novo_produto():
    d = body()
    try:
        preco = float(str(d.get("preco")).replace(",", "."))
    except ValueError:
        preco = 0
    if not (d.get("nome") or "").strip() or preco <= 0:
        return jsonify(erro="Informe o nome e um preço maior que zero."), 400
    icone = {"Alimentos": "sack", "Roupas": "shirt", "Limpeza": "bottle", "Eletrônicos": "plug"}.get(d.get("categoria"), "box")
    i = run("INSERT INTO produtos(fornecedor_id,nome,preco,unidade,qtd_min,categoria,descricao,icone) VALUES(?,?,?,?,?,?,?,?)",
            (session["uid"], d["nome"].strip(), preco, d.get("unidade") or "unidade", int(d.get("qtd_min") or 1), d.get("categoria"), d.get("descricao") or "Sem descrição.", icone))
    return jsonify(id=i)


@app.post("/api/favoritos/<int:i>")
@auth()
def favoritar(i):
    k = (session["uid"], i)
    if q("SELECT 1 FROM favoritos WHERE user_id=? AND produto_id=?", k, one=True):
        run("DELETE FROM favoritos WHERE user_id=? AND produto_id=?", k); return jsonify(fav=0)
    run("INSERT INTO favoritos VALUES(?,?)", k); return jsonify(fav=1)


@app.get("/api/favoritos")
@auth()
def favoritos():
    return jsonify(q(PSQL + " WHERE p.id IN(SELECT produto_id FROM favoritos WHERE user_id=?)", (session["uid"], session["uid"])))


@app.get("/api/conversas")
@auth()
def conversas():
    u = session["uid"]
    return jsonify(q("""SELECT u.id,u.empresa,m.texto,m.criado_em FROM users u JOIN mensagens m ON m.id=(SELECT MAX(id) FROM mensagens
      WHERE (de_id=? AND para_id=u.id) OR (para_id=? AND de_id=u.id)) ORDER BY m.id DESC""", (u, u)))


@app.get("/api/conversa/<int:o>")
@auth()
def conversa(o):
    u = session["uid"]
    return jsonify(dict(com=q("SELECT id,empresa FROM users WHERE id=?", (o,), one=True), msgs=q(
        "SELECT de_id,texto,substr(criado_em,12,5) AS hora FROM mensagens WHERE (de_id=? AND para_id=?) OR (de_id=? AND para_id=?) ORDER BY id", (u, o, o, u))))


@app.post("/api/mensagens")
@auth()
def enviar():
    d = body()
    p, t = int(d.get("para") or 0), (d.get("texto") or "").strip()
    dest = q("SELECT email FROM users WHERE id=?", (p,), one=True)
    if not dest or not t or p == session["uid"]:
        return jsonify(erro="Mensagem inválida."), 400
    run("INSERT INTO mensagens(de_id,para_id,texto) VALUES(?,?,?)", (session["uid"], p, t))
    if dest["email"].endswith("@seed.local"):  # fornecedores de exemplo respondem sozinhos
        run("INSERT INTO mensagens(de_id,para_id,texto) VALUES(?,?,?)", (p, session["uid"], "Recebemos sua mensagem! Posso te enviar uma proposta."))
    return jsonify(ok=True)


@app.post("/api/pedidos")
@auth("e")
def pedir():
    d = body()
    p = q("SELECT * FROM produtos WHERE id=?", (int(d.get("produto_id") or 0),), one=True)
    if not p:
        return jsonify(erro="Produto não encontrado."), 404
    qtd = max(int(d.get("qtd") or p["qtd_min"]), p["qtd_min"])
    run("INSERT INTO pedidos(produto_id,empresario_id,qtd) VALUES(?,?,?)", (p["id"], session["uid"], qtd))
    return jsonify(ok=True, qtd=qtd)


@app.get("/api/pedidos")
@auth()
def pedidos():
    col = "p.fornecedor_id" if session["tipo"] == "f" else "o.empresario_id"
    return jsonify(q(f"""SELECT o.id,o.qtd,o.status,p.nome,p.unidade,e.empresa AS cliente,e.id AS cliente_id FROM pedidos o
      JOIN produtos p ON p.id=o.produto_id JOIN users e ON e.id=o.empresario_id WHERE {col}=? ORDER BY o.id DESC""", (session["uid"],)))


@app.post("/api/pedidos/<int:i>/status")
@auth("f")
def status(i):
    s = body().get("status")
    if s not in STATUS or not q("SELECT 1 FROM pedidos o JOIN produtos p ON p.id=o.produto_id WHERE o.id=? AND p.fornecedor_id=?", (i, session["uid"]), one=True):
        return jsonify(erro="Pedido inválido."), 400
    run("UPDATE pedidos SET status=? WHERE id=?", (s, i))
    return jsonify(ok=True)


@app.get("/api/painel")
@auth("f")
def painel():
    u = session["uid"]
    n = lambda s: q(s, (u,), one=True)["n"]
    return jsonify(produtos=n("SELECT COUNT(*) n FROM produtos WHERE fornecedor_id=?"), views=n("SELECT IFNULL(SUM(views),0) n FROM produtos WHERE fornecedor_id=?"),
                   mensagens=n("SELECT COUNT(*) n FROM mensagens WHERE para_id=?"),
                   pedidos=n("SELECT COUNT(*) n FROM pedidos o JOIN produtos p ON p.id=o.produto_id WHERE p.fornecedor_id=?"))


init_db()
if __name__ == "__main__":
    app.run(debug=True)
