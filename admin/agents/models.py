from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
import uuid
from google.cloud import firestore
from .firestore_client import _get_db

class FirestoreUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if not user.id:
            user.id = str(uuid.uuid4())
            
        user.set_password(password)
        
        # Save directly to Firestore instead of calling user.save(using=self._db)
        db = _get_db()
        db.collection("users").document(user.id).set({
            "email": user.email,
            "password": user.password,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return user

class FirestoreUser(AbstractBaseUser):
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    objects = FirestoreUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override save to prevent Django from accessing the SQL database.
        Django's login() updates `last_login` and calls `save(update_fields=['last_login'])`.
        """
        if "update_fields" in kwargs and kwargs["update_fields"] == ["last_login"]:
            db = _get_db()
            db.collection("users").document(str(self.id)).update({
                "last_login": firestore.SERVER_TIMESTAMP
            })
            return
            
        # For any other rogue save calls, just ignore instead of crashing
        pass
        
    class Meta:
        managed = False  # Don't try to create a SQL table for this
        db_table = "users"