from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password

from .firestore_client import _get_db
from .models import FirestoreUser

USERS_COLLECTION = "users"

class FirestoreAuthBackend(BaseBackend):
    """
    Custom authentication backend that talks directly to Firestore.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
            
        db = _get_db()
        # Query Firestore for a user with this email
        users_ref = db.collection(USERS_COLLECTION)
        query = users_ref.where("email", "==", username).limit(1)
        docs = list(query.stream())
        
        if not docs:
            return None
            
        user_doc = docs[0]
        user_data = user_doc.to_dict()
        
        # Verify password hash
        stored_password = user_data.get("password")
        if check_password(password, stored_password):
            user = FirestoreUser(id=user_doc.id, email=user_data.get("email"))
            user.password = stored_password
            return user
            
        return None

    def get_user(self, user_id):
        db = _get_db()
        doc_ref = db.collection(USERS_COLLECTION).document(str(user_id))
        doc = doc_ref.get()
        
        if doc.exists:
            user_data = doc.to_dict()
            user = FirestoreUser(id=doc.id, email=user_data.get("email"))
            user.password = user_data.get("password")
            return user
        return None
