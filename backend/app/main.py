from datetime import datetime, timedelta, timezone
import os

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import engine, Base, SessionLocal
from . import model
from .schemas import (
    UserCreate,
    UserResponse,
    TransactionResponse
)


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not configured")


app = FastAPI(title="MiniPay API")

Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# JWT CONFIGURATION
# --------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login"
)


def create_access_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# --------------------------------------------------
# DATABASE DEPENDENCY
# --------------------------------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# CURRENT AUTHENTICATED USER
# --------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (JWTError, ValueError):
        raise credentials_exception

    user = (
        db.query(model.User)
        .filter(model.User.id == user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


# --------------------------------------------------
# HEALTH
# --------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# --------------------------------------------------
# REGISTER USER
# --------------------------------------------------

@app.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(model.User)
        .filter(model.User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Hash password
    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    new_user = model.User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# --------------------------------------------------
# LOGIN + CREATE JWT
# --------------------------------------------------

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # OAuth2 calls the email "username".
    # We use the username field to receive the user's email.

    existing_user = (
        db.query(model.User)
        .filter(model.User.email == form_data.username)
        .first()
    )

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Verify password
    password_correct = bcrypt.checkpw(
        form_data.password.encode("utf-8"),
        existing_user.password_hash.encode("utf-8")
    )

    if not password_correct:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Create JWT
    access_token = create_access_token(
        existing_user.id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": existing_user.id,
        "name": existing_user.name
    }


# --------------------------------------------------
# GET ALL USERS
# --------------------------------------------------

@app.get("/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db)
):
    return db.query(model.User).all()


# --------------------------------------------------
# GET USER BY ID
# --------------------------------------------------

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    user = (
        db.query(model.User)
        .filter(model.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user


# --------------------------------------------------
# ADD MONEY
# --------------------------------------------------

@app.post("/wallet/{user_id}/add-money")
def add_money(
    user_id: int,
    amount: int,
    current_user: model.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # User can only modify their own wallet
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own wallet"
        )

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == user_id)
        .first()
    )

    if not wallet:
        wallet = model.Wallet(
            user_id=user_id,
            balance_paise=0
        )

        db.add(wallet)

    wallet.balance_paise += amount

    db.commit()
    db.refresh(wallet)

    return {
        "message": "Money added successfully",
        "user_id": user_id,
        "balance_paise": wallet.balance_paise
    }


# --------------------------------------------------
# GET WALLET BALANCE
# --------------------------------------------------

@app.get("/wallet/{user_id}")
def get_wallet(
    user_id: int,
    current_user: model.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # User can only see their own wallet
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own wallet"
        )

    wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == user_id)
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    return {
        "user_id": user_id,
        "balance_paise": wallet.balance_paise
    }


# --------------------------------------------------
# TRANSFER MONEY
# --------------------------------------------------

@app.post("/transfer")
def transfer_money(
    sender_id: int,
    receiver_id: int,
    amount: int,
    current_user: model.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Authenticated user must be the sender
    if current_user.id != sender_id:
        raise HTTPException(
            status_code=403,
            detail="You can only transfer from your own account"
        )

    if sender_id == receiver_id:
        raise HTTPException(
            status_code=400,
            detail="Sender and receiver cannot be the same"
        )

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    sender = (
        db.query(model.User)
        .filter(model.User.id == sender_id)
        .first()
    )

    receiver = (
        db.query(model.User)
        .filter(model.User.id == receiver_id)
        .first()
    )

    if not sender:
        raise HTTPException(
            status_code=404,
            detail="Sender not found"
        )

    if not receiver:
        raise HTTPException(
            status_code=404,
            detail="Receiver not found"
        )

    sender_wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == sender_id)
        .first()
    )

    receiver_wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == receiver_id)
        .first()
    )

    if not sender_wallet:
        raise HTTPException(
            status_code=404,
            detail="Sender wallet not found"
        )

    if not receiver_wallet:
        receiver_wallet = model.Wallet(
            user_id=receiver_id,
            balance_paise=0
        )

        db.add(receiver_wallet)

    # Check balance
    if sender_wallet.balance_paise < amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance"
        )

    # Transfer money
    sender_wallet.balance_paise -= amount
    receiver_wallet.balance_paise += amount

    # Record transaction
    transaction = model.Transaction(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount_paise=amount,
        status="completed"
    )

    db.add(transaction)

    db.commit()
    db.refresh(transaction)

    return {
        "message": "Transfer successful",
        "transaction_id": transaction.id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "amount_paise": amount,
        "status": transaction.status
    }


# --------------------------------------------------
# GET TRANSACTIONS
# --------------------------------------------------

@app.get(
    "/transactions/{user_id}",
    response_model=list[TransactionResponse]
)
def get_transactions(
    user_id: int,
    current_user: model.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # User can only see their own transactions
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own transactions"
        )

    transactions = (
        db.query(model.Transaction)
        .filter(
            (model.Transaction.sender_id == user_id)
            |
            (model.Transaction.receiver_id == user_id)
        )
        .all()
    )

    return transactions