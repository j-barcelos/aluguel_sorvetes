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