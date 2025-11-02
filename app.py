# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from weasyprint import HTML, CSS
import user_manager 
import data_manager 
import db_setup
import os
import json
from datetime import datetime, timedelta
from functools import wraps # Pour la sécurité Admin

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) 

# --- SÉCURITÉ : DÉCORATEUR POUR ADMIN ---
def admin_required(f):
    """Vérifie si l'utilisateur est connecté ET s'il a le rôle 'Admin'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'Admin':
            flash("Accès non autorisé. Vous devez être Administrateur.", 'error')
            return redirect(url_for('reception'))
        return f(*args, **kwargs)
    return decorated_function

# --- SÉCURITÉ : DÉCORATEUR POUR ACCÈS CONNECTÉ ---
def login_required(f):
    """Vérifie si l'utilisateur est connecté."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Vous devez être connecté pour voir cette page.", 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------------------------------------------------------
# --- GESTION DE L'AUTHENTIFICATION ---
# ----------------------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    """Affiche la page de connexion et gère la soumission du formulaire."""
    if 'user' in session: 
        return redirect(url_for('reception'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = user_manager.authenticate_user(username, password)
        
        if user:
            # Stocke les infos utilisateur (id, username, role) dans la session
            session['user'] = user 
            flash(f"Connexion réussie ! Bienvenue {user['username']}.", 'success')
            return redirect(url_for('reception'))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect.", 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Déconnecte l'utilisateur."""
    session.pop('user', None) 
    flash("Vous avez été déconnecté.", 'info')
    return redirect(url_for('login'))

# ----------------------------------------------------------------------
# --- MODULE RÉCEPTION & FACTURATION ---
# ----------------------------------------------------------------------

@app.route('/reception')
@login_required
def reception():
    """Page principale (Dashboard Réception)."""
    active_stays_data = data_manager.get_active_stays()
    
    return render_template(
        'reception.html', 
        user=session['user'], 
        active_stays=active_stays_data
    )

@app.route('/checkin/nouveau', methods=['GET'])
@login_required
def show_checkin_form():
    """Affiche la page avec le formulaire de check-in."""
    available_rooms_data = data_manager.get_available_rooms()
    default_checkout = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    return render_template(
        'checkin.html', 
        user=session['user'],
        available_rooms=available_rooms_data,
        default_checkout_date=default_checkout
    )

@app.route('/checkin/creer', methods=['POST'])
@login_required
def create_checkin():
    """Traite les données du formulaire de check-in."""
    room_id = request.form['chambre_id']
    client_name = request.form['client_nom']
    checkout_date = request.form['date_checkout_prevue']

    if not room_id or not client_name or not checkout_date:
        flash("Tous les champs sont requis.", 'error')
        return redirect(url_for('show_checkin_form'))

    success = data_manager.create_new_stay(room_id, client_name, checkout_date)
    
    if success:
        flash(f"Check-in de {client_name} effectué avec succès !", 'success')
    else:
        flash("Erreur lors de la création du séjour.", 'error')

    return redirect(url_for('reception'))

@app.route('/facture/<int:stay_id>', methods=['GET'])
@login_required
def show_billing(stay_id):
    """Affiche la page de facturation détaillée pour un séjour."""
    stay_details = data_manager.get_stay_details(stay_id)
    if not stay_details:
        flash("Erreur : Séjour non trouvé ou déjà clôturé.", 'error')
        return redirect(url_for('reception'))
    
    ordered_items = data_manager.get_stay_ordered_items(stay_id)
    # Le solde actuel contient déjà le coût des services transférés
    cost_services = stay_details['solde_actuel'] 

    checkin_dt = datetime.strptime(stay_details['date_checkin'], '%Y-%m-%d %H:%M:%S')
    checkout_dt_now = datetime.now()
    
    duration = checkout_dt_now - checkin_dt
    num_nights = duration.days
    
    # Logique de facturation : minimum 1 nuit, +1 si journée entamée
    if duration.seconds > 3600: # Marge de 1h
        num_nights += 1
    if num_nights == 0:
        num_nights = 1
    
    cost_room_stay = num_nights * stay_details['prix_nuit']
    
    # Le total est l'hébergement + les services déjà transférés (solde_actuel)
    total_bill = cost_room_stay + cost_services

    return render_template(
        'facture.html',
        user=session['user'],
        stay=stay_details,
        ordered_items=ordered_items,
        checkin_date=checkin_dt,
        checkout_date=checkout_dt_now,
        num_nights=num_nights,
        cost_room_stay=cost_room_stay,
        cost_services=cost_services,
        total_bill=total_bill
    )

@app.route('/facture/pdf/<int:stay_id>', methods=['GET'])
@login_required
def generate_invoice_pdf(stay_id):
    """Génère la facture en PDF pour un séjour."""
    stay_details = data_manager.get_stay_details(stay_id)
    if not stay_details:
        flash("Erreur : Séjour non trouvé.", 'error')
        return redirect(url_for('reception'))

    ordered_items = data_manager.get_stay_ordered_items(stay_id)
    cost_services = stay_details['solde_actuel']

    checkin_dt = datetime.strptime(stay_details['date_checkin'], '%Y-%m-%d %H:%M:%S')
    checkout_dt_now = datetime.now()

    duration = checkout_dt_now - checkin_dt
    num_nights = duration.days

    if duration.seconds > 3600:
        num_nights += 1
    if num_nights == 0:
        num_nights = 1

    cost_room_stay = num_nights * stay_details['prix_nuit']
    total_bill = cost_room_stay + cost_services

    # Rendre le template HTML avec les données
    html_out = render_template(
        'facture_pdf_a4.html',
        stay=stay_details,
        ordered_items=ordered_items,
        checkin_date=checkin_dt,
        checkout_date=checkout_dt_now,
        num_nights=num_nights,
        cost_room_stay=cost_room_stay,
        cost_services=cost_services,
        total_bill=total_bill
    )

    # Créer le PDF en mémoire
    pdf = HTML(string=html_out).write_pdf()

    # Créer une réponse HTTP avec le PDF
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Facture_{stay_details["client_nom"]}.pdf'

    return response

@app.route('/checkout/confirmer/<int:stay_id>', methods=['POST'])
@login_required
def confirm_checkout(stay_id):
    """Traite la confirmation du check-out et marque le séjour comme 'Clos'."""
    total_bill_paid = request.form['total_bill']
    
    success = data_manager.perform_checkout(stay_id, total_bill_paid)
    
    if success:
        flash("Check-out effectué avec succès ! La chambre est maintenant libre.", 'success')
    else:
        flash("Erreur lors de la finalisation du Check-out.", 'error')
        
    return redirect(url_for('reception'))

# ----------------------------------------------------------------------
# --- MODULE POINT DE VENTE (POS) ---
# ----------------------------------------------------------------------

@app.route('/pos', methods=['GET'])
@login_required
def pos_interface():
    """Affiche l'interface principale du POS."""
    products = data_manager.get_all_products()
    active_stays = data_manager.get_active_stays()
    
    return render_template(
        'pos.html',
        user=session['user'],
        products=products,
        active_stays=active_stays
    )

@app.route('/pos/submit', methods=['POST'])
@login_required
def submit_pos_order():
    """Traite la soumission du panier POS."""
    try:
        user_id = session['user']['id']
        cart_json = request.form['cart_data']
        payment_type = request.form['payment_type']
        stay_id = request.form.get('stay_id') 

        cart = json.loads(cart_json)
        
        if not cart:
            flash("Le panier est vide.", 'error')
            return redirect(url_for('pos_interface'))
            
        # Convertir le panier (dict JS) en liste d'items
        cart_items = []
        for item_id, details in cart.items():
            cart_items.append({
                'id': int(item_id),
                'nom': details['nom'],
                'prix': details['prix'],
                'qte': details['qte']
            })

        if payment_type == 'Transfert Compte':
            if not stay_id:
                flash("Veuillez sélectionner un séjour pour le transfert.", 'error')
                return redirect(url_for('pos_interface'))
        else:
            stay_id = None
            
        order_id = data_manager.create_pos_order(user_id, cart_items, payment_type, stay_id)

        if order_id:
            # Modifié pour inclure un lien d'impression
            print_link = url_for('generate_pos_ticket_pdf', order_id=order_id)
            flash(f"""
                Commande N°{order_id} validée avec succès !
                <a href='{print_link}' target='_blank' class='print-ticket-link'>Imprimer le Ticket</a>
            """, 'success')
        else:
            flash("Erreur lors de la création de la commande.", 'error')

    except Exception as e:
        flash(f"Une erreur est survenue : {e}", 'error')
    
    return redirect(url_for('pos_interface'))

@app.route('/pos/ticket/<int:order_id>')
@login_required
def generate_pos_ticket_pdf(order_id):
    """Génère un ticket de caisse POS en PDF."""
    order_details = data_manager.get_order_details(order_id)

    if not order_details:
        flash("Commande non trouvée.", 'error')
        return redirect(url_for('pos_interface'))

    # Rendre le template HTML avec les données
    html_out = render_template(
        'ticket_pos_80mm.html',
        order_details=order_details,
        datetime=datetime # Fournir le module datetime au template
    )

    # Créer le PDF en mémoire
    pdf = HTML(string=html_out).write_pdf()

    # Créer une réponse HTTP
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Ticket_{order_id}.pdf'

    return response

# ----------------------------------------------------------------------
# --- MODULE : ADMINISTRATION ---
# ----------------------------------------------------------------------

@app.route('/admin')
@admin_required # Sécurité ! Seul un admin peut voir cette page
def admin_dashboard():
    """Affiche le panneau d'administration pour gérer chambres, produits et utilisateurs."""
    all_rooms = data_manager.get_all_rooms()
    all_products = data_manager.get_all_products()
    all_users = user_manager.get_all_users() # Récupère les utilisateurs
    
    return render_template(
        'admin.html',
        user=session['user'],
        all_rooms=all_rooms,
        all_products=all_products,
        all_users=all_users # Passe les utilisateurs au template
    )

# --- Routes Chambres ---

@app.route('/admin/add_room', methods=['POST'])
@admin_required
def admin_add_room():
    """Traite l'ajout d'une nouvelle chambre."""
    try:
        numero = request.form['numero']
        type_chambre = request.form['type_chambre']
        prix_nuit = float(request.form['prix_nuit'])
        
        if data_manager.add_room_type(numero, type_chambre, prix_nuit):
            flash(f"Chambre {numero} ajoutée avec succès.", 'success')
        else:
            flash("Erreur : Le numéro de chambre existe déjà.", 'error')
    except Exception as e:
        flash(f"Erreur lors de l'ajout : {e}", 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_room/<int:room_id>')
@admin_required
def admin_delete_room(room_id):
    """Supprime une chambre."""
    if data_manager.delete_room(room_id):
        flash("Chambre supprimée avec succès.", 'success')
    else:
        flash("Erreur : Impossible de supprimer une chambre occupée.", 'error')
    return redirect(url_for('admin_dashboard'))

# --- Routes Produits POS ---

@app.route('/admin/add_product', methods=['POST'])
@admin_required
def admin_add_product():
    """Traite l'ajout d'un nouveau produit POS."""
    try:
        nom = request.form['nom']
        prix = float(request.form['prix_unitaire'])
        categorie = request.form['categorie']
        type_vente = request.form['type_vente']
        
        if data_manager.add_product(nom, prix, type_vente, categorie):
            flash(f"Produit '{nom}' ajouté avec succès.", 'success')
        else:
            flash("Erreur lors de l'ajout du produit.", 'error')
    except Exception as e:
        flash(f"Erreur lors de l'ajout : {e}", 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<int:product_id>')
@admin_required
def admin_delete_product(product_id):
    """Supprime un produit POS."""
    if data_manager.delete_product(product_id):
        flash("Produit supprimé avec succès.", 'success')
    else:
        flash("Erreur : Impossible de supprimer ce produit (peut-être lié à d'anciennes commandes).", 'error')
    return redirect(url_for('admin_dashboard'))

# --- Routes Utilisateurs ---

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def admin_add_user():
    """Traite l'ajout d'un nouvel utilisateur."""
    try:
        username = request.form['nom_utilisateur']
        password = request.form['mot_de_passe']
        role = request.form['role']
        
        if not username or not password or not role:
            flash("Tous les champs sont requis.", 'error')
            return redirect(url_for('admin_dashboard'))

        if user_manager.add_user(username, password, role):
            flash(f"Utilisateur '{username}' ({role}) créé avec succès.", 'success')
        else:
            flash("Erreur : Ce nom d'utilisateur existe déjà.", 'error')
            
    except Exception as e:
        flash(f"Erreur lors de la création de l'utilisateur : {e}", 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    """Supprime un utilisateur."""
    
    if 'user' in session and session['user']['id'] == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", 'error')
        return redirect(url_for('admin_dashboard'))
        
    if user_manager.delete_user(user_id):
        flash("Utilisateur supprimé avec succès.", 'success')
    else:
        flash("Erreur : Impossible de supprimer cet utilisateur (il s'agit peut-être de l'admin principal).", 'error')
        
    return redirect(url_for('admin_dashboard'))

# ----------------------------------------------------------------------
# --- DÉMARRAGE DE L'APPLICATION ---
# ----------------------------------------------------------------------

if __name__ == '__main__':
    # Vérifie et crée l'utilisateur 'admin' si nécessaire
    user_manager.check_for_admin_and_setup()
    
    # Lance le serveur web
    print("Serveur démarré. Ouvrez http://127.0.0.1:5000/ dans votre navigateur.")
    app.run(debug=True, host='0.0.0.0', port=5000)