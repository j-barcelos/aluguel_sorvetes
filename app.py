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