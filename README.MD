Vou migrar este projeto Django para Flask + SQLite. Abaixo está a estrutura completa convertida:

## Estrutura do Projeto Flask

```
meusite_flask/
├── app.py
├── models.py
├── config.py
├── requirements.txt
├── static/
│   ├── aluguel/
│   │   ├── css/
│   │   │   ├── style.css
│   │   │   └── painel.css
│   │   └── js/
│   │       ├── main.js
│   │       └── painel.js
│   └── img/
│       ├── logo-oggi.png
│       ├── fachada-oggi-barueri.jpeg
│       └── carrinho-oggi.jpeg
├── templates/
│   ├── aluguel/
│   │   ├── index.html
│   │   └── painel.html
└── instance/
    └── database.db
```

## 1. requirements.txt

```txt
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
Werkzeug==3.0.3
Pillow==10.3.0
python-decouple==3.8
```

## 2. config.py

```python
import os
from decouple import config

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-key')
    SQLALCHEMY_DATABASE_URI = config('DATABASE_URL', default=f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'media', 'sabores')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Configurações de sessão
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hora
```

## 3. models.py

```python
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from decimal import Decimal
import urllib.parse

db = SQLAlchemy()

class Carrinho(db.Model):
    __tablename__ = 'carrinho'
    
    id = db.Column(db.Integer, primary_key=True)
    preco_diaria = db.Column(db.Numeric(5, 2), nullable=False, default=50.00)
    status = db.Column(db.Boolean, default=True)
    
    reservas = db.relationship('Reserva', backref='carrinho', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': f'Carrinho {self.id}',
            'preco_diaria': str(self.preco_diaria),
            'status': self.status
        }
    
    def __repr__(self):
        return str(self.id)


class Sorvete(db.Model):
    __tablename__ = 'sorvete'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_sorvete = db.Column(db.String(200), nullable=False)
    preco = db.Column(db.Numeric(5, 2), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    imagem = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    
    itens_reserva = db.relationship('ReservaProduto', backref='sorvete', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome_sorvete,
            'preco': str(self.preco),
            'quantidade': self.quantidade,
            'ativo': self.ativo,
            'imagem_url': f'/static/media/sabores/{self.imagem}' if self.imagem else ''
        }
    
    def __repr__(self):
        return self.nome_sorvete


class Cliente(db.Model):
    __tablename__ = 'cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_cliente = db.Column(db.String(200), nullable=False)
    endereco = db.Column(db.String(300), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    
    reservas = db.relationship('Reserva', backref='cliente', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_cliente': self.nome_cliente,
            'telefone': self.telefone,
            'email': self.email or '',
            'endereco': self.endereco
        }
    
    def __repr__(self):
        return self.nome_cliente


class Reserva(db.Model):
    __tablename__ = 'reserva'
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    id_carrinho = db.Column(db.Integer, db.ForeignKey('carrinho.id'), nullable=True)
    data_evento = db.Column(db.Date, nullable=False)
    valor_pedido = db.Column(db.Numeric(6, 2), default=0)
    status = db.Column(db.String(15), default='pendente')
    descricao = db.Column(db.String(500), nullable=True)
    disponibilidade = db.Column(db.Boolean, default=False)
    
    itens = db.relationship('ReservaProduto', backref='reserva', lazy=True, cascade='all, delete-orphan')
    
    def subtotal_sorvetes(self):
        """Calcula APENAS o valor dos produtos escolhidos."""
        total = sum(
            item.quantidade_escolhida * float(item.sorvete.preco) 
            for item in self.itens if item.sorvete
        )
        return Decimal(str(total))
    
    def taxa_aluguel(self):
        """Calcula a taxa com base no subtotal e carrinhos ativos."""
        if self.subtotal_sorvetes() >= 300:
            return Decimal('0.00')
        
        carrinho_padrao = Carrinho.query.filter_by(status=True).first()
        if carrinho_padrao:
            return carrinho_padrao.preco_diaria
        return Decimal('50.00')
    
    def total_pedido(self):
        """Soma as duas partes para dar o valor final ao cliente."""
        return self.subtotal_sorvetes() + self.taxa_aluguel()
    
    def quantidade_carrinhos(self):
        """Extrai quantidade de carrinhos da descrição ou retorna 1"""
        import re
        texto = self.descricao or ''
        match = re.search(r'Quantidade de carrinhos(?: solicitada)?:\s*(\d+)', texto, re.IGNORECASE)
        if match:
            return max(1, int(match.group(1)))
        return 1
    
    def gerar_link_whatsapp(self):
        numero_whatsapp = "551141990035"
        
        def moeda(valor):
            return f"{float(valor):.2f}".replace(".", ",")
        
        data_formatada = self.data_evento.strftime("%d/%m/%Y") if self.data_evento else ''
        
        itens_texto = ""
        for item in self.itens:
            if item.sorvete:
                total_item = item.quantidade_escolhida * float(item.sorvete.preco)
                itens_texto += (
                    f"- {item.quantidade_escolhida}x {item.sorvete.nome_sorvete} "
                    f"(R$ {moeda(item.sorvete.preco)} un.) "
                    f"= R$ {moeda(total_item)}\n"
                )
        
        if not itens_texto:
            itens_texto = "Nenhum sorvete informado.\n"
        
        texto = (
            f"Olá! Gostaria de confirmar minha reserva.\n\n"
            f"*Reserva ID:* {self.id}\n"
            f"*Cliente:* {self.cliente.nome_cliente}\n"
            f"*Telefone:* {self.cliente.telefone}\n"
            f"*Endereço:* {self.cliente.endereco}\n"
            f"*Data do evento:* {data_formatada}\n\n"
            f"*Resumo do pedido:*\n"
            f"{itens_texto}\n"
            f"*Total dos produtos:* R$ {moeda(self.subtotal_sorvetes())}\n"
            f"*Taxa de aluguel:* R$ {moeda(self.taxa_aluguel())}\n"
            f"*Total geral:* R$ {moeda(self.total_pedido())}\n\n"
            f"*Observações:* {self.descricao or 'Nenhuma observação informada.'}\n\n"
            f"*Atenção:* Este valor não inclui frete, que será cotado via Lalamove no dia do evento."
        )
        
        texto_url = urllib.parse.quote(texto)
        return f"https://wa.me/{numero_whatsapp}?text={texto_url}"
    
    def to_dict(self):
        qtd_carrinhos = self.quantidade_carrinhos()
        subtotal = self.subtotal_sorvetes()
        taxa = self.taxa_aluguel()
        valor_carrinhos = taxa * qtd_carrinhos
        total = subtotal + valor_carrinhos
        
        sabores_txt = ', '.join(
            f"{item.quantidade_escolhida}x {item.sorvete.nome_sorvete}"
            for item in self.itens if item.sorvete
        )
        
        return {
            'id': self.id,
            'data': self.data_evento.strftime('%Y-%m-%d') if self.data_evento else '',
            'status': self.status,
            'cliente_id': self.id_cliente,
            'cliente_nome': self.cliente.nome_cliente if self.cliente else '',
            'cliente_telefone': self.cliente.telefone if self.cliente else '',
            'cliente_email': self.cliente.email if self.cliente else '',
            'cliente_endereco': self.cliente.endereco if self.cliente else '',
            'carrinho_id': self.id_carrinho,
            'quantidade_carrinhos': qtd_carrinhos,
            'carrinho_nome': f"{qtd_carrinhos} carrinho{'s' if qtd_carrinhos > 1 else ''}",
            'sabores': sabores_txt or 'Não informado',
            'observacoes': self.descricao or '',
            'subtotal': str(subtotal),
            'taxa_aluguel': str(valor_carrinhos),
            'valor_carrinhos': str(valor_carrinhos),
            'total': str(total),
        }
    
    def __repr__(self):
        return f"Reserva {self.id} - {self.cliente.nome_cliente if self.cliente else 'Sem cliente'}"


class ReservaProduto(db.Model):
    __tablename__ = 'reserva_produto'
    
    id = db.Column(db.Integer, primary_key=True)
    id_reserva = db.Column(db.Integer, db.ForeignKey('reserva.id'), nullable=False)
    id_sorvete = db.Column(db.Integer, db.ForeignKey('sorvete.id'), nullable=True)
    quantidade_escolhida = db.Column(db.Integer, default=1)
    
    def __repr__(self):
        return f"Item {self.id} - Reserva {self.id_reserva}"
```

## 4. app.py

```python
import os
import re
import json
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, abort, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

from config import Config
from models import db, Carrinho, Sorvete, Cliente, Reserva, ReservaProduto

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)

# Inicializa extensões
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'painel'

# Cria diretórios necessários
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.instance_path), exist_ok=True)

# Usuário admin simples (em produção, use tabela no banco)
ADMIN_USER = {
    'username': 'admin',
    'password': generate_password_hash('admin123')  # Mude em produção!
}

class AdminUser:
    def __init__(self, username):
        self.id = username
        self.username = username
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_staff = True
    
    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USER['username']:
        return AdminUser(user_id)
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_staff', False):
            return jsonify({'erro': 'Não autorizado.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Context processor para variáveis globais nos templates
@app.context_processor
def inject_globals():
    return {
        'STATIC_URL': '/static/',
        'MEDIA_URL': '/static/media/'
    }

# Rotas principais
@app.route('/')
def index():
    return render_template('aluguel/index.html')

@app.route('/painel')
@login_required
def painel():
    return render_template('aluguel/painel.html')

# API - Sabores
@app.route('/api/sabores/')
def api_sabores():
    """Retorna todos os sabores ativos"""
    sabores = Sorvete.query.filter_by(ativo=True).all()
    return jsonify([s.to_dict() for s in sabores])

@app.route('/api/admin/sabores/', methods=['GET', 'POST'])
@admin_required
def api_admin_sabores():
    if request.method == 'GET':
        sabores = Sorvete.query.order_by(Sorvete.nome_sorvete).all()
        return jsonify([s.to_dict() for s in sabores])
    
    elif request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        preco = request.form.get('preco', '0')
        ativo = request.form.get('ativo') == 'true'
        quantidade = int(request.form.get('quantidade') or 0)
        
        if not nome:
            return jsonify({'erro': 'Informe o nome do sabor.'}), 400
        
        sorvete = Sorvete(
            nome_sorvete=nome,
            preco=Decimal(str(preco).replace(',', '.')),
            ativo=ativo,
            quantidade=quantidade
        )
        
        # Processa imagem
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file.filename:
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                filename = f"sorvete_{int(os.time())}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Redimensiona imagem
                img = Image.open(filepath)
                max_size = (400, 400)
                img.thumbnail(max_size)
                img.save(filepath)
                
                sorvete.imagem = filename
        
        db.session.add(sorvete)
        db.session.commit()
        return jsonify(sorvete.to_dict()), 201

@app.route('/api/admin/sabores/<int:sorvete_id>/', methods=['POST'])
@admin_required
def api_admin_sabor_detalhe(sorvete_id):
    sorvete = Sorvete.query.get_or_404(sorvete_id)
    
    nome = request.form.get('nome', '').strip()
    preco = request.form.get('preco', '0')
    
    if not nome:
        return jsonify({'erro': 'Informe o nome do sabor.'}), 400
    
    sorvete.nome_sorvete = nome
    sorvete.preco = Decimal(str(preco).replace(',', '.'))
    sorvete.ativo = request.form.get('ativo') == 'true'
    sorvete.quantidade = int(request.form.get('quantidade') or 0)
    
    if 'imagem' in request.files:
        file = request.files['imagem']
        if file.filename:
            # Remove imagem antiga
            if sorvete.imagem:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], sorvete.imagem)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            filename = f"sorvete_{sorvete_id}_{int(os.time())}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            img = Image.open(filepath)
            max_size = (400, 400)
            img.thumbnail(max_size)
            img.save(filepath)
            
            sorvete.imagem = filename
    
    db.session.commit()
    return jsonify(sorvete.to_dict())

# API - Disponibilidade
@app.route('/api/disponibilidade/')
def api_disponibilidade():
    mes_ref = request.args.get('mes')
    if not mes_ref:
        return jsonify({"ocupacao": {}, "total_carrinhos": 0})
    
    try:
        ano, mes = map(int, mes_ref.split('-'))
        total_carrinhos = Carrinho.query.filter_by(status=True).count()
        
        # Busca reservas confirmadas do mês
        from sqlalchemy import extract
        reservas = Reserva.query.filter(
            extract('year', Reserva.data_evento) == ano,
            extract('month', Reserva.data_evento) == mes,
            Reserva.status == 'confirmado'
        ).all()
        
        dados_ocupacao = {}
        for reserva in reservas:
            chave = reserva.data_evento.strftime('%Y-%m-%d')
            qtd = reserva.quantidade_carrinhos()
            dados_ocupacao[chave] = dados_ocupacao.get(chave, 0) + qtd
        
        return jsonify({
            "total_carrinhos": total_carrinhos,
            "ocupacao": dados_ocupacao
        })
    except ValueError:
        return jsonify({"erro": "Data inválida"}), 400

# API - Reservas
@app.route('/api/reserva/criar/', methods=['POST'])
def api_criar_reserva():
    try:
        data = request.get_json()
        
        email_input = data.get('email')
        quantidade_carrinhos = max(1, int(data.get('quantidade_carrinhos') or 1))
        
        # Cria cliente
        cliente = Cliente(
            nome_cliente=data.get('nome'),
            telefone=data.get('telefone'),
            endereco=data.get('endereco'),
            email=email_input if email_input and email_input.strip() else None
        )
        db.session.add(cliente)
        db.session.flush()  # Para obter o ID
        
        # Prepara observação
        observacao = data.get('descricao') or ''
        if quantidade_carrinhos > 1:
            observacao = f"{observacao}\nQuantidade de carrinhos solicitada: {quantidade_carrinhos}".strip()
        
        # Cria reserva
        from datetime import datetime
        data_evento = datetime.strptime(data.get('data'), '%Y-%m-%d').date()
        
        reserva = Reserva(
            id_cliente=cliente.id,
            data_evento=data_evento,
            descricao=observacao,
            status='pendente',
            valor_pedido=0
        )
        db.session.add(reserva)
        db.session.flush()
        
        # Adiciona itens
        for item in data.get('sabores', []):
            sorvete = Sorvete.query.get(item['id'])
            if sorvete:
                reserva_produto = ReservaProduto(
                    id_reserva=reserva.id,
                    id_sorvete=sorvete.id,
                    quantidade_escolhida=item['qtd']
                )
                db.session.add(reserva_produto)
        
        db.session.commit()
        
        return jsonify({
            'status': 'sucesso',
            'whatsapp_url': reserva.gerar_link_whatsapp()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'erro', 'message': str(e)}), 400

@app.route('/api/reservas/', methods=['GET', 'POST'])
@admin_required
def api_reservas():
    if request.method == 'GET':
        reservas = Reserva.query.order_by(Reserva.data_evento.desc(), Reserva.id.desc()).all()
        return jsonify([r.to_dict() for r in reservas])
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            cliente = Cliente(
                nome_cliente=data.get('cliente_nome'),
                telefone=data.get('cliente_telefone', ''),
                email=data.get('cliente_email') or None,
                endereco=data.get('cliente_endereco', '')
            )
            db.session.add(cliente)
            db.session.flush()
            
            carrinho = None
            carrinho_id = data.get('carrinho_id')
            if carrinho_id:
                carrinho = Carrinho.query.get(carrinho_id)
            
            from datetime import datetime
            data_evento = datetime.strptime(data.get('data'), '%Y-%m-%d').date()
            
            reserva = Reserva(
                id_cliente=cliente.id,
                id_carrinho=carrinho.id if carrinho else None,
                data_evento=data_evento,
                descricao=data.get('observacoes', ''),
                status='pendente',
                valor_pedido=0
            )
            db.session.add(reserva)
            db.session.commit()
            
            return jsonify(reserva.to_dict()), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'erro': str(e)}), 400

@app.route('/api/reservas/<int:reserva_id>/')
@admin_required
def api_reserva_detalhe(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)
    return jsonify(reserva.to_dict())

@app.route('/api/reservas/<int:reserva_id>/status/', methods=['POST'])
@admin_required
def api_reserva_status(reserva_id):
    try:
        data = request.get_json()
        novo_status = data.get('status')
        
        if novo_status not in ['pendente', 'confirmado', 'cancelado']:
            return jsonify({'erro': 'Status inválido.'}), 400
        
        reserva = Reserva.query.get_or_404(reserva_id)
        reserva.status = novo_status
        
        # Se confirmado, dá baixa no estoque
        if novo_status == 'confirmado':
            for item in reserva.itens:
                if item.sorvete:
                    item.sorvete.quantidade -= item.quantidade_escolhida
                    if item.sorvete.quantidade < 0:
                        item.sorvete.quantidade = 0
        
        db.session.commit()
        return jsonify(reserva.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400

# API - Clientes
@app.route('/api/clientes/', methods=['GET', 'POST'])
@admin_required
def api_clientes():
    if request.method == 'GET':
        clientes = Cliente.query.order_by(Cliente.id).all()
        return jsonify([c.to_dict() for c in clientes])
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            cliente = Cliente(
                nome_cliente=data.get('nome_cliente'),
                telefone=data.get('telefone', ''),
                email=data.get('email') or None,
                endereco=data.get('endereco', '')
            )
            db.session.add(cliente)
            db.session.commit()
            return jsonify(cliente.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'erro': str(e)}), 400

# API - Carrinhos
@app.route('/api/carrinhos/')
@admin_required
def api_carrinhos():
    carrinhos = Carrinho.query.order_by(Carrinho.id).all()
    return jsonify([c.to_dict() for c in carrinhos])

@app.route('/api/carrinhos/<int:carrinho_id>/', methods=['POST'])
@admin_required
def api_carrinho_update(carrinho_id):
    try:
        carrinho = Carrinho.query.get_or_404(carrinho_id)
        data = request.get_json()
        
        carrinho.preco_diaria = Decimal(str(data.get('preco_diaria', 50)))
        carrinho.status = data.get('status', True)
        
        db.session.commit()
        return jsonify(carrinho.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400

# API - Auth
@app.route('/api/auth/login/', methods=['POST'])
def api_auth_login():
    dados = request.get_json()
    username = dados.get('username')
    password = dados.get('password')
    
    if username == ADMIN_USER['username'] and check_password_hash(ADMIN_USER['password'], password):
        user = AdminUser(username)
        login_user(user)
        return jsonify({'success': True, 'usuario': username})
    
    return jsonify({'erro': 'Usuário ou senha inválidos.'}), 401

@app.route('/api/auth/logout/', methods=['POST'])
@login_required
def api_auth_logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/auth/check/')
def api_auth_check():
    if current_user.is_authenticated and getattr(current_user, 'is_staff', False):
        return jsonify({
            'authenticated': True,
            'usuario': current_user.username
        })
    return jsonify({'authenticated': False}), 401

# Serve media files
@app.route('/static/media/sabores/<path:filename>')
def serve_sabor_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Inicialização do banco
@app.before_request
def init_db():
    if not hasattr(app, '_db_initialized'):
        with app.app_context():
            db.create_all()
            
            # Cria carrinhos padrão se não existirem
            if Carrinho.query.count() == 0:
                for i in range(1, 4):  # 3 carrinhos
                    c = Carrinho(preco_diaria=50.00, status=True)
                    db.session.add(c)
                db.session.commit()
            
            # Cria sabores de exemplo se não existirem
            if Sorvete.query.count() == 0:
                sabores_exemplo = [
                    ('Chocolate', 1.75, 200),
                    ('Morango', 1.75, 200),
                    ('Baunilha', 1.75, 200),
                    ('Flocos', 1.75, 150),
                    ('Creme', 1.50, 150),
                ]
                for nome, preco, qtd in sabores_exemplo:
                    s = Sorvete(nome_sorvete=nome, preco=preco, quantidade=qtd, ativo=True)
                    db.session.add(s)
                db.session.commit()
            
            app._db_initialized = True

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

## 5. templates/aluguel/index.html

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aluguel de Carrinhos de Sorvete</title>
    
    <link rel="stylesheet" href="{{ url_for('static', filename='aluguel/css/style.css') }}">
</head>
<body>

    <header class="header-fixo">
        <div class="container-header">
            <div class="logo">
                <img src="{{ url_for('static', filename='img/logo-oggi.png') }}" alt="Oggi Sorvetes">
            </div>
            
            <nav class="navegacao">
                <button type="button" class="menu-toggle" id="js-menu-toggle">☰</button>

                <ul class="menu-links" id="js-menu-links">
                    <li><a href="#como-funciona">Como funciona</a></li>
                    <li><a href="#lista-sorvetes">Sorvetes</a></li>
                    <li><a href="#calendar-grid">Calendário</a></li>
                    <li><a href="#duvidas-frequentes">Dúvidas</a></li>
                    <li><a href="#contato">Contato</a></li>
                </ul>
            </nav>
        </div>
    </header>

    <section class="hero-loja" id="inicio">
        <div class="hero-loja-conteudo">
            <div class="hero-texto">
                <span class="hero-etiqueta">Oggi Sorvetes Barueri Centro</span>

                <h1>Aluguel de carrinho de sorvete para festas e eventos</h1>

                <p>
                    Escolha os sabores, consulte a disponibilidade da data e finalize sua solicitação
                    com a nossa loja pelo WhatsApp.
                </p>

                <div class="hero-acoes">
                    <a href="#lista-sorvetes" class="btn-hero btn-hero-principal">Começar reserva</a>
                    <a href="#calendar-grid" class="btn-hero btn-hero-secundario">Ver calendário</a>
                </div>
            </div>

            <div class="hero-foto-placeholder" aria-label="Espaço reservado para foto da fachada da loja">
                <img
                    class="hero-fachada-img"
                    src="{{ url_for('static', filename='img/fachada-oggi-barueri.jpeg') }}"
                    alt="Fachada da Oggi Sorvetes Barueri">
            </div>
        </div>
    </section>

    <div class="container">
        <section class="produto-info" id="como-funciona">
            <div class="produto-imagem">
                <img src="{{ url_for('static', filename='img/carrinho-oggi.jpeg') }}" alt="Carrinho de sorvete Oggi para eventos">
            </div>

            <div class="info-rapida">
                <div class="info-item">
                    <strong>Retirada e devolução</strong>
                    <span>Retire no dia combinado e devolva no dia seguinte, dentro do nosso horário de funcionamento.</span>
                </div>

                <div class="info-item">
                    <strong>Capacidade média</strong>
                    <span>O carrinho comporta aproximadamente 200 sorvetes.</span>
                </div>

                <div class="info-item">
                    <strong>Refrigeração</strong>
                    <span>Mantém a refrigeração por cerca de 6 horas, dependendo do uso.</span>
                </div>

                <div class="info-item">
                    <strong>Entrega ou retirada</strong>
                    <span>Entrega via transportadora ou retirada na loja com carro espaçoso.</span>
                </div>
            </div>
        </section>

        <section id="secao-sabores">
            <h2>1. Selecione os Sabores</h2>
            <div id="lista-sorvetes" class="card-container">
                <!-- Preenchido via JS -->
            </div>
        </section>

        <section class="calendario-secao">
            <h2>2. Escolha a Data do Evento</h2>
            <p>As cores indicam a disponibilidade da nossa frota para o dia selecionado.</p>
            
            <div class="calendario-controle-mes">
                <button id="btn-mes-anterior" class="btn-mes btn-mes-anterior" onclick="mudarMes(-1)">
                    &#10094; Anterior
                </button>

                <h3 id="mes-ano-display">Mês Ano</h3>

                <button id="btn-mes-proximo" class="btn-mes btn-mes-proximo" onclick="mudarMes(1)">
                    Próximo &#10095;
                </button>
            </div>
            
            
            <div class="legenda">
                <div class="legenda-item">
                    <span class="ponto passado"></span> Data passada
                </div>
                <div class="legenda-item">
                    <span class="ponto livre"></span> Livre
                </div>
                <div class="legenda-item">
                    <span class="ponto alerta"></span> Poucas vagas
                </div>
                <div class="legenda-item">
                    <span class="ponto esgotado"></span> Esgotado
                </div>
            </div>

            <div id="calendar-grid" class="calendar-grid"></div>
        </section>

        <section id="secao-carrinhos" class="secao-carrinhos" style="display: none;">
            <h2>3. Quantidade de Carrinhos</h2>
            <p>Quantos carrinhos você precisa para o seu evento?</p>

            <div class="carrinhos-controle">
                <label for="qtd-carrinhos">Carrinhos necessários:</label>

                <select id="qtd-carrinhos" onchange="atualizarQuantidadeCarrinhos()">
                </select>

                <span id="aviso-disponibilidade"></span>
            </div>
        </section>

        <div class="finalizar-area">
            <button id="btn-abrir-reserva" class="btn-finalizar" onclick="abrirModal()">
                Revisar e finalizar reserva
            </button>
        </div>
    </div>

    <section id="duvidas-frequentes" class="faq-section">
        <div class="section-header">
            <span class="section-tag">Dúvidas frequentes</span>
            <h2>Antes de finalizar sua reserva</h2>
            <p>Veja as respostas para as principais dúvidas sobre o aluguel do carrinho.</p>
        </div>

        <div class="faq-lista">
            <details>
                <summary>Como funciona o aluguel?</summary>
                <p>A retirada do carrinho é feita no dia solicitado e a devolução deve ocorrer no dia seguinte, sempre dentro do horário de funcionamento da loja.</p>
            </details>

            <details>
                <summary>Existe multa por atraso na devolução?</summary>
                <p>Sim. Caso o carrinho seja devolvido fora do prazo combinado, será cobrada multa de R$ 50,00 por dia atrasado.</p>
            </details>

            <details>
                <summary>Quantos sorvetes cabem no carrinho?</summary>
                <p>O carrinho comporta aproximadamente 200 sorvetes. A capacidade pode variar conforme a organização dos produtos, marcas e quantidade escolhida pois cada marca tem um tamanho variado de picolé.</p>
            </details>

            <details>
                <summary>Quanto tempo dura a refrigeração?</summary>
                <p>A refrigeração dura em média 6 horas, podendo variar conforme a frequência de abertura do carrinho durante o evento ou caso esqueçam destampado.</p>
            </details>

            <details>
                <summary>Vocês entregam?</summary>
                <p>A entrega pode ser feita por uma transportadora terceirizada, com frete calculado separadamente. Também é possível retirar na loja com um carro espaçoso.</p>
            </details>

            <details>
                <summary>Tem pedido mínimo de sorvetes?</summary>
                <p>Pelo site, é necessário selecionar pelo menos 1 sorvete para enviar a solicitação. A quantidade total fica a critério do cliente e está sujeita à disponibilidade da loja.</p>
            </details>

            <details>
                <summary>Há desconto ou preço de atacado?</summary>
                <p>Não. Os sorvetes mantêm o mesmo valor unitário, independentemente da quantidade solicitada.</p>
            </details>

            <details>
                <summary>Quais formas de pagamento são aceitas?</summary>
                <p>O pagamento pode ser feito via Pix presencialmente ou pelo WhatsApp. Na loja, também aceitamos débito, crédito e dinheiro.</p>
            </details>
        </div>
    </section>

    <!-- MODAL DE FINALIZAÇÃO -->
    <div id="modal-reserva" class="modal">
        <div class="modal-content">
            <span class="close" onclick="fecharModal()">&times;</span>
            
            <div class="modal-scroll-area">
                <h2>Resumo do Pedido</h2>
                <div id="resumo-pedido" class="nota-fiscal">
                    <p>Selecione sabores e uma data para ver o resumo.</p>
                </div>

                <form id="form-contato" onsubmit="event.preventDefault(); finalizarPedido();">
                    <div class="input-group">
                        <label for="cli-nome">Nome Completo*</label>
                        <input type="text" id="cli-nome" required maxlength="80" placeholder="Seu nome">
                    </div>

                    <div class="input-group">
                        <label for="cli-tel">WhatsApp*</label>
                        <input type="text" id="cli-tel" required maxlength="15" onkeyup="mascaraTelefone(this)" placeholder="(00) 00000-0000">
                    </div>

                    <div class="input-group">
                        <label for="cli-email">E-mail (Opcional)</label>
                        <input type="email" id="cli-email" maxlength="100" placeholder="seu@email.com">
                    </div>

                    <div class="input-group">
                        <label for="cli-end">Endereço de Entrega*</label>
                        <input type="text" id="cli-end" required maxlength="200" placeholder="Rua, número e bairro do evento">
                    </div>

                    <div class="input-group">
                        <label for="cli-obs">Observações/Dúvidas</label>
                        <textarea id="cli-obs" rows="3" maxlength="400" placeholder="Ex: Horário de início..."></textarea>
                    </div>

                    <button type="submit" class="btn-finalizar" style="background-color: #25d366;">
                        🚀 Confirmar Reserva no WhatsApp
                    </button>
                </form>
            </div>
            </div>
    </div>

    <script src="{{ url_for('static', filename='aluguel/js/main.js') }}"></script>
    <script>
        function abrirModal() {
            document.getElementById('modal-reserva').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
        function fecharModal() {
            document.getElementById('modal-reserva').style.display = 'none';
            document.body.style.overflow = 'auto';
        }
        window.onclick = function(event) {
            if (event.target == document.getElementById('modal-reserva')) fecharModal();
        }
    </script>

    <div id="modal-contrato" class="modal modal-contrato" style="display: none; z-index: 1001;">
    <div class="modal-content contrato-content">
        <span class="close" onclick="fecharModalContrato()">&times;</span>
        
        <div class="contrato-header">
            <h2>Contrato de comodato de carrinho de sorvetes</h2>
            <p><strong>Oggi Sorvetes</strong> | Instrumento particular de parceria</p>
        </div>
        
        <div class="contrato-scroll">
            <div id="corpo-contrato-scroll" class="contrato-scroll" style="border: 1px solid #aaa; padding: 20px; height: 350px; overflow-y: scroll; background: #fff; font-size: 0.85rem; line-height: 1.5; text-align: justify; border-radius: 4px;">
                
                <strong>COMODANTE:</strong><br>
                Razão Social: Hevon Comercio LTDA<br>
                CNPJ: 38.467.951/0001-48<br>
                Endereço: Av. Henriqueta Mendes Guerra, 1330 – Loja 16-H Terreo<br><br>

                <strong>COMODATÁRIO(A):</strong><br>
                <span id="ct-dados-cliente" style="background-color: #fff9c4; padding: 2px 4px; border-radius: 3px;">
                    Preencha os dados no formulário anterior...
                </span><br><br>

                <p>As partes acima qualificadas têm, entre si, justo e contratado o presente Comodato, que se regerá pelas cláusulas e condições seguintes:</p>

                <p><strong>I. OBJETO DO COMODATO:</strong> O presente contrato tem como objeto a entrega a título de Comodato de <strong id="ct-qtd-carrinhos" style="color:red;">__</strong> Carrinho(s) de Sorvete da marca CEM PRODUTOS PLÁSTICOS ("Equipamento"), de propriedade da COMODANTE.</p>
                <p><strong>II. VALOR DO EQUIPAMENTO:</strong> O valor do equipamento descrito no item anterior é de R$ 2.500,00 (dois mil e quinhentos reais).</p>
                <p><strong>III. LOCAL DO EVENTO:</strong> O equipamento será utilizado no endereço fornecido: <strong id="ct-endereco-evento">__</strong>.</p>
                <p><strong>IV. PRAZO DE VIGÊNCIA DO CONTRATO:</strong> O prazo de vigência é de 1 (um) dia, balizado pela data do evento: <strong id="ct-data-evento">__</strong>.</p>

                <hr style="border: 0; border-top: 1px solid #eee; margin: 15px 0;">

                <p><strong>1 –</strong> O <strong>COMODATÁRIO(A)</strong> declara que está ciente e de pleno acordo com as cláusulas, sob pena de rescisão e perdas e danos.</p>
                <p><strong>2 –</strong> O Equipamento destina-se ao armazenamento dos Sorvetes Oggi, não podendo ser utilizado para fins comerciais de terceiros.</p>
                <p><strong>3 –</strong> É vedado o armazenamento de quaisquer outros produtos no Equipamento.</p>
                <p><strong>4 –</strong> Não é permitida a transferência do Equipamento para outro local sem autorização prévia da COMODANTE.</p>
                <p><strong>5 a 16 –</strong> [Demais cláusulas de conservação, devolução no prazo estipulado, multas por atraso e eleição do Foro da Comarca de Barueri/SP confirmadas no ato do envio].</p>
                <p><strong>17. DA PROTEÇÃO DE DADOS (LGPD):</strong> Autorizo a COMODANTE a tratar os dados pessoais fornecidos para fins logísticos e de segurança (Lei nº 13.709/2018).</p>
            </div>
        </div>

        <div class="contrato-aceite">
            <input type="checkbox" id="aceite-contrato" disabled onchange="alternarBotaoFinalizar()">
            <label for="aceite-contrato">
                Declaro que li, preenchi corretamente e aceito todos os termos do contrato de comodato acima, incluindo a responsabilidade pelo valor de R$ 2.500,00 por equipamento.
            </label>
        </div>

        <div class="contrato-acoes">
            <button type="button" class="btn-finalizar btn-voltar" onclick="fecharModalContrato()">Voltar e ajustar</button>
            <button type="button" id="btn-enviar-reserva" class="btn-finalizar btn-whatsapp-contrato" disabled onclick="enviarFormularioServidor()">
                Aceitar contrato e ir para o WhatsApp
            </button>
        </div>
    </div>
</div>

    <footer id="contato" class="footer-contato">
    <div class="footer-conteudo">
        <div class="footer-marca">
            <img src="{{ url_for('static', filename='img/logo-oggi.png') }}" alt="Oggi Sorvetes">
            <p>Aluguel de carrinhos de sorvete para festas, empresas e eventos em Barueri e região.</p>
            <p class="footer-destaque">Retirada na loja ou entrega via transportadora.</p>
        </div>

        <div class="footer-coluna">
            <h3>Contato</h3>

            <a href="https://wa.me/551141990035" target="_blank" rel="noopener">
                WhatsApp: (11) 4199-0035
            </a>

            <a href="https://www.instagram.com/oggi.Barueri" target="_blank" rel="noopener">
                Instagram: @oggi.Barueri
            </a>
        </div>

        <div class="footer-coluna">
            <h3>Endereço</h3>
            <p>
                Av. Henriqueta Mendes Guerra, 1330<br>
                Loja 16-H - Térreo<br>
                Centro - Barueri/SP
            </p>
            <a href="https://maps.app.goo.gl/yHEGb7FcRJR7RvvLA" target="_blank" rel="noopener">
                Ver localização no Google Maps
            </a>
        </div>

        <div class="footer-coluna">
            <h3>Horário</h3>
            <p>
                Segunda a sábado<br>
                das 09:00 às 20:00
            </p>
            <p>
                Domingo e feriados<br>
                das 11:00 às 17:00
            </p>
        </div>
    </div>

    <div class="footer-base">
        <p>© 2026 Oggi Sorvetes Barueri. Todos os direitos reservados.</p>
        <p>Hevon Comércio LTDA - CNPJ: 38.467.951/0001-48</p>
    </div>
</footer>
</body>
</html>
```

## 6. templates/aluguel/painel.html

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Oggi Admin — Gestão de Reservas</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Nunito:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="{{ url_for('static', filename='aluguel/css/painel.css') }}">
</head>
<body>

<div id="loginScreen">
  <div class="login-box">
    <div class="login-logo">🍦</div>
    <div class="login-title">Oggi Admin</div>
    <div class="login-sub">Acesso restrito — somente administradores</div>
    <div class="login-field">
      <label>Usuário</label>
      <input type="text" id="loginUser" placeholder="admin" autocomplete="username"/>
    </div>
    <div class="login-field">
      <label>Senha</label>
      <input type="password" id="loginPass" placeholder="••••••••" autocomplete="current-password"/>
    </div>
    <button class="login-btn" onclick="tentarLogin()">Entrar no Painel</button>
    <div class="login-error" id="loginError">Usuário ou senha incorretos.</div>
    <div class="login-lock">🔒 Área protegida — acesso não autorizado é registrado</div>
  </div>
</div>

<div class="mobile-top-bar">
  <button class="burger-btn" id="sidebarToggle" aria-label="Menu">
    <span></span><span></span><span></span>
  </button>
  <span style="font-family:'Syne',sans-serif;font-weight:800;color:white;font-size:16px">🍦 Oggi Admin</span>
</div>
<div class="sidebar-overlay" id="sidebarOverlay"></div>

<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <span>🍦</span>
    <div>
      <div class="sidebar-logo-text">Oggi</div>
      <div class="sidebar-logo-sub">Painel Admin</div>
    </div>
  </div>
  <nav class="sidebar-nav">
    <button class="nav-item active" onclick="setView('calendario',this)">
      <span class="nav-icon">📅</span> Calendário
    </button>
    <button class="nav-item" onclick="setView('reservas',this)">
      <span class="nav-icon">📋</span> Reservas
    </button>
    <button class="nav-item" onclick="setView('clientes',this)">
      <span class="nav-icon">👥</span> Clientes
    </button>
    <button class="nav-item" onclick="setView('sabores',this)">
      <span class="nav-icon">🍨</span> Sabores
    </button>
    <button class="nav-item" onclick="setView('carrinhos',this)">
      <span class="nav-icon">🛒</span> Carrinhos
    </button>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,.08);margin:8px 0"/>
    <a href="/" class="nav-item" target="_blank">
      <span class="nav-icon">🌐</span> Ver Site
    </a>
  </nav>
  <div class="sidebar-footer">
    <button class="logout-btn" onclick="logout()">
      <span>🚪</span> Sair
    </button>
  </div>
</aside>

<div class="main-content">
  <div class="top-bar">
    <h1 id="pageTitle">📅 Calendário de Reservas</h1>
    <div style="display:flex;gap:10px;flex-wrap:wrap;" id="topBarActions">
      <button class="btn btn-outline btn-sm" onclick="recarregarPainel()">
        🔄 Atualizar
      </button>
    </div>
  </div>

  <div class="content">

    <div class="metrics-grid">
      <div class="metric-card pending">
        <div class="metric-icon">⏳</div>
        <div class="metric-value" id="metPendentes">—</div>
        <div class="metric-label">Pendentes</div>
        <div class="metric-delta neutral" id="metPendDelta"></div>
      </div>
      <div class="metric-card confirmed">
        <div class="metric-icon">✅</div>
        <div class="metric-value" id="metConfirmadas">—</div>
        <div class="metric-label">Confirmadas</div>
      </div>
      <div class="metric-card total">
        <div class="metric-icon">📊</div>
        <div class="metric-value" id="metTotal">—</div>
        <div class="metric-label">Total no Mês</div>
      </div>
      <div class="metric-card carts">
        <div class="metric-icon">🛒</div>
        <div class="metric-value" id="metCarrinhos">3</div>
        <div class="metric-label">Carrinhos Disponíveis</div>
      </div>
    </div>

    <div id="view-calendario" class="view-section active">
      <div class="max-info">
        <span>⚠️</span>
        <span>Máximo de <strong>3 reservas por dia</strong> (1 por carrinho). Dias cheios ficam bloqueados automaticamente para os usuários.</span>
      </div>
      <div style="height:12px"></div>
      <div class="admin-layout">
        <div class="calendar-card">
          <div class="cal-header">
            <button class="cal-nav-btn" id="prevMonth">‹</button>
            <h2 id="calTitle">—</h2>
            <button class="cal-nav-btn" id="nextMonth">›</button>
          </div>
          <div class="cal-weekdays">
            <span>Dom</span><span>Seg</span><span>Ter</span>
            <span>Qua</span><span>Qui</span><span>Sex</span><span>Sáb</span>
          </div>
          <div class="cal-body" id="calBody">
            <div style="grid-column:1/-1;text-align:center;padding:32px"><div class="spinner"></div></div>
          </div>
        </div>

        <div class="admin-sidebar">
          <div class="panel">
            <div class="panel-header"><span class="panel-title">Capacidade Diária</span></div>
            <div class="panel-body" style="gap:10px">
              <div style="display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600">
                <span class="day-capacity ok">1–2</span> Disponível
              </div>
              <div style="display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600">
                <span class="day-capacity warn">2/3</span> Quase cheio
              </div>
              <div style="display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600">
                <span class="day-capacity full">3/3</span> Lotado
              </div>
              <div style="display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600">
                <div style="width:20px;height:12px;border-radius:3px;background:repeating-linear-gradient(45deg,#eee,#eee 3px,#ddd 3px,#ddd 6px)"></div>
                Bloqueado pelo admin
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <span class="panel-title">⏳ Aguardando Confirmação</span>
              <span style="font-size:11px;color:var(--mid);font-weight:600" id="pendentesCount">0</span>
            </div>
            <div class="panel-body" id="pendentesList" style="max-height:400px;overflow-y:auto">
              <div class="spinner"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="view-reservas" class="view-section">
      <div class="reservas-table-wrap">
        <div class="reservas-table-header">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
  <h2 style="margin:0;">📋 Todas as Reservas</h2>

  <input
    type="text"
    id="buscaReserva"
    class="form-control"
    placeholder="Buscar cliente..."
    style="width:220px;padding:8px 12px;font-size:13px;"
    oninput="renderReservasTabela()"
  >
</div>
          <div class="filter-tabs" id="reservasTabs">
            <button class="filter-tab active" onclick="filtrarReservas('todas',this)">Todas</button>
            <button class="filter-tab" onclick="filtrarReservas('pendente',this)">Pendentes</button>
            <button class="filter-tab" onclick="filtrarReservas('confirmado',this)">Confirmadas</button>
            <button class="filter-tab" onclick="filtrarReservas('cancelado',this)">Canceladas</button>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table>
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Data</th>
                <th>Carrinho</th>
                <th>Sabores</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody id="reservasTableBody"></tbody>
          </table>
        </div>
      </div>
    </div>

    <div id="view-clientes" class="view-section">
  <div class="reservas-table-header">
  <h2>👥 Clientes <span id="clientesTotal" style="font-size:13px;color:var(--mid);font-weight:700;">0 cadastrados</span></h2>

  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
    <input
      type="text"
      id="clientesBusca"
      class="form-control"
      placeholder="Pesquisar cliente..."
      style="width:220px;padding:8px 12px;font-size:13px;"
      oninput="renderClientesTabela()"
    >

    <select
      id="clientesOrdem"
      class="form-control"
      style="width:160px;padding:8px 12px;font-size:13px;"
      onchange="renderClientesTabela()"
    >
      <option value="id">Ordenar por ID</option>
      <option value="nome">Ordenar por nome</option>
      <option value="telefone">Ordenar por telefone</option>
    </select>

    <button class="btn btn-primary btn-sm" onclick="openModal('modalCliente')">
      + Novo Cliente
    </button>
  </div>
</div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>ID Cliente</th>
            <th>Nome</th>
            <th>Telefone</th>
            <th>Email</th>
            <th>Endereço</th>
          </tr>
        </thead>

        <tbody id="clientesTableBody"></tbody>
      </table>
    </div>
  </div>
</div>

    <div id="view-sabores" class="view-section">
      <div class="sabores-section">
        <div class="sabores-header">
          <h2>Sabores</h2>
          <button class="btn btn-primary btn-sm" onclick="abrirModalNovoSabor()">
            + Novo Sabor
          </button>
        </div>

        <div class="sabores-grid-admin" id="saboresAdminGrid"></div>
      </div>
    </div>

    <div id="view-carrinhos" class="view-section">
      <div class="carrinhos-section">
        <div class="carrinhos-header">
          <h2>🛒 Carrinhos</h2>
          <p>Temos <strong>3 carrinhos</strong> disponíveis. O máximo de reservas por dia é <strong>3</strong> (um por carrinho).</p>
        </div>
        <div class="carrinhos-list" id="carrinhosList"></div>
      </div>
    </div>

  </div>
</div>

<div class="overlay" id="modalReserva">
  <div class="modal">
    <div class="modal-title">🍦 Nova Reserva</div>
    <div class="form-group">
      <label class="form-label">Data *</label>
      <input type="date" class="form-control" id="fData"/>
      <span style="font-size:12px;color:var(--mid);margin-top:4px" id="fDataAviso"></span>
    </div>
    <div class="form-group">
      <label class="form-label">Carrinho *</label>
      <select class="form-control" id="fCarrinho"></select>
    </div>
    <div class="form-group">
      <label class="form-label">Nome do Cliente *</label>
      <input type="text" class="form-control" id="fNome" placeholder="Ex: Maria Silva"/>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">E-mail</label>
        <input type="email" class="form-control" id="fEmail" placeholder="email@exemplo.com"/>
      </div>
      <div class="form-group">
        <label class="form-label">Telefone</label>
        <input type="tel" class="form-control" id="fTelefone" placeholder="(11) 99999-9999"/>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Sabores Solicitados</label>
      <input type="text" class="form-control" id="fSabores" placeholder="Ex: Chocolate, Morango, Baunilha"/>
    </div>
    <div class="form-group">
      <label class="form-label">Observações</label>
      <textarea class="form-control" id="fObs" placeholder="Informações adicionais..."></textarea>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('modalReserva')">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarReserva()">💾 Salvar Reserva</button>
    </div>
  </div>
</div>

<div class="overlay" id="modalBloqueio">
  <div class="modal" style="max-width:380px">
    <div class="modal-title">🔒 Bloquear Data</div>
    <div class="form-group">
      <label class="form-label">Data *</label>
      <input type="date" class="form-control" id="bData"/>
    </div>
    <div class="form-group">
      <label class="form-label">Motivo</label>
      <input type="text" class="form-control" id="bMotivo" placeholder="Ex: Feriado, manutenção..."/>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('modalBloqueio')">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarBloqueio()">🔒 Confirmar Bloqueio</button>
    </div>
  </div>
</div>

<div class="overlay" id="modalDetalhe">
  <div class="modal">
    <div class="modal-title">📋 Detalhes da Reserva</div>
    <div id="detalheBody"></div>
    <div class="modal-footer" id="detalheBotoes"></div>
  </div>
</div>

<div class="overlay" id="modalCliente">
  <div class="modal">

    <div class="modal-title">👥 Novo Cliente</div>

    <div class="form-group">
      <label class="form-label">Nome *</label>
      <input type="text" class="form-control" id="cNome">
    </div>

    <div class="form-group">
      <label class="form-label">Telefone</label>
      <input type="text" class="form-control" id="cTelefone">
    </div>

    <div class="form-group">
      <label class="form-label">Email</label>
      <input type="email" class="form-control" id="cEmail">
    </div>

    <div class="form-group">
      <label class="form-label">Endereço</label>
      <input type="text" class="form-control" id="cEndereco">
    </div>

    <div class="modal-footer">
      <button class="btn btn-outline"
              onclick="closeModal('modalCliente')">
        Cancelar
      </button>

      <button class="btn btn-primary"
              onclick="salvarCliente()">
        💾 Salvar Cliente
      </button>
    </div>

  </div>
</div>

<div class="overlay" id="modalSabor">
  <div class="modal">
    <div class="modal-title" id="modalSaborTitulo">Editar Sabor</div>

    <input type="hidden" id="saborEditId">

    <div class="form-group">
      <label class="form-label">Nome *</label>
      <input type="text" class="form-control" id="saborEditNome">
    </div>

    <div class="form-group">
      <label class="form-label">Preço *</label>
      <input type="number" step="0.01" class="form-control" id="saborEditPreco">
    </div>

    <div class="form-group">
      <label class="form-label">Quantidade em estoque</label>
      <input type="number" class="form-control" id="saborEditQuantidade">
    </div>

    <div class="form-group">
      <label class="form-label">Foto</label>
      <input type="file" class="form-control" id="saborEditImagem" accept="image/*">
    </div>

    <label style="font-size:13px;font-weight:800">
      <input type="checkbox" id="saborEditAtivo">
      Ativo
    </label>

    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('modalSabor')">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarSaborModal()">Salvar Sabor</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script src="{{ url_for('static', filename='aluguel/js/painel.js') }}"></script>
</body>
</html>
```

## Instruções de Migração

1. **Copie os arquivos estáticos** do projeto Django para a pasta `static/` do Flask:
   - `aluguel/static/aluguel/css/` → `static/aluguel/css/`
   - `aluguel/static/alugorel/js/` → `static/aluguel/js/`
   - `aluguel/static/img/` → `static/img/`

2. **Configure as variáveis de ambiente** criando um arquivo `.env`:
```env
SECRET_KEY=sua-chave-secreta-aqui
FLASK_ENV=development
```

3. **Execute a aplicação**:
```bash
pip install -r requirements.txt
python app.py
```

4. **Acesse**:
- Site: `http://localhost:5000/`
- Painel Admin: `http://localhost:5000/painel`
- Login: `admin` / `admin123` (altere em produção!)

## Principais Alterações Realizadas

1. **Models**: Convertidos de Django ORM para SQLAlchemy
2. **Views**: Convertidas de Django views para Flask routes
3. **Templates**: Adaptados de Django Template Language para Jinja2 (sintaxe similar)
4. **Autenticação**: Simplificada usando Flask-Login com usuário hardcoded (substitua por tabela no banco em produção)
5. **Banco de Dados**: MySQL → SQLite (pode ser alterado facilmente na configuração)
6. **CSRF**: Implementado via Flask-WTF (necessário adicionar ao JS se quiser usar tokens)
7. **Upload de Imagens**: Configurado para salvar em `static/media/sabores/`

O sistema mantém todas as funcionalidades originais: reservas, controle de estoque, calendário de disponibilidade, painel administrativo e geração de link WhatsApp.
