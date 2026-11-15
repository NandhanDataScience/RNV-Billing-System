import os
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from io import BytesIO

from flask import Flask, abort, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("RNV_SECRET_KEY", "change-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "rnv_stores.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access the billing desk."

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False, index=True)
    category = db.Column(db.String(80), default="Grocery")
    selling_price = db.Column(db.Float, nullable=False, default=0)
    cost_price = db.Column(db.Float, nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(140), nullable=False, default="Cash Customer")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    total = db.Column(db.Float, nullable=False, default=0)
    items = db.relationship("SaleItem", backref="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(140), nullable=False)
    actual_price = db.Column(db.Float, nullable=False)  # selling price per unit at time of sale
    unit_cost = db.Column(db.Float, nullable=False)     # purchase cost per unit at time of sale
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@lru_cache(maxsize=1)
def get_background_removal_session():
    from rembg import new_session

    return new_session("u2net")


def remove_product_background(image_data):
    from rembg import remove

    return remove(
        image_data,
        session=get_background_removal_session(),
        force_return_bytes=True,
    )


def money(value):
    return f"₹{value:,.2f}"


app.jinja_env.filters["money"] = money


@app.context_processor
def inject_globals():
    return {"store_name": "RNV STORES"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pos"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(request.args.get("next") or url_for("pos"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def pos():
    products = Product.query.filter_by(active=True).order_by(Product.name.asc()).all()
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
    return render_template("pos.html", products=products, recent_sales=recent_sales)


@app.route("/api/products")
@login_required
def product_search():
    q = request.args.get("q", "").strip()
    query = Product.query.filter_by(active=True)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    products = query.order_by(Product.name.asc()).limit(50).all()
    return {
        "products": [{
            "id": p.id, "name": p.name, "category": p.category,
            "price": p.selling_price, "cost": p.cost_price, "stock": p.stock,
            "image": url_for("static", filename="uploads/" + p.image) if p.image else ""
        } for p in products]
    }


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        product_id = request.form.get("product_id")
        product = db.session.get(Product, int(product_id)) if product_id else Product()
        name = request.form.get("name", "").strip()
        try:
            selling = float(request.form.get("selling_price", "0"))
            cost = float(request.form.get("cost_price", "0"))
            stock = int(request.form.get("stock", "0"))
        except ValueError:
            flash("Enter valid numeric values for price and stock.", "error")
            return redirect(url_for("products"))
        if not name or selling < 0 or cost < 0 or stock < 0:
            flash("Product name, prices and stock must be valid.", "error")
            return redirect(url_for("products"))
        product.name = name
        product.category = request.form.get("category", "Grocery").strip() or "Grocery"
        product.selling_price = selling
        product.cost_price = cost
        product.stock = stock
        product.active = True
        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Image must be PNG, JPG, JPEG, WEBP or GIF.", "error")
                return redirect(url_for("products"))
            image_stem = secure_filename(os.path.splitext(image.filename)[0]) or "product"
            filename = secure_filename(f"{datetime.now().timestamp()}_{image_stem}.png")
            processed_image = remove_product_background(image.read())
            with open(os.path.join(app.config["UPLOAD_FOLDER"], filename), "wb") as output:
                output.write(processed_image)
            product.image = filename
        db.session.add(product)
        db.session.commit()
        flash("Product saved successfully.", "success")
        return redirect(url_for("products"))
    items = Product.query.order_by(Product.name.asc()).all()
    return render_template("products.html", products=items)


@app.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product:
        product.active = False
        db.session.commit()
        flash("Product hidden from the billing screen.", "success")
    return redirect(url_for("products"))


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    payload = request.get_json(silent=True) or {}
    customer = (payload.get("customer") or "Cash Customer").strip()[:140]
    items = payload.get("items") or []
    if not items:
        return {"ok": False, "message": "Add at least one product."}, 400

    try:
        invoice_no = "RNV-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[-17:]
        sale = Sale(invoice_no=invoice_no, customer_name=customer or "Cash Customer")
        db.session.add(sale)
        total = 0
        for row in items:
            product = db.session.get(Product, int(row["id"]))
            qty = int(row["quantity"])
            if not product or not product.active or qty < 1:
                raise ValueError("A selected product or quantity is invalid.")
            if qty > product.stock:
                raise ValueError(f"Only {product.stock} unit(s) of {product.name} are in stock.")
            # Snapshot price/cost so later product edits do not rewrite historical sales.
            price, cost = float(product.selling_price), float(product.cost_price)
            line_total = price * qty
            profit = (price - cost) * qty
            sale.items.append(SaleItem(
                product_id=product.id, product_name=product.name,
                actual_price=price, unit_cost=cost, quantity=qty,
                line_total=line_total, profit=profit
            ))
            product.stock -= qty
            total += line_total
        sale.total = total
        db.session.commit()
        return {"ok": True, "invoice": invoice_no, "total": total}
    except (ValueError, KeyError, TypeError) as exc:
        db.session.rollback()
        return {"ok": False, "message": str(exc)}, 400


@app.route("/sales")
@login_required
def sales():
    month_key = func.strftime("%Y-%m", Sale.created_at)
    rows = (db.session.query(month_key, func.count(Sale.id), func.sum(Sale.total))
            .group_by(month_key).order_by(month_key.desc()).all())
    months = [{
        "year": int(key[:4]),
        "month": int(key[5:]),
        "label": datetime.strptime(key, "%Y-%m").strftime("%B %Y"),
        "count": count,
        "total": total or 0,
    } for key, count, total in rows]
    return render_template(
        "sales.html", view_mode="months", months=months, page_title="Sales history",
        export_url=url_for("export_excel"),
    )


@app.route("/sales/<int:year>/<int:month>")
@login_required
def sales_month(year, month):
    try:
        month_start = datetime(year, month, 1)
        month_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    except ValueError:
        abort(404)

    sale_date = func.date(Sale.created_at)
    rows = (db.session.query(sale_date, func.count(Sale.id), func.sum(Sale.total))
            .filter(Sale.created_at >= month_start, Sale.created_at < month_end)
            .group_by(sale_date).order_by(sale_date.desc()).all())
    dates = [{
        "date": datetime.strptime(key, "%Y-%m-%d"),
        "count": count,
        "total": total or 0,
    } for key, count, total in rows]
    month_label = month_start.strftime("%B %Y")
    return render_template(
        "sales.html", view_mode="dates", dates=dates, year=year, month=month,
        month_label=month_label, page_title="Sales history",
        export_url=url_for("export_excel", year=year, month=month),
    )


@app.route("/sales/<int:year>/<int:month>/<int:day>")
@login_required
def sales_date(year, month, day):
    try:
        date_start = datetime(year, month, day)
        date_end = date_start + timedelta(days=1)
    except (ValueError, OverflowError):
        abort(404)

    records = (Sale.query
               .filter(Sale.created_at >= date_start, Sale.created_at < date_end)
               .order_by(Sale.created_at.desc()).all())
    return render_template(
        "sales.html", view_mode="invoices", sales=records, year=year, month=month,
        month_label=date_start.strftime("%B %Y"), date_label=date_start.strftime("%d %b %Y"),
        page_title="Sales history", export_url=url_for("export_excel", year=year, month=month, day=day),
    )


@app.route("/export.xlsx")
@login_required
def export_excel():
    raw_year = request.args.get("year")
    raw_month = request.args.get("month")
    raw_day = request.args.get("day")
    export_start = export_end = None

    if any(value is not None for value in (raw_year, raw_month, raw_day)):
        if raw_year is None or raw_month is None:
            abort(400)
        try:
            year, month = int(raw_year), int(raw_month)
            if raw_day is None:
                export_start = datetime(year, month, 1)
                export_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
            else:
                export_start = datetime(year, month, int(raw_day))
                export_end = export_start + timedelta(days=1)
        except (ValueError, OverflowError):
            abort(400)

    # One row per sold product line; repeat purchases by the same customer remain separate records.
    query = (db.session.query(Sale, SaleItem)
             .join(SaleItem, Sale.id == SaleItem.sale_id))
    if export_start is not None:
        query = query.filter(Sale.created_at >= export_start, Sale.created_at < export_end)
    rows = query.order_by(Sale.created_at.desc(), SaleItem.id.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Product Sales"
    headers = ["Date/Time", "Name of the Product", "Actual Price", "Quantity", "Cost", "Profit"]
    ws.append(headers)
    for sale, item in rows:
        ws.append([
            sale.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            item.product_name,
            item.actual_price,
            item.quantity,
            item.unit_cost * item.quantity,
            item.profit
        ])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="B51F2A")
        cell.alignment = Alignment(horizontal="center")
    for col, width in enumerate([22, 30, 18, 12, 18, 18], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        row[0].number_format = '₹#,##0.00'
    for row in ws.iter_rows(min_row=2, min_col=5, max_col=6):
        for cell in row:
            cell.number_format = '₹#,##0.00'
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    if export_start is None:
        filename = "RNV_Stores_Sales_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
    else:
        filename = "RNV_Stores_Sales_" + export_start.strftime(
            "%Y%m%d" if raw_day is not None else "%Y%m"
        ) + ".xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.errorhandler(413)
def too_large(_):
    flash("Image upload is too large. Maximum size is 5 MB.", "error")
    return redirect(url_for("products"))


def initialize_database():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username=os.environ.get("RNV_ADMIN_USER", "admin")).first():
            user = User(username=os.environ.get("RNV_ADMIN_USER", "admin"))
            user.set_password(os.environ.get("RNV_ADMIN_PASSWORD", "Murugan@123"))
            db.session.add(user)
            db.session.commit()


initialize_database()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
