import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Account, AccountStatus, TransactionType, WithdrawalStatus
from services.user_service import UserService
from services.account_service import AccountService

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_user_service_balance(db_session):
    user = UserService.get_or_create_user(db_session, user_id=123, username="testuser", first_name="Test")
    assert user.id == 123
    assert user.balance == 0.0

    UserService.add_balance(db_session, user_id=123, amount=10.0, tx_type=TransactionType.DEPOSIT)
    assert user.balance == 10.0

    UserService.deduct_balance(db_session, user_id=123, amount=4.0, tx_type=TransactionType.WITHDRAWAL)
    assert user.balance == 6.0

def test_admin_task_creation_and_user_submission(db_session):
    # Admin creates task template
    task = AccountService.create_email_task(
        session=db_session,
        email="admintask@gmail.com",
        password="pass123task",
        recovery_info="rec@gmail.com",
        creator_payout=80.0,
        selling_price=250.0
    )
    assert task.status == AccountStatus.TASK_AVAILABLE
    assert task.creator_id is None

    # Normal user claims & submits task
    user = UserService.get_or_create_user(db_session, user_id=50, username="worker", first_name="Worker")
    submitted = AccountService.submit_task_completion(session=db_session, account_id=task.id, creator_id=user.id)
    assert submitted.status == AccountStatus.PENDING_REVIEW
    assert submitted.creator_id == 50

    # Admin approves submission and user earns creator_payout
    approved = AccountService.approve_account(
        session=db_session,
        account_id=submitted.id,
        selling_price=submitted.selling_price,
        creator_payout=submitted.creator_payout
    )
    assert approved.status == AccountStatus.APPROVED
    assert user.balance == 80.0

def test_account_service_lifecycle(db_session):
    seller = UserService.get_or_create_user(db_session, user_id=1, username="seller", first_name="Seller")
    buyer = UserService.get_or_create_user(db_session, user_id=2, username="buyer", first_name="Buyer")

    account = AccountService.register_account(
        session=db_session,
        creator_id=seller.id,
        email="test@gmail.com",
        password="password123"
    )
    assert account.status == AccountStatus.PENDING_REVIEW

    approved = AccountService.approve_account(
        session=db_session,
        account_id=account.id,
        selling_price=5.0,
        creator_payout=2.0
    )
    assert approved.status == AccountStatus.APPROVED
    assert seller.balance == 2.0

    # Test approving with zero payout
    zero_acc = AccountService.register_account(
        session=db_session,
        creator_id=seller.id,
        email="zero@gmail.com",
        password="password123"
    )
    approved_zero = AccountService.approve_account(
        session=db_session,
        account_id=zero_acc.id,
        selling_price=1.0,
        creator_payout=0.0
    )
    assert approved_zero.status == AccountStatus.APPROVED
    assert seller.balance == 2.0

    UserService.add_balance(db_session, user_id=buyer.id, amount=10.0, tx_type=TransactionType.DEPOSIT)
    purchased = AccountService.purchase_account(db_session, buyer_id=buyer.id, account_id=account.id)
    assert purchased.status == AccountStatus.SOLD
    assert buyer.balance == 5.0

def test_withdrawal_request_lifecycle(db_session):
    user = UserService.get_or_create_user(db_session, user_id=100, username="wuser", first_name="WUser")
    UserService.add_balance(db_session, user_id=100, amount=500.0, tx_type=TransactionType.DEPOSIT)
    assert user.balance == 500.0

    # Create withdrawal request via Telebirr
    req1 = UserService.create_withdrawal_request(
        session=db_session,
        user_id=100,
        amount=200.0,
        method="Telebirr",
        account_details="0911223344"
    )
    assert req1.status == WithdrawalStatus.PENDING
    assert user.balance == 300.0

    # Approve request
    app_req = UserService.approve_withdrawal(db_session, req1.id)
    assert app_req.status == WithdrawalStatus.APPROVED
    assert user.balance == 300.0

    # Create second request via CBE and reject it (should refund balance)
    req2 = UserService.create_withdrawal_request(
        session=db_session,
        user_id=100,
        amount=100.0,
        method="CBE",
        account_details="1000123456789"
    )
    assert user.balance == 200.0

    rej_req = UserService.reject_withdrawal(db_session, req2.id, reason="Invalid details")
    assert rej_req.status == WithdrawalStatus.REJECTED
    assert user.balance == 300.0
