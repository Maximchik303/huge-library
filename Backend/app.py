from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['CORS_HEADERS'] = 'Content-Type'

db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    disabled = db.Column(db.Boolean, default=False)
    books = db.relationship('BorrowedBook', backref='customer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    borrowed = db.Column(db.Boolean, default=False)
    disabled = db.Column(db.Boolean, default=False)  


class BorrowedBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    returned = db.Column(db.Boolean, default=False)  


# Routes
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get('name')
    password = data.get('password')

    if Customer.query.filter_by(name=name).first():
        return jsonify({"error": "Customer already exists"}), 400

    new_customer = Customer(name=name)
    new_customer.set_password(password)

    db.session.add(new_customer)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    name = data['name']
    password = data['password']

    customer = Customer.query.filter_by(name=name).first()
    if customer is None or not customer.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    session['user_id'] = customer.id
    session['user_name'] = customer.name

    if name == 'admin':
        return jsonify({"message": "Login to admin successful", "redirect": "admin.html"}), 200

    return jsonify({"message": "Login successful", "redirect": "library.html", "name": customer.name}), 200

@app.route("/logout", methods=["POST"])
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/books", methods=["GET"])
def get_books():
    books = Book.query.filter_by(disabled=False).all()
    book_list = [{'id': book.id, 'name': book.name, 'author': book.author, 'borrowed': book.borrowed, 'disabled': book.disabled} for book in books]
    return jsonify(book_list)

@app.route("/borrow/<int:book_id>", methods=["POST"])
def borrow_book(book_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    customer_id = session['user_id']
    customer = Customer.query.get(customer_id)
    book = Book.query.get(book_id)

    if not customer or not book:
        return jsonify({"error": "Customer or book not found"}), 404

    # Check if the customer is already borrowing this book
    already_borrowed = BorrowedBook.query.filter_by(customer_id=customer_id, book_id=book_id, returned=False).first()
    if already_borrowed:
        return jsonify({"error": "You have already borrowed this book"}), 400

    borrowed_book = BorrowedBook(customer_id=customer_id, book_id=book_id)
    db.session.add(borrowed_book)
    db.session.commit()

    return jsonify({"message": f"Book '{book.name}' borrowed successfully"}), 200

@app.route("/return/<int:borrow_id>", methods=["POST"])
def return_book(borrow_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    customer_id = session['user_id']
    borrowed_book = BorrowedBook.query.filter_by(id=borrow_id, customer_id=customer_id, returned=False).first()

    if not borrowed_book:
        return jsonify({"error": "Borrow record not found or already returned"}), 400

    # Mark the specific borrow instance as returned
    borrowed_book.returned = True
    db.session.commit()

    return jsonify({"message": f"Returned book succesfully"}), 200


@app.route("/add_book", methods=["POST"])
def add_book():
    data = request.get_json()
    name = data.get('name')
    author = data.get('author')

    if not name or not author:
        return jsonify({"error": "Missing required fields"}), 400

    new_book = Book(name=name, author=author)
    db.session.add(new_book)
    db.session.commit()

    return jsonify({"message": "Book added successfully"}), 201

# Admin Page Routes
@app.route("/admin_books", methods=["GET"])
def get_admin_books():
    books = Book.query.all()
    book_list = [{'id': book.id, 'name': book.name, 'author': book.author, 'borrowed': book.borrowed} for book in books]
    return jsonify(book_list)

@app.route("/admin_add_book", methods=["POST"])
def admin_add_book():
    data = request.get_json()
    name = data.get('name')
    author = data.get('author')

    if not name or not author:
        return jsonify({"error": "Missing required fields"}), 400

    new_book = Book(name=name, author=author)
    db.session.add(new_book)
    db.session.commit()

    return jsonify({"message": "Book added successfully"}), 201

@app.route("/admin/disable_book/<int:book_id>", methods=["POST"])
def disable_book(book_id):
    if 'user_name' not in session or session['user_name'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    book = Book.query.get(book_id)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    if BorrowedBook.query.filter_by(book_id=book_id, returned=False).first():
        return jsonify({"error": "Book is currently borrowed and cannot be disabled"}), 400

    book.disabled = True
    db.session.commit()

    return jsonify({"message": f"Book '{book.name}' has been disabled successfully"}), 200

@app.route("/admin/borrowed_books", methods=["GET"])
def get_admin_borrowed_books():
    if 'user_name' not in session or session['user_name'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    borrowed_books = db.session.query(BorrowedBook, Book, Customer).join(Book, BorrowedBook.book_id == Book.id).join(Customer, BorrowedBook.customer_id == Customer.id).filter(BorrowedBook.returned == False).all()
    borrowed_books_list = [
        {
            "book_id": borrowed_book.book_id,
            "book_name": book.name,
            "author": book.author,
            "borrowed_by": customer.name
        }
        for borrowed_book, book, customer in borrowed_books
    ]
    return jsonify(borrowed_books_list), 200

@app.route("/borrowed_books_by_customer", methods=["GET"])
def get_borrowed_books_by_customer():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    customer_id = session['user_id']
    borrowed_books = db.session.query(BorrowedBook, Book).join(Book).filter(BorrowedBook.customer_id == customer_id, BorrowedBook.returned == False, Book.disabled == False).all()
    borrowed_books_list = [
        {
            "borrowed_book_id": borrowed_book.id,
            "book_id": book.id,
            "book_name": book.name,
            "author": book.author,
        }
        for borrowed_book, book in borrowed_books
    ]
    return jsonify(borrowed_books_list), 200

@app.route("/admin_customers", methods=["GET"])
def get_active_customers():
    if 'user_name' not in session or session['user_name'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    customers = Customer.query.filter_by(disabled=False).all()
    customer_list = [{'id': customer.id, 'name': customer.name} for customer in customers]
    return jsonify(customer_list), 200

@app.route("/disable_customer/<int:customer_id>", methods=["POST"])
def disable_customer(customer_id):
    if 'user_name' not in session or session['user_name'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    customer.disabled = True
    db.session.commit()

    return jsonify({"message": f"Customer '{customer.name}' has been disabled successfully"}), 200


# Ensure tables are created
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
