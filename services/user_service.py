from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models import User, Transaction, TransactionType, WithdrawalRequest, WithdrawalStatus

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
            user = UserService.get_or_create_user(session, user_id)

        if amount > 0:
            user.balance += amount
            tx = Transaction(user_id=user_id, amount=amount, type=tx_type, description=description)
            session.add(tx)

        if commit:
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def create_withdrawal_request(session: Session, user_id: int, amount: float, method: str, account_details: str) -> WithdrawalRequest:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be greater than zero")

        UserService.deduct_balance(
            session=session,
            user_id=user_id,
            amount=amount,
            tx_type=TransactionType.WITHDRAWAL,
            description=f"Withdrawal request via {method}",
            commit=False
        )

        req = WithdrawalRequest(
            user_id=user_id,
            amount=amount,
            method=method,
            account_details=account_details,
            status=WithdrawalStatus.PENDING
        )
        session.add(req)
        session.commit()
        session.refresh(req)
        return req

    @staticmethod
    def get_pending_withdrawals(session: Session):
        return session.query(WithdrawalRequest).filter(WithdrawalRequest.status == WithdrawalStatus.PENDING).order_by(WithdrawalRequest.created_at.asc()).all()

    @staticmethod
    def get_user_withdrawals(session: Session, user_id: int):
        return session.query(WithdrawalRequest).filter(WithdrawalRequest.user_id == user_id).order_by(WithdrawalRequest.created_at.desc()).all()

    @staticmethod
    def approve_withdrawal(session: Session, withdrawal_id: int) -> WithdrawalRequest:
        req = session.query(WithdrawalRequest).filter(WithdrawalRequest.id == withdrawal_id).first()
        if not req:
            raise ValueError("Withdrawal request not found")
        if req.status != WithdrawalStatus.PENDING:
            raise ValueError("Withdrawal request is not pending")

        req.status = WithdrawalStatus.APPROVED
        req.processed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(req)
        return req

    @staticmethod
    def reject_withdrawal(session: Session, withdrawal_id: int, reason: str = None) -> WithdrawalRequest:
        req = session.query(WithdrawalRequest).filter(WithdrawalRequest.id == withdrawal_id).first()
        if not req:
            raise ValueError("Withdrawal request not found")
        if req.status != WithdrawalStatus.PENDING:
            raise ValueError("Withdrawal request is not pending")

        req.status = WithdrawalStatus.REJECTED
        req.rejection_reason = reason
        req.processed_at = datetime.now(timezone.utc)

        # Refund user balance
        UserService.add_balance(
            session=session,
            user_id=req.user_id,
            amount=req.amount,
            tx_type=TransactionType.DEPOSIT,
            description=f"Refund for rejected withdrawal #{req.id}",
            commit=False
        )

        session.commit()
        session.refresh(req)
        return req

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
