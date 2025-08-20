import sqlalchemy.exc
import random
from bot.database.models import User, ItemValues, Goods, Categories, BoughtGoods, \
    Operations, UnfinishedOperations, PromoCode
from bot.database import Database


def create_user(telegram_id: int, registration_date, referral_id, role: int = 1,
                language: str | None = None, username: str | None = None) -> None:
    session = Database().session
    try:
        user = session.query(User).filter(User.telegram_id == telegram_id).one()
        if user.username != username:
            user.username = username
            session.commit()
    except sqlalchemy.exc.NoResultFound:
        if referral_id != '':
            session.add(
                User(telegram_id=telegram_id, role_id=role, registration_date=registration_date,
                     referral_id=referral_id, language=language, username=username))
            session.commit()
        else:
            session.add(
                User(telegram_id=telegram_id, role_id=role, registration_date=registration_date,
                     referral_id=None, language=language, username=username))
            session.commit()


def create_item(item_name: str, item_description: str, item_price: int, category_name: str,
                delivery_description: str | None = None) -> None:
    session = Database().session
    session.add(
        Goods(name=item_name, description=item_description, price=item_price,
              category_name=category_name, delivery_description=delivery_description))
    session.commit()


def add_values_to_item(item_name: str, value: str, is_infinity: bool) -> None:
    session = Database().session
    if is_infinity is False:
        session.add(
            ItemValues(name=item_name, value=value, is_infinity=False))
    else:
        session.add(
            ItemValues(name=item_name, value=value, is_infinity=True))
    session.commit()


def create_category(category_name: str, parent: str | None = None) -> None:
    session = Database().session
    session.add(
        Categories(name=category_name, parent_name=parent))
    session.commit()


def create_operation(user_id: int, value: int, operation_time: str) -> None:
    session = Database().session
    session.add(
        Operations(user_id=user_id, operation_value=value, operation_time=operation_time))
    session.commit()


def start_operation(user_id: int, value: int, operation_id: str, message_id: int | None = None) -> None:
    session = Database().session
    session.add(
        UnfinishedOperations(user_id=user_id, operation_value=value, operation_id=operation_id, message_id=message_id))
    session.commit()


def add_bought_item(item_name: str, value: str, price: int, buyer_id: int,
                    bought_time: str) -> None:
    session = Database().session
    session.add(
        BoughtGoods(name=item_name, value=value, price=price, buyer_id=buyer_id, bought_datetime=bought_time,
                    unique_id=str(random.randint(1000000000, 9999999999))))
    session.commit()


def create_promocode(code: str, discount: int, expires_at: str | None) -> None:
    session = Database().session
    session.add(PromoCode(code=code, discount=discount, expires_at=expires_at, active=True))
    session.commit()
