from sqlalchemy.orm import Session
from models import User, Transaction, TransactionType

class UserService:
    @staticmethod
    def get_or_create_user(session: Session, user_id: int, username: str = None, first_name: str = None, referred_by_id: int = None) -> User:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            ref_id = referred_by_id if (referred_by_id and referred_by_id != user_id) else None
            user = User(id=user_id, username=username, first_name=first_name, balance=0.0, referred_by_id=ref_id)
            session.add(user)
            session.commit()
            session.refresh(user)
        else:
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if updated:
                session.commit()
                session.refresh(user)
        return user

    @staticmethod
    def add_balance(session: Session, user_id: int, amount: float, tx_type: TransactionType, description: str = None, commit: bool = True) -> User:
        if amount < 0:
            raise ValueError("Amount must be non-negative")
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if amount > 0:
            user.balance += amount
            tx = Transaction(user_id=user_id, amount=amount, type=tx_type, description=description)
            session.add(tx)

        if commit:
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def deduct_balance(session: Session, user_id: int, amount: float, tx_type: TransactionType, description: str = None, commit: bool = True) -> User:
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        if user.balance < amount:
            raise ValueError("Insufficient balance")

        user.balance -= amount
        tx = Transaction(user_id=user_id, amount=-amount, type=tx_type, description=description)
        session.add(tx)
        if commit:
            session.commit()
            session.refresh(user)
        return user
