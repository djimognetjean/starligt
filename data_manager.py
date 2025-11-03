# data_manager.py
import sqlite3
from datetime import datetime

DATABASE_NAME = 'hotel_pos.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

# --- GESTION DES CHAMBRES (CRUD) ---
def get_all_rooms():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, numero, type_chambre, prix_nuit FROM chambres ORDER BY numero")
    rooms = cursor.fetchall()
    conn.close()
    return rooms

def add_room_type(numero, type_chambre, prix_nuit):
    """(ADMIN) Ajoute une nouvelle chambre."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO chambres (numero, type_chambre, prix_nuit) VALUES (?, ?, ?)", 
                       (numero, type_chambre, prix_nuit))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False 
    finally:
        conn.close()

def delete_room(room_id):
    """(ADMIN) Supprime une chambre par ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # On vérifie si la chambre est occupée
        cursor.execute("SELECT COUNT(*) FROM sejours WHERE chambre_id = ? AND date_checkout_reelle IS NULL", (room_id,))
        if cursor.fetchone()[0] > 0:
            return False # Ne peut pas supprimer une chambre occupée
            
        cursor.execute("DELETE FROM chambres WHERE id = ?", (room_id,))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()

# --- GESTION DES PRODUITS (CRUD) ---
def get_all_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produits_services WHERE type_vente != 'Hébergement' ORDER BY categorie, nom")
    products = cursor.fetchall()
    conn.close()
    return products

def add_product(nom, prix_unitaire, type_vente, categorie):
    """(ADMIN) Ajoute un nouveau produit/service."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO produits_services (nom, prix_unitaire, type_vente, categorie) 
            VALUES (?, ?, ?, ?)
        """, (nom, prix_unitaire, type_vente, categorie))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()

def delete_product(product_id):
    """(ADMIN) Supprime un produit par ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Idéalement, on vérifierait si le produit est dans d'anciennes commandes
        # Mais pour l'instant, suppression simple
        cursor.execute("DELETE FROM produits_services WHERE id = ?", (product_id,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Le produit est lié à une ligne_commande
        return False 
    finally:
        conn.close()

# --- GESTION DES SÉJOURS (CHECK-IN / CHECK-OUT) ---
# (Toutes les fonctions de l'étape précédente restent ici - inchangées)
def get_active_stays():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT s.id, c.numero, s.client_nom, s.date_checkin, s.solde_actuel FROM sejours s JOIN chambres c ON s.chambre_id = c.id WHERE s.date_checkout_reelle IS NULL ORDER BY c.numero"
    cursor.execute(query)
    stays = cursor.fetchall()
    conn.close()
    return stays

def get_available_rooms():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM chambres WHERE id NOT IN (SELECT chambre_id FROM sejours WHERE date_checkout_reelle IS NULL) ORDER BY numero"
    cursor.execute(query)
    rooms = cursor.fetchall()
    conn.close()
    return rooms

def create_new_stay(room_id, client_name, date_checkout_prevue):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_checkin = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute("INSERT INTO sejours (chambre_id, client_nom, date_checkin, date_checkout_prevue, statut) VALUES (?, ?, ?, ?, 'Ouvert')", 
                       (room_id, client_name, date_checkin, date_checkout_prevue))
        conn.commit()
        return True
    except sqlite3.Error as e: return False
    finally: conn.close()

# --- MODULE REPORTING ---
def get_reporting_data():
    """Calcule les indicateurs clés pour le tableau de bord."""
    conn = get_db_connection()
    cursor = conn.cursor()

    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')

    results = {
        'taux_occupation': 0,
        'revenus_jour': 0,
        'revenus_mois': 0
    }

    try:
        # 1. Taux d'occupation
        cursor.execute("SELECT COUNT(*) FROM chambres")
        total_rooms = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sejours WHERE statut = 'Ouvert'")
        occupied_rooms = cursor.fetchone()[0]

        if total_rooms > 0:
            results['taux_occupation'] = (occupied_rooms / total_rooms) * 100

        # 2. Revenus du jour (Paiements directs POS + Check-outs finalisés)
        # On somme les paiements directs (non-transferts) et les soldes finaux des séjours clôturés
        cursor.execute("""
            SELECT SUM(montant) FROM paiements
            WHERE DATE(date_heure) = ? AND mode_paiement != 'Transfert Compte'
        """, (today_str,))
        revenus_pos_jour = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(solde_actuel) FROM sejours
            WHERE DATE(date_checkout_reelle) = ? AND statut = 'Clos'
        """, (today_str,))
        revenus_sejours_jour = cursor.fetchone()[0] or 0

        results['revenus_jour'] = revenus_pos_jour + revenus_sejours_jour

        # 3. Revenus du mois (Même logique que pour le jour)
        cursor.execute("""
            SELECT SUM(montant) FROM paiements
            WHERE STRFTIME('%Y-%m', date_heure) = ? AND mode_paiement != 'Transfert Compte'
        """, (month_str,))
        revenus_pos_mois = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(solde_actuel) FROM sejours
            WHERE STRFTIME('%Y-%m', date_checkout_reelle) = ? AND statut = 'Clos'
        """, (month_str,))
        revenus_sejours_mois = cursor.fetchone()[0] or 0

        results['revenus_mois'] = revenus_pos_mois + revenus_sejours_mois

    except sqlite3.Error as e:
        print(f"Erreur lors du calcul des rapports : {e}")
    finally:
        conn.close()

    return results

def get_stay_details(stay_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT s.id, c.numero, c.type_chambre, c.prix_nuit, s.client_nom, s.date_checkin, s.date_checkout_prevue, s.solde_actuel FROM sejours s JOIN chambres c ON s.chambre_id = c.id WHERE s.id = ? AND s.date_checkout_reelle IS NULL"
    cursor.execute(query, (stay_id,))
    details = cursor.fetchone()
    conn.close()
    return details

def get_stay_ordered_items(stay_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT p.nom, lc.quantite, lc.prix_unitaire_vente, (lc.quantite * lc.prix_unitaire_vente) AS sous_total FROM lignes_commande lc JOIN produits_services p ON lc.produit_id = p.id JOIN commandes_ventes cv ON lc.commande_id = cv.id WHERE cv.stay_id = ? AND cv.statut_paiement = 'Transféré' ORDER BY cv.date_heure"
    cursor.execute(query, (stay_id,))
    items = cursor.fetchall()
    conn.close()
    return items

def perform_checkout(stay_id, final_bill_amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_checkout_reelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute("UPDATE sejours SET date_checkout_reelle = ?, solde_actuel = ?, statut = 'Clos' WHERE id = ?", 
                       (date_checkout_reelle, final_bill_amount, stay_id))
        cursor.execute("UPDATE commandes_ventes SET statut_paiement = 'Payé' WHERE stay_id = ?", (stay_id,))
        conn.commit()
        return True
    except sqlite3.Error as e: return False
    finally: conn.close()

# --- GESTION DU POS ET DES COMMANDES ---
# (Inchangé)
def create_pos_order(user_id, cart_items, payment_type, stay_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    total_net = sum(item['prix'] * item['qte'] for item in cart_items)
    if payment_type == 'Transfert Compte' and stay_id:
        statut_paiement = 'Transféré'
    elif payment_type in ['Espèces', 'Carte', 'Mobile']:
        statut_paiement = 'Payé'
        stay_id = None 
    else: return False
    try:
        cursor.execute("INSERT INTO commandes_ventes (utilisateur_id, stay_id, total_net, statut_paiement, date_heure) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, stay_id, total_net, statut_paiement, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        commande_id = cursor.lastrowid
        lignes_a_inserer = []
        for item in cart_items:
            lignes_a_inserer.append((commande_id, item['id'], item['qte'], item['prix']))
        cursor.executemany("INSERT INTO lignes_commande (commande_id, produit_id, quantite, prix_unitaire_vente) VALUES (?, ?, ?, ?)", lignes_a_inserer)
        cursor.execute("INSERT INTO paiements (commande_id, montant, mode_paiement, date_heure) VALUES (?, ?, ?, ?)", 
                       (commande_id, total_net, payment_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        if statut_paiement == 'Transféré':
            cursor.execute("UPDATE sejours SET solde_actuel = solde_actuel + ? WHERE id = ?", (total_net, stay_id))
        conn.commit()
        return commande_id
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Erreur lors de la création de la commande POS : {e}")
        return False
    finally: conn.close()