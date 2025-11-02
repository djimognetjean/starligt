# user_manager.py
import sqlite3
import hashlib

DATABASE_NAME = 'hotel_pos.db'

def hash_password(password):
    """Hache le mot de passe pour le stocker en toute sécurité."""
    return hashlib.sha256(password.encode()).hexdigest()

def connect_db():
    """Établit la connexion à la base de données."""
    conn = sqlite3.connect(DATABASE_NAME)
    # Important: Activer row_factory pour obtenir les résultats comme des dictionnaires
    conn.row_factory = sqlite3.Row 
    return conn

def add_user(username, password, role):
    """Ajoute un nouvel utilisateur à la base de données."""
    conn = connect_db()
    cursor = conn.cursor()
    
    hashed_pass = hash_password(password)
    
    try:
        cursor.execute("""
            INSERT INTO utilisateurs (nom_utilisateur, mot_de_passe_hash, role) 
            VALUES (?, ?, ?)
        """, (username, hashed_pass, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # L'utilisateur existe déjà
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    """
    Vérifie les identifiants et retourne l'ID, le nom (renommé 'username') et le rôle.
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    hashed_pass = hash_password(password)
    
    try:
        # --- CORRECTION ICI ---
        # Sélectionne 'id', 'nom_utilisateur' (renommé en 'username'), et 'role'
        cursor.execute("""
            SELECT id, nom_utilisateur AS username, role 
            FROM utilisateurs 
            WHERE nom_utilisateur = ? AND mot_de_passe_hash = ?
        """, (username, hashed_pass))
        
        user_info = cursor.fetchone()
        
        if user_info:
            # Convertit l'objet Row en un dictionnaire simple
            # (ex: {'id': 1, 'username': 'admin', 'role': 'Admin'})
            return dict(user_info)
        else:
            return None # Échec de l'authentification
    finally:
        conn.close()

def check_for_admin_and_setup():
    """
    Vérifie s'il existe au moins un administrateur. 
    Si non, insère l'administrateur initial ('admin' / 'admin123').
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM utilisateurs WHERE role = 'Admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            print("\n--- CONFIGURATION INITIALE ---")
            print("CRÉATION DU PREMIER UTILISATEUR ADMINISTRATEUR")
            if add_user("admin", "admin123", "Admin"):
                print("Utilisateur 'admin' (Mot de passe: admin123) créé avec succès.")
            else:
                print("Erreur lors de la création de l'utilisateur Admin.")
    except sqlite3.Error as e:
        print(f"Erreur lors de la vérification de l'admin : {e}")
    finally:
        conn.close()
# Dans user_manager.py, AJOUTEZ CECI :

def get_all_users():
    """Récupère tous les utilisateurs sauf l'admin 'admin' pour l'affichage."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        # On exclut 'admin' pour qu'il ne puisse pas être supprimé
        cursor.execute("SELECT id, nom_utilisateur, role FROM utilisateurs WHERE nom_utilisateur != 'admin' ORDER BY role, nom_utilisateur")
        users = cursor.fetchall()
        return [dict(user) for user in users] # Convertit en liste de dictionnaires
    except sqlite3.Error as e:
        print(f"Erreur lors de la récupération des utilisateurs : {e}")
        return []
    finally:
        conn.close()

def delete_user(user_id):
    """Supprime un utilisateur par son ID."""
    # S'assurer qu'on ne supprime pas l'admin principal
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nom_utilisateur FROM utilisateurs WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user and user['nom_utilisateur'] == 'admin':
            return False # Sécurité : Ne pas supprimer l'admin
            
        cursor.execute("DELETE FROM utilisateurs WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0 # Vrai si la suppression a réussi
    except sqlite3.Error as e:
        print(f"Erreur lors de la suppression de l'utilisateur : {e}")
        return False
    finally:
        conn.close()
if __name__ == '__main__':
    # Vous pouvez exécuter ce fichier seul pour tester la création de l'admin
    check_for_admin_and_setup()