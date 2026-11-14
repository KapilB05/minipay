from datetime import datetime, timedelta, timezone
import os

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from pydantic import BaseModel

from sqlalchemy.orm import Session

from .database import engine, Base, SessionLocal
from . import model
from .schemas import (
    UserCreate,
    UserResponse,
    TransactionResponse
)


# ==========================================================
# ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set in .env")


# ==========================================================
# FASTAPI APP
# ==========================================================

app = FastAPI(title="MiniPay API")


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# DATABASE
# ==========================================================

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ==========================================================
# JWT AUTHENTICATION
# ==========================================================

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

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
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

    user = db.query(model.User).filter(
        model.User.id == user_id
    ).first()

    if user is None:
        raise credentials_exception

    return user


# ==========================================================
# TRANSFER REQUEST
# ==========================================================

class TransferRequest(BaseModel):
    receiver_id: int
    amount_paise: int


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# ==========================================================
# CREATE USER
# ==========================================================

@app.post(
    "/users",
    response_model=UserResponse
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(model.User).filter(
        model.User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    password_hash = bcrypt.hashpw(
        user_data.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    new_user = model.User(
        name=user_data.name,
        email=user_data.email,
        password_hash=password_hash
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ==========================================================
# LOGIN
# ==========================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = db.query(model.User).filter(
        model.User.email == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    password_correct = bcrypt.checkpw(
        form_data.password.encode("utf-8"),
        user.password_hash.encode("utf-8")
    )

    if not password_correct:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name
    }


# ==========================================================
# GET ALL USERS
# ==========================================================

@app.get("/users")
def get_users(
    db: Session = Depends(get_db)
):

    users = db.query(model.User).all()

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
        for user in users
    ]


# ==========================================================
# GET SINGLE USER
# ==========================================================

@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(model.User).filter(
        model.User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email
    }


# ==========================================================
# ADD MONEY TO WALLET
# ==========================================================

@app.post("/wallet/{user_id}/add-money")
def add_money(
    user_id: int,
    amount_paise: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own wallet"
        )

    if amount_paise <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    wallet = db.query(model.Wallet).filter(
        model.Wallet.user_id == user_id
    ).first()

    if not wallet:
        wallet = model.Wallet(
            user_id=user_id,
            balance_paise=0
        )

        db.add(wallet)
        db.flush()

    wallet.balance_paise += amount_paise

    db.commit()
    db.refresh(wallet)

    return {
        "message": "Money added successfully",
        "user_id": user_id,
        "balance_paise": wallet.balance_paise
    }


# ==========================================================
# GET WALLET
# ==========================================================

@app.get("/wallet/{user_id}")
def get_wallet(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own wallet"
        )

    wallet = db.query(model.Wallet).filter(
        model.Wallet.user_id == user_id
    ).first()

    if not wallet:
        return {
            "user_id": user_id,
            "balance_paise": 0
        }

    return {
        "user_id": user_id,
        "balance_paise": wallet.balance_paise
    }


# ==========================================================
# TRANSFER MONEY
# ==========================================================

@app.post("/transfer")
def transfer_money(
    transfer_data: TransferRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    sender_id = current_user.id
    receiver_id = transfer_data.receiver_id
    amount_paise = transfer_data.amount_paise

    # ------------------------------------------
    # Validate amount
    # ------------------------------------------

    if amount_paise <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    # ------------------------------------------
    # Prevent self transfer
    # ------------------------------------------

    if sender_id == receiver_id:
        raise HTTPException(
            status_code=400,
            detail="You cannot transfer money to yourself"
        )

    # ------------------------------------------
    # Check receiver
    # ------------------------------------------

    receiver = db.query(model.User).filter(
        model.User.id == receiver_id
    ).first()

    if not receiver:
        raise HTTPException(
            status_code=404,
            detail="Receiver not found"
        )

    # ------------------------------------------
    # Get sender wallet
    # ------------------------------------------

    sender_wallet = db.query(model.Wallet).filter(
        model.Wallet.user_id == sender_id
    ).first()

    if not sender_wallet:
        raise HTTPException(
            status_code=400,
            detail="Sender wallet not found"
        )

    # ------------------------------------------
    # Check balance
    # ------------------------------------------

    if sender_wallet.balance_paise < amount_paise:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance"
        )

    # ------------------------------------------
    # Get or create receiver wallet
    # ------------------------------------------

    receiver_wallet = db.query(model.Wallet).filter(
        model.Wallet.user_id == receiver_id
    ).first()

    if not receiver_wallet:

        receiver_wallet = model.Wallet(
            user_id=receiver_id,
            balance_paise=0
        )

        db.add(receiver_wallet)
        db.flush()

    # ------------------------------------------
    # Transfer
    # ------------------------------------------

    sender_wallet.balance_paise -= amount_paise
    receiver_wallet.balance_paise += amount_paise

    # ------------------------------------------
    # Create transaction
    # ------------------------------------------

    transaction = model.Transaction(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount_paise=amount_paise,
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
        "amount_paise": amount_paise,
        "status": transaction.status
    }


# ==========================================================
# GET TRANSACTIONS
# ==========================================================

@app.get(
    "/transactions/{user_id}",
    response_model=list[TransactionResponse]
)
def get_transactions(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own transactions"
        )

    transactions = db.query(model.Transaction).filter(
        (model.Transaction.sender_id == user_id)
        |
        (model.Transaction.receiver_id == user_id)
    ).all()

    return transactions