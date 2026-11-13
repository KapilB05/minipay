from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from .database import engine, Base, SessionLocal
from . import model
from .schemas import UserCreate


app = FastAPI(title="MiniPay API")

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = model.User(
        name=user.name,
        email=user.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(model.User).all()


@app.post("/wallets/{user_id}")
def create_wallet(user_id: int, db: Session = Depends(get_db)):
    user = (
        db.query(model.User)
        .filter(model.User.id == user_id)
        .first()
    )

    if not user:
        return {"error": "User not found"}

    existing_wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == user_id)
        .first()
    )

    if existing_wallet:
        return {"error": "Wallet already exists"}

    wallet = model.Wallet(
        user_id=user_id,
        balance_paise=0
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return wallet


@app.get("/wallets/{user_id}")
def get_wallet(user_id: int, db: Session = Depends(get_db)):
    wallet = (
        db.query(model.Wallet)
        .filter(model.Wallet.user_id == user_id)
        .first()
    )

    if not wallet:
        return {"error": "Wallet not found"}

    return wallet