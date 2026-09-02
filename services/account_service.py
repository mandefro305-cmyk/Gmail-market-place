from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from models import Account, AccountStatus, User, TransactionType
from services.user_service import UserService

class AccountService:
    @staticmethod
    def register_account(
        session: Session,
        creator_id: int,
        email: str,
        password: str,
        recovery_info: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Account:
        email = email.strip().lower()
        if "@" not in email:
            raise ValueError("Invalid email format")

        existing = session.query(Account).filter(
            Account.email == email,
            Account.status.in_([AccountStatus.PENDING_REVIEW, AccountStatus.APPROVED, AccountStatus.SOLD])
        ).first()
        if existing:
            raise ValueError("This Gmail account has already been registered.")

        account = Account(
            creator_id=creator_id,
            email=email,
            password=password.strip(),
            recovery_info=recovery_info.strip() if recovery_info else None,
            notes=notes.strip() if notes else None,
            status=AccountStatus.PENDING_REVIEW
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account

    @staticmethod
    def get_pending_accounts(session: Session) -> List[Account]:
        return session.query(Account).filter(Account.status == AccountStatus.PENDING_REVIEW).order_by(Account.created_at.asc()).all()

    @staticmethod
    def approve_account(
        session: Session,
        account_id: int,
        selling_price: float,
        creator_payout: float
    ) -> Account:
        if selling_price < 0 or creator_payout < 0:
            raise ValueError("Price and payout must be non-negative")

        account = session.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")
        if account.status != AccountStatus.PENDING_REVIEW:
            raise ValueError(f"Account cannot be reviewed because its status is {account.status}")

        account.status = AccountStatus.APPROVED
        account.selling_price = selling_price
        account.creator_payout = creator_payout
        account.reviewed_at = datetime.now(timezone.utc)

        UserService.add_balance(
            session=session,
            user_id=account.creator_id,
            amount=creator_payout,
            tx_type=TransactionType.PAYOUT,
            description=f"Payout for approved Gmail account ({account.email})",
            commit=False
        )

        session.commit()
        session.refresh(account)
        return account

    @staticmethod
    def reject_account(session: Session, account_id: int, reason: str) -> Account:
        account = session.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")
        if account.status != AccountStatus.PENDING_REVIEW:
            raise ValueError(f"Account cannot be reviewed because its status is {account.status}")

        account.status = AccountStatus.REJECTED
        account.rejection_reason = reason
        account.reviewed_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(account)
        return account

    @staticmethod
    def get_available_marketplace_accounts(session: Session) -> List[Account]:
        return session.query(Account).filter(Account.status == AccountStatus.APPROVED).order_by(Account.selling_price.asc()).all()

    @staticmethod
    def purchase_account(session: Session, buyer_id: int, account_id: int) -> Account:
        account = session.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")
        if account.status != AccountStatus.APPROVED:
            raise ValueError("Account is not available for purchase")

        buyer = session.query(User).filter(User.id == buyer_id).first()
        if not buyer:
            raise ValueError("Buyer not found")

        UserService.deduct_balance(
            session=session,
            user_id=buyer_id,
            amount=account.selling_price,
            tx_type=TransactionType.PURCHASE,
            description=f"Purchased Gmail account ({account.email})",
            commit=False
        )

        account.status = AccountStatus.SOLD
        account.buyer_id = buyer_id
        account.purchased_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(account)
        return account
