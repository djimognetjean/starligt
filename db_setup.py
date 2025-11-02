# db_setup.py
import sqlite3

DATABASE_NAME = 'hotel_pos.db'

def prefill_rooms(cursor):
    """Vérifie et pré-remplit les chambres Starlight si la table est vide."""
    cursor.execute("SELECT COUNT(*) FROM chambres")
    if cursor.fetchone()[0] == 0:
        print("Base de données 'chambres' vide. Pré-remplissage...")
        
        # Données basées sur vos discussions
        rooms_to_add = [
            ('101', 'Élégance', 30000), ('104', 'Élégance', 30000),
            ('201', 'Élégance', 30000), ('204', 'Élégance', 30000),
            ('102', 'Deluxes', 50000), ('106', 'Deluxes', 50000), ('108', 'Deluxes', 50000),
            ('202', 'Deluxes', 50000), ('206', 'Deluxes', 50000), ('208', 'Deluxes', 50000),
            ('103', 'Premium', 40000), ('105', 'Premium', 40000), ('107', 'Premium', 40000),
            ('203', 'Premium', 40000), ('205', 'Premium', 40000), ('207', 'Premium', 40000),
            ('301', 'Suites', 70000), ('302', 'Suites', 70000),
            ('303', 'Suites', 70000), ('304', 'Suites', 70000),
            ('305', 'Confort', 20000), ('306', 'Confort', 20000),
            ('307', 'Confort', 20000), ('308', 'Confort', 20000)
        ]
        
        cursor.executemany("INSERT INTO chambres (numero, type_chambre, prix_nuit) VALUES (?, ?, ?)", rooms_to_add)
        print(f"{len(rooms_to_add)} chambres pré-remplies.")

# --- NOUVELLE FONCTION ---
def prefill_products(cursor):
    """Pré-remplit la table 'produits_services' avec des exemples d'articles."""
    cursor.execute("SELECT COUNT(*) FROM produits_services")
    if cursor.fetchone()[0] == 0:
        print("Base de données 'produits_services' vide. Pré-remplissage...")
        
        # Exemples de produits pour vos services (Pizzeria, Resto, Bar, Fast Food)
        products_to_add = [
            # Restauration
            ('Poulet DG', 5000, 'Consommation', 'Restauration'),
            ('Poisson Braisé', 4500, 'Consommation', 'Restauration'),
            ('Ndole (Crevettes)', 6000, 'Consommation', 'Restauration'),
            # Pizzeria
            ('Pizza Royale', 7000, 'Consommation', 'Pizzeria'),
            ('Pizza Margherita', 6000, 'Consommation', 'Pizzeria'),
            # Fast Food
            ('Burger Starlight', 3500, 'Consommation', 'Fast Food'),
            ('Frites Nature', 1500, 'Consommation', 'Fast Food'),
            # Bar / Glacier
            ('Jus Naturel', 1500, 'Consommation', 'Glacier'),
            ('Coca-Cola 33cl', 1000, 'Consommation', 'Bar'),
            ('Eau Minérale 1.5L', 1000, 'Consommation', 'Bar'),
            ('Bière Locale (33cl)', 1000, 'Consommation', 'Bar'),
            # Services (Spa, etc.)
            ('Accès Piscine (Jour)', 2000, 'Service Auxiliaire', 'Piscine'),
            ('Massage (30 min)', 10000, 'Service Auxiliaire', 'Spa'),
        ]
        
        cursor.executemany("""
            INSERT INTO produits_services (nom, prix_unitaire, type_vente, categorie) 
            VALUES (?, ?, ?, ?)
        """, products_to_add)
        print(f"{len(products_to_add)} produits/services pré-remplis.")


def create_database():
    """Crée la base de données SQLite et toutes les tables nécessaires."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # 1. Table des Utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_utilisateur TEXT UNIQUE NOT NULL,
                mot_de_passe_hash TEXT NOT NULL,
                role TEXT NOT NULL 
            )
        """)
        
        # 2. Table des Chambres
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chambres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                type_chambre TEXT NOT NULL,
                prix_nuit REAL NOT NULL
            )
        """)

        # 3. Table des Séjours
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sejours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chambre_id INTEGER NOT NULL,
                client_nom TEXT NOT NULL,
                date_checkin TEXT NOT NULL,
                date_checkout_prevue TEXT,
                date_checkout_reelle TEXT,
                solde_actuel REAL DEFAULT 0.0,
                statut TEXT DEFAULT 'Ouvert',
                FOREIGN KEY (chambre_id) REFERENCES chambres(id)
            )
        """)
        
        # 4. Table des Produits et Services (POS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produits_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                prix_unitaire REAL NOT NULL,
                type_vente TEXT NOT NULL,
                categorie TEXT NOT NULL
            )
        """)

        # 5. Table des Commandes (Tickets de caisse)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commandes_ventes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utilisateur_id INTEGER NOT NULL,
                stay_id INTEGER, -- NULL si vente directe
                total_net REAL NOT NULL,
                statut_paiement TEXT NOT NULL, -- Payé, Transféré
                date_heure TEXT NOT NULL,
                FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id),
                FOREIGN KEY (stay_id) REFERENCES sejours(id)
            )
        """)

        # 6. Table Lignes de Commande (Détail du ticket)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lignes_commande (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commande_id INTEGER NOT NULL,
                produit_id INTEGER NOT NULL,
                quantite INTEGER NOT NULL,
                prix_unitaire_vente REAL NOT NULL,
                FOREIGN KEY (commande_id) REFERENCES commandes_ventes(id),
                FOREIGN KEY (produit_id) REFERENCES produits_services(id)
            )
        """)

        # 7. Table des Paiements (Encaissements)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paiements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commande_id INTEGER NOT NULL,
                montant REAL NOT NULL,
                mode_paiement TEXT NOT NULL, -- Espèces, Carte, Mobile, Transfert Compte
                date_heure TEXT NOT NULL,
                FOREIGN KEY (commande_id) REFERENCES commandes_ventes(id)
            )
        """)
        
        # --- APPEL DES PRÉ-REMPLISSAGES ---
        prefill_rooms(cursor)
        prefill_products(cursor) # <-- AJOUTÉ
        
        conn.commit()
        print(f"Base de données '{DATABASE_NAME}' et tables créées/vérifiées.")

    except sqlite3.Error as e:
        print(f"Erreur SQLite : {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    create_database()