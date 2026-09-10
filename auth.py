"""Authentification par jetons JWT."""

import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request

from models import User, db
from ratelimit import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def make_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def user_from_token(token):
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    return db.session.get(User, payload.get("sub"))


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = user_from_token(_bearer_token())
        if user is None:
            return jsonify({"error": "Authentification requise."}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def current_user():
    return getattr(g, "current_user", None)


@auth_bp.post("/register")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Adresse e-mail invalide."}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return (
            jsonify({"error": f"Le mot de passe doit faire au moins {MIN_PASSWORD_LENGTH} caractères."}),
            400,
        )
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "Un compte existe déjà avec cet e-mail."}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"token": make_token(user), "user": user.to_dict()}), 201


@auth_bp.post("/login")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = db.session.query(User).filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "E-mail ou mot de passe incorrect."}), 401
    return jsonify({"token": make_token(user), "user": user.to_dict()})


@auth_bp.get("/me")
@require_auth
def me():
    return jsonify(current_user().to_dict())
