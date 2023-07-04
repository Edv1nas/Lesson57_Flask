import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user, logout_user, login_user, UserMixin, login_required
import forms
import secrets
from PIL import Image
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView


class ManoModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.el_pastas == "valio@valio.lt"


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(
        app.root_path, 'static/profilio_nuotraukos', picture_fn)

    output_size = (225, 225)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = '4654f5dfadsrfasdr54e6rae'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
    os.path.join(basedir, 'biudzetas.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'prisijungti'
login_manager.login_message_category = 'info'


class Vartotojas(db.Model, UserMixin):
    __tablename__ = "vartotojas"
    id = db.Column(db.Integer, primary_key=True)
    vardas = db.Column("Vardas", db.String(20), unique=True, nullable=False)
    el_pastas = db.Column("El. pašto adresas", db.String(
        120), unique=True, nullable=False)
    nuotrauka = db.Column(db.String(20), nullable=False, default='default.jpg')
    slaptazodis = db.Column("Slaptažodis", db.String(
        60), unique=True, nullable=False)
    data_records = db.relationship(
        'DataRecord', backref='Vartotojas', lazy=True)


class DataRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expenses_name = db.Column("Išlaidų pav.", db.String(20))
    cost = db.Column("Suma", db.Integer())
    user_id = db.Column(db.Integer, db.ForeignKey(
        'vartotojas.id'), nullable=False)


admin = Admin(app)
# admin.add_view(ModelView(Irasas, db.session))
admin.add_view(ManoModelView(Vartotojas, db.session))


@login_manager.user_loader
def load_user(user_id: str) -> Vartotojas:
    return Vartotojas.query.get(int(user_id))


@app.route("/registruotis", methods=['GET', 'POST'])
def registruotis():
    db.create_all()
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = forms.RegistracijosForma()
    if form.validate_on_submit():
        koduotas_slaptazodis = bcrypt.generate_password_hash(
            form.slaptazodis.data).decode('utf-8')
        vartotojas = Vartotojas(
            vardas=form.vardas.data, el_pastas=form.el_pastas.data, slaptazodis=koduotas_slaptazodis)
        db.session.add(vartotojas)
        db.session.commit()
        flash('Sėkmingai prisiregistravote! Galite prisijungti', 'success')
        return redirect(url_for('index'))
    return render_template('registruotis.html', title='Register', form=form)


@app.route("/prisijungti", methods=['GET', 'POST'])
def prisijungti():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = forms.PrisijungimoForma()
    if form.validate_on_submit():
        user = Vartotojas.query.filter_by(
            el_pastas=form.el_pastas.data).first()
        if user and bcrypt.check_password_hash(user.slaptazodis, form.slaptazodis.data):
            login_user(user, remember=form.prisiminti.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash(
                'Prisijungti nepavyko. Patikrinkite el. paštą ir slaptažodį', 'danger')
    return render_template('prisijungti.html', title='Prisijungti', form=form)


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = forms.PasswordChangeForma()
    if form.validate_on_submit():
        if bcrypt.check_password_hash(current_user.slaptazodis, form.senas_slaptazodis.data):
            new_password_hash = bcrypt.generate_password_hash(
                form.naujas_slaptazodis.data).decode('utf-8')
            current_user.slaptazodis = new_password_hash
            db.session.commit()
            flash('Slaptažodis sėkmingai pakeistas!', 'success')
            return redirect(url_for("paskyra"))
        else:
            flash('Neteisingas dabartinis slaptažodis.', 'danger')
    return render_template('change_password.html', form=form)


@app.route("/atsijungti")
def atsijungti():
    logout_user()
    return redirect(url_for('index'))


@app.route("/paskyra", methods=['GET', 'POST'])
@login_required
def paskyra():
    form = forms.PaskyrosAtnaujinimoForma()
    if form.validate_on_submit():
        if form.nuotrauka.data:
            nuotrauka = save_picture(form.nuotrauka.data)
            current_user.nuotrauka = nuotrauka
        current_user.vardas = form.vardas.data
        current_user.el_pastas = form.el_pastas.data
        db.session.commit()
        flash('Tavo paskyra atnaujinta!', 'success')
        return redirect(url_for('paskyra'))
    elif request.method == 'GET':
        form.vardas.data = current_user.vardas
        form.el_pastas.data = current_user.el_pastas
    nuotrauka = url_for(
        'static', filename='profilio_nuotraukos/' + current_user.nuotrauka)
    return render_template('paskyra.html', title='Account', form=form, nuotrauka=nuotrauka)


# @app.route("/irasai")
# @login_required
# def irasai():
#     return render_template('irasai.html', title='Įrašai')

@app.route('/irasai', methods=['GET', 'POST'])
def add_record():
    form = forms.DataRecordForm()
    if form.validate_on_submit():
        data_record = DataRecord(
            expenses_name=form.expenses_name.data,
            cost=form.cost.data,
            user_id=current_user.id
        )
        db.session.add(data_record)
        db.session.commit()
        flash("Įrašas sukurtas sėkmingai.")
        return redirect(url_for("paskyra"))
    return render_template('irasai.html', form=form)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
