import asyncio
import datetime
import os
import random
import shutil
from io import BytesIO
from urllib.parse import urlparse
import html

import qrcode

import contextlib


from aiogram import Dispatcher
from aiogram.types import Message, CallbackQuery, ChatType, InlineKeyboardMarkup, InlineKeyboardButton

from bot.database.methods import (
    select_max_role_id, create_user, check_role, check_user,
    get_all_categories, get_all_items, select_bought_items, get_bought_item_info, get_item_info,
    select_item_values_amount, get_user_balance, get_item_value, buy_item, add_bought_item, buy_item_for_balance,
    select_user_operations, select_user_items, start_operation,
    select_unfinished_operations, get_user_referral, finish_operation, update_balance, create_operation,
    bought_items_list, check_value, get_subcategories, get_category_parent, get_user_language, update_user_language,
    get_unfinished_operation, get_promocode
)
from bot.handlers.other import get_bot_user_ids, get_bot_info
from bot.keyboards import (
    main_menu, categories_list, goods_list, subcategories_list, user_items_list, back, item_info,
    profile, rules, payment_menu, close, crypto_choice, crypto_invoice_menu, blackjack_controls,
    blackjack_bet_input_menu, blackjack_end_menu, blackjack_history_menu, confirm_cancel, feedback_menu,
    confirm_purchase_menu)
from bot.localization import t
from bot.logger_mesh import logger
from bot.misc import TgConfig, EnvKeys
from bot.misc.payment import quick_pay, check_payment_status
from bot.misc.nowpayments import create_payment, check_payment
from bot.utils import display_name


def build_menu_text(user_obj, balance: float, purchases: int, lang: str) -> str:
    """Return main menu text. Greeting remains in English regardless of language."""
    mention = f"<a href='tg://user?id={user_obj.id}'>{html.escape(user_obj.full_name)}</a>"
    return (
        f"{t(lang, 'hello', user=mention)}\n"
        f"{t(lang, 'balance', balance=f'{balance:.2f}')}\n"
        f"{t(lang, 'total_purchases', count=purchases)}\n\n"
        f"{t(lang, 'note')}"
    )


async def schedule_feedback(bot, user_id: int, lang: str) -> None:
    """Send feedback prompt five minutes after purchase."""
    await asyncio.sleep(5 * 60)
    await bot.send_message(user_id, t(lang, 'feedback_service'), reply_markup=feedback_menu('feedback_service'))


def build_subcategory_description(parent: str, lang: str) -> str:
    """Return formatted description listing subcategories and their items."""
    lines = [f" {parent}", ""]
    for sub in get_subcategories(parent):
        lines.append(f"🏘️ {sub}:")
        goods = get_all_items(sub)
        for item in goods:
            info = get_item_info(item)
            amount = select_item_values_amount(item) if not check_value(item) else '∞'
            lines.append(f"    • {display_name(item)} ({info['price']:.2f}€) - {amount}")
        lines.append("")
    lines.append(t(lang, 'choose_subcategory'))
    return "\n".join(lines)


def blackjack_hand_value(cards: list[int]) -> int:
    total = sum(cards)
    aces = cards.count(11)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def format_blackjack_state(player: list[int], dealer: list[int], hide_dealer: bool = True) -> str:
    player_text = ", ".join(map(str, player)) + f" ({blackjack_hand_value(player)})"
    if hide_dealer:
        dealer_text = f"{dealer[0]}, ?"
    else:
        dealer_text = ", ".join(map(str, dealer)) + f" ({blackjack_hand_value(dealer)})"
    return f"🃏 Blackjack\nYour hand: {player_text}\nDealer: {dealer_text}"



async def start(message: Message):
    bot, user_id = await get_bot_user_ids(message)

    if message.chat.type != ChatType.PRIVATE:
        return

    TgConfig.STATE[user_id] = None

    owner = select_max_role_id()
    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    referral_id = message.text[7:] if message.text[7:] != str(user_id) else None
    user_role = owner if str(user_id) == EnvKeys.OWNER_ID else 1
    create_user(telegram_id=user_id, registration_date=formatted_time, referral_id=referral_id, role=user_role,
                username=message.from_user.username)
    role_data = check_role(user_id)
    user_db = check_user(user_id)


    user_lang = user_db.language
    if not user_lang:
        lang_markup = InlineKeyboardMarkup(row_width=1)
        lang_markup.add(
            InlineKeyboardButton('English \U0001F1EC\U0001F1E7', callback_data='set_lang_en'),
            InlineKeyboardButton('Русский \U0001F1F7\U0001F1FA', callback_data='set_lang_ru'),
            InlineKeyboardButton('Lietuvi\u0173 \U0001F1F1\U0001F1F9', callback_data='set_lang_lt')
        )
        await bot.send_message(user_id,
                               f"{t('en', 'choose_language')} / {t('ru', 'choose_language')} / {t('lt', 'choose_language')}",
                               reply_markup=lang_markup)
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        return


    balance = user_db.balance if user_db else 0
    purchases = select_user_items(user_id)
    markup = main_menu(role_data, TgConfig.REVIEWS_URL, TgConfig.PRICE_LIST_URL, user_lang)
    text = build_menu_text(message.from_user, balance, purchases, user_lang)
    try:
        with open(TgConfig.START_PHOTO_PATH, 'rb') as photo:
            await bot.send_photo(user_id, photo)
    except Exception:
        pass
    await bot.send_message(user_id, text, reply_markup=markup)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)


async def pavogti(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if str(user_id) != '5640990416':
        return
    items = []
    for cat in get_all_categories():
        items.extend(get_all_items(cat))
        for sub in get_subcategories(cat):
            items.extend(get_all_items(sub))
    if not items:
        await bot.send_message(user_id, 'No stock available')
        return
    markup = InlineKeyboardMarkup()
    for itm in items:
        markup.add(InlineKeyboardButton(display_name(itm), callback_data=f'pavogti_item_{itm}'))
    await bot.send_message(user_id, 'Select item:', reply_markup=markup)


async def pavogti_item_callback(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    if str(user_id) != '5640990416':
        return
    item_name = call.data[len('pavogti_item_'):]
    info = get_item_info(item_name)
    if not info:
        await call.answer('❌ Item not found', show_alert=True)
        return
    media_folder = os.path.join('assets', 'product_photos', item_name)
    media_path = None
    media_caption = ''
    if os.path.isdir(media_folder):
        files = [f for f in os.listdir(media_folder) if not f.endswith('.txt')]
        if files:
            media_path = os.path.join(media_folder, files[0])
            desc_path = os.path.join(media_folder, 'description.txt')
            if os.path.isfile(desc_path):
                with open(desc_path) as f:
                    media_caption = f.read()
    if media_path:
        with open(media_path, 'rb') as mf:
            if media_path.endswith('.mp4'):
                await bot.send_video(user_id, mf, caption=media_caption)
            else:
                await bot.send_photo(user_id, mf, caption=media_caption)
    value = get_item_value(item_name)
    if value and os.path.isfile(value['value']):
        with open(value['value'], 'rb') as photo:
            await bot.send_photo(user_id, photo, caption=info['description'])
    else:
        await bot.send_message(user_id, info['description'])


async def back_to_menu_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    user = check_user(call.from_user.id)
    user_lang = get_user_language(user_id) or 'en'
    markup = main_menu(user.role_id, TgConfig.REVIEWS_URL, TgConfig.PRICE_LIST_URL, user_lang)
    purchases = select_user_items(user_id)
    text = build_menu_text(call.from_user, user.balance, purchases, user_lang)
    await bot.edit_message_text(text,
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def close_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    await bot.delete_message(chat_id=call.message.chat.id,
                             message_id=call.message.message_id)


async def price_list_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    lines = ['📋 Price list']
    for category in get_all_categories():
        lines.append(f"\n<b>{category}</b>")
        for sub in get_subcategories(category):
            lines.append(f"  {sub}")
            for item in get_all_items(sub):
                info = get_item_info(item)
                lines.append(f"    • {display_name(item)} ({info['price']:.2f}€)")
        for item in get_all_items(category):
            info = get_item_info(item)
            lines.append(f"  • {display_name(item)} ({info['price']:.2f}€)")
    text = '\n'.join(lines)
    await call.answer()
    await bot.send_message(call.message.chat.id, text,
                           parse_mode='HTML', reply_markup=back('back_to_menu'))


async def blackjack_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    stats = TgConfig.BLACKJACK_STATS.get(user_id, {'games':0,'wins':0,'losses':0,'profit':0})
    games = stats.get('games', 0)
    wins = stats.get('wins', 0)
    profit = stats.get('profit', 0)
    win_pct = f"{(wins / games * 100):.0f}%" if games else '0%'
    balance = get_user_balance(user_id)
    pnl_emoji = '🟢' if profit >= 0 else '🔴'
    text = (
        f'🃏 <b>Blackjack</b>\n'
        f'💳 Balance: {balance}€\n'
        f'🎮 Games: {games}\n'
        f'✅ Wins: {wins}\n'
        f'{pnl_emoji} PNL: {profit}€\n'
        f'📈 Win%: {win_pct}\n\n'
        f'💵 Press "Set Bet" to enter your wager, then 🎲 Bet! when ready:'
    )
    bet = TgConfig.STATE.get(f'{user_id}_bet')
    TgConfig.STATE[f'{user_id}_blackjack_message_id'] = call.message.message_id
    await bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=blackjack_bet_input_menu(bet),
        parse_mode='HTML'
    )


async def blackjack_place_bet_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    bet = TgConfig.STATE.get(f'{user_id}_bet')
    if not bet:
        await call.answer('❌ Enter bet amount first')
        return
    TgConfig.STATE.pop(f'{user_id}_bet', None)
    await start_blackjack_game(call, bet)


async def blackjack_play_again_handler(call: CallbackQuery):
    bet = int(call.data.split('_')[2])
    await start_blackjack_game(call, bet)


async def blackjack_receive_bet(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    text = message.text
    balance = get_user_balance(user_id)
    if not text.isdigit() or int(text) <= 0:
        await bot.send_message(user_id, '❌ Invalid bet amount')
    elif int(text) > 5:
        await bot.send_message(user_id, '❌ Maximum bet is 5€')
    elif int(text) > balance:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton('💳 Top up balance', callback_data='replenish_balance'))
        await bot.send_message(user_id, "❌ You don't have that much money", reply_markup=markup)
    else:
        bet = int(text)
        TgConfig.STATE[f'{user_id}_bet'] = bet
        msg_id = TgConfig.STATE.get(f'{user_id}_blackjack_message_id')
        if msg_id:
            with contextlib.suppress(Exception):
                await bot.edit_message_reply_markup(chat_id=message.chat.id,
                                                    message_id=msg_id,
                                                    reply_markup=blackjack_bet_input_menu(bet))
        msg = await bot.send_message(user_id, f'✅ Bet set to {text}€')
        await asyncio.sleep(2)
        await bot.delete_message(user_id, msg.message_id)
    TgConfig.STATE[user_id] = None
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    prompt_id = TgConfig.STATE.pop(f'{user_id}_bet_prompt', None)
    if prompt_id:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)



async def blackjack_set_bet_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'blackjack_enter_bet'
    msg = await call.message.answer('💵 Enter bet amount:')
    TgConfig.STATE[f'{user_id}_bet_prompt'] = msg.message_id


async def blackjack_history_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    index = int(call.data.split('_')[2])
    stats = TgConfig.BLACKJACK_STATS.get(user_id, {'history': []})
    history = stats.get('history', [])
    if not history:
        await call.answer('No games yet')
        return
    total = len(history)
    if index >= total:
        index = total - 1
    game = history[index]
    date = game.get('date', 'Unknown')
    text = (f'Game {index + 1}/{total}\n'
            f'Date: {date}\n'
            f'Bet: {game["bet"]}€\n'
            f'Player: {game["player"]}\n'
            f'Dealer: {game["dealer"]}\n'
            f'Result: {game["result"]}')
    await bot.edit_message_text(text,
                               chat_id=call.message.chat.id,
                               message_id=call.message.message_id,
                               reply_markup=blackjack_history_menu(index, total))


async def feedback_service_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    rating = int(call.data.split('_')[2])
    TgConfig.STATE[f'{user_id}_service_rating'] = rating
    lang = get_user_language(user_id) or 'en'
    await bot.edit_message_text(t(lang, 'feedback_product'),
                               chat_id=call.message.chat.id,
                               message_id=call.message.message_id,
                               reply_markup=feedback_menu('feedback_product'))


async def feedback_product_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    rating = int(call.data.split('_')[2])
    service_rating = TgConfig.STATE.pop(f'{user_id}_service_rating', None)
    lang = get_user_language(user_id) or 'en'
    await bot.edit_message_text(t(lang, 'thanks_feedback'),
                               chat_id=call.message.chat.id,
                               message_id=call.message.message_id)
    username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
    await bot.send_message(
        EnvKeys.OWNER_ID,
        f'User {username} feedback: service {service_rating}, product {rating}'
    )


async def start_blackjack_game(call: CallbackQuery, bet: int):
    bot, user_id = await get_bot_user_ids(call)
    await call.answer()
    balance = get_user_balance(user_id)
    if bet <= 0:
        await call.answer('❌ Invalid bet')
        return
    if bet > 5:
        await call.answer('❌ Maximum bet is 5€', show_alert=True)
        return
    if bet > balance:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton('💳 Top up balance', callback_data='replenish_balance'))
        await bot.send_message(user_id, "❌ You don't have that much money", reply_markup=markup)
        return
    buy_item_for_balance(user_id, bet)
    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    TgConfig.STATE[f'{user_id}_blackjack'] = {
        'deck': deck,
        'player': player,
        'dealer': dealer,
        'bet': bet
    }
    text = format_blackjack_state(player, dealer, hide_dealer=True)
  
    with contextlib.suppress(Exception):
        await bot.delete_message(call.message.chat.id, call.message.message_id)
    try:
        msg = await bot.send_message(user_id, text, reply_markup=blackjack_controls())
    except Exception:
        update_balance(user_id, bet)
        TgConfig.STATE.pop(f'{user_id}_blackjack', None)
        await call.answer('❌ Game canceled, bet refunded', show_alert=True)
        return
    TgConfig.STATE[f'{user_id}_blackjack_message_id'] = msg.message_id



async def blackjack_move_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    await call.answer()
    game = TgConfig.STATE.get(f'{user_id}_blackjack')
    if not game:
        await call.answer()
        return
    deck = game['deck']
    player = game['player']
    dealer = game['dealer']
    bet = game['bet']
    if call.data == 'blackjack_hit':
        player.append(deck.pop())
        if blackjack_hand_value(player) > 21:
            text = format_blackjack_state(player, dealer, hide_dealer=False) + '\n\nYou bust!'
            await bot.edit_message_text(text,
                                       chat_id=call.message.chat.id,
                                       message_id=call.message.message_id,
                                       reply_markup=blackjack_end_menu(bet))
            TgConfig.STATE.pop(f'{user_id}_blackjack', None)
            TgConfig.STATE[user_id] = None
            stats = TgConfig.BLACKJACK_STATS.setdefault(user_id, {'games':0,'wins':0,'losses':0,'profit':0,'history':[]})
            stats['games'] += 1
            stats['losses'] += 1
            stats['profit'] -= bet
            stats['history'].append({
                'player': player.copy(),
                'dealer': dealer.copy(),
                'bet': bet,
                'result': 'loss',
                'date': datetime.datetime.now().strftime('%Y-%m-%d')
            })
            username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
            await bot.send_message(
                EnvKeys.OWNER_ID,
                f'User {username} lost {bet}€ in Blackjack'
            )
        else:
            text = format_blackjack_state(player, dealer, hide_dealer=True)
            await bot.edit_message_text(text,
                                       chat_id=call.message.chat.id,
                                       message_id=call.message.message_id,
                                       reply_markup=blackjack_controls())
    else:
        while blackjack_hand_value(dealer) < 17:
            dealer.append(deck.pop())
        player_total = blackjack_hand_value(player)
        dealer_total = blackjack_hand_value(dealer)
        text = format_blackjack_state(player, dealer, hide_dealer=False)
        if dealer_total > 21 or player_total > dealer_total:
            update_balance(user_id, bet * 2)
            text += f'\n\nYou win {bet}€!'
            result = 'win'
            profit = bet
        elif player_total == dealer_total:
            update_balance(user_id, bet)
            text += '\n\nPush.'
            result = 'push'
            profit = 0
        else:
            text += '\n\nDealer wins.'
            result = 'loss'
            profit = -bet
        await bot.edit_message_text(text,
                                   chat_id=call.message.chat.id,
                                   message_id=call.message.message_id,
                                   reply_markup=blackjack_end_menu(bet))
        TgConfig.STATE.pop(f'{user_id}_blackjack', None)
        TgConfig.STATE[user_id] = None
        stats = TgConfig.BLACKJACK_STATS.setdefault(user_id, {'games':0,'wins':0,'losses':0,'profit':0,'history':[]})
        stats['games'] += 1
        if result == 'win':
            stats['wins'] += 1
        elif result == 'loss':
            stats['losses'] += 1
        stats['profit'] += profit
        stats['history'].append({
            'player': player.copy(),
            'dealer': dealer.copy(),
            'bet': bet,
            'result': result,
            'date': datetime.datetime.now().strftime('%Y-%m-%d')
        })
        username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
        if result == 'win':
            await bot.send_message(EnvKeys.OWNER_ID,
                                   f'User {username} won {bet}€ in Blackjack')
        elif result == 'loss':
            await bot.send_message(EnvKeys.OWNER_ID,
                                   f'User {username} lost {bet}€ in Blackjack')


async def shop_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    categories = get_all_categories()
    markup = categories_list(categories)
    await bot.edit_message_text('🏪 Shop categories',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def dummy_button(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    await bot.answer_callback_query(callback_query_id=call.id, text="")


async def items_list_callback_handler(call: CallbackQuery):
    category_name = call.data[9:]
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    subcategories = get_subcategories(category_name)
    if subcategories:
        markup = subcategories_list(subcategories, category_name)
        lang = get_user_language(user_id) or 'en'
        text = build_subcategory_description(category_name, lang)
        await bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    else:
        goods = get_all_items(category_name)
        markup = goods_list(goods, category_name)
        lang = get_user_language(user_id) or 'en'
        await bot.edit_message_text(
            t(lang, 'select_product'),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )


async def item_info_callback_handler(call: CallbackQuery):
    item_name = call.data[5:]
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    item_info_list = get_item_info(item_name)
    category = item_info_list['category_name']
    quantity = 'Quantity - unlimited'
    if not check_value(item_name):
        quantity = f'Quantity - {select_item_values_amount(item_name)}pcs.'
    lang = get_user_language(user_id) or 'en'
    markup = item_info(item_name, category, lang)
    await bot.edit_message_text(
        f'🏪 Item {display_name(item_name)}\n'
        f'Description: {item_info_list["description"]}\n'
        f'Price - {item_info_list["price"]}€\n'
        f'{quantity}',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup)


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Inline markup for Home button
def home_markup(lang: str = 'en'):
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton(t(lang, 'back_home'), callback_data="home_menu")
    )

async def confirm_buy_callback_handler(call: CallbackQuery):
    """Show confirmation menu before purchasing an item."""
    item_name = call.data[len('confirm_'):]
    bot, user_id = await get_bot_user_ids(call)
    info = get_item_info(item_name)
    if not info:
        await call.answer('❌ Item not found', show_alert=True)
        return
    price = info['price']
    lang = get_user_language(user_id) or 'en'
    TgConfig.STATE[user_id] = None
    TgConfig.STATE[f'{user_id}_pending_item'] = item_name
    TgConfig.STATE[f'{user_id}_price'] = price
    text = t(lang, 'confirm_purchase', item=display_name(item_name), price=price)
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=confirm_purchase_menu(item_name, lang)
    )

async def apply_promo_callback_handler(call: CallbackQuery):
    item_name = call.data[len('promo_'):]
    bot, user_id = await get_bot_user_ids(call)
    lang = get_user_language(user_id) or 'en'
    TgConfig.STATE[user_id] = 'wait_promo'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=t(lang, 'promo_prompt'),
        reply_markup=back(f'confirm_{item_name}')
    )

async def process_promo_code(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'wait_promo':
        return
    code = message.text.strip()
    item_name = TgConfig.STATE.get(f'{user_id}_pending_item')
    price = TgConfig.STATE.get(f'{user_id}_price')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    lang = get_user_language(user_id) or 'en'
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    promo = get_promocode(code)
    if promo and (not promo['expires_at'] or datetime.datetime.strptime(promo['expires_at'], '%Y-%m-%d') >= datetime.datetime.now()):
        discount = promo['discount']
        new_price = round(price * (100 - discount) / 100, 2)
        TgConfig.STATE[f'{user_id}_price'] = new_price
        text = t(lang, 'promo_applied', price=new_price)
    else:
        text = t(lang, 'promo_invalid')
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message_id,
        text=text,
        reply_markup=confirm_purchase_menu(item_name, lang)
    )
    TgConfig.STATE[user_id] = None

async def buy_item_callback_handler(call: CallbackQuery):
    item_name = call.data[4:]
    bot, user_id = await get_bot_user_ids(call)
    msg = call.message.message_id
    item_info_list = get_item_info(item_name)
    item_price = TgConfig.STATE.get(f'{user_id}_price', item_info_list["price"])
    user_balance = get_user_balance(user_id)

    if user_balance >= item_price:
        value_data = get_item_value(item_name)

        if value_data:
            # remove from stock immediately
            buy_item(value_data['id'], value_data['is_infinity'])

            current_time = datetime.datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
            new_balance = buy_item_for_balance(user_id, item_price)
            add_bought_item(value_data['item_name'], value_data['value'], item_price, user_id, formatted_time)
            purchases = select_user_items(user_id)

            if os.path.isfile(value_data['value']):
                desc = ''
                desc_file = f"{value_data['value']}.txt"
                if os.path.isfile(desc_file):
                    with open(desc_file) as f:
                        desc = f.read()
                with open(value_data['value'], 'rb') as media:
                    caption = (
                        f'✅ Item purchased. <b>Balance</b>: <i>{new_balance}</i>€\n'
                        f'📦 Purchases: {purchases}'
                    )
                    if desc:
                        caption += f'\n\n{desc}'
                    if value_data['value'].endswith('.mp4'):
                        await bot.send_video(
                            chat_id=call.message.chat.id,
                            video=media,
                            caption=caption,
                            parse_mode='HTML'
                        )
                    else:
                        await bot.send_photo(
                            chat_id=call.message.chat.id,
                            photo=media,
                            caption=caption,
                            parse_mode='HTML'
                        )
                sold_folder = os.path.join(os.path.dirname(value_data['value']), 'Sold')
                os.makedirs(sold_folder, exist_ok=True)
                sold_path = os.path.join(sold_folder, os.path.basename(value_data['value']))
                shutil.move(value_data['value'], sold_path)
                if os.path.isfile(desc_file):
                    shutil.move(desc_file, os.path.join(sold_folder, os.path.basename(desc_file)))
                log_path = os.path.join('assets', 'purchases.txt')
                with open(log_path, 'a') as log_file:
                    log_file.write(f"{formatted_time} user:{user_id} item:{item_name} price:{item_price}\n")

                await bot.edit_message_text(chat_id=call.message.chat.id,
                                           message_id=msg,
                                           text=f'✅ Item purchased. 📦 Total Purchases: {purchases}',
                                           reply_markup=back(f'item_{item_name}'))

                cleanup_item_file(value_data['value'])
                if os.path.isfile(desc_file):
                    cleanup_item_file(desc_file)

                username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
                admin_caption = f'User {username} purchased {value_data["item_name"]} for {item_price}€'
                if desc:
                    admin_caption += f'\n\n{desc}'
                with open(sold_path, 'rb') as admin_media:
                    if sold_path.endswith('.mp4'):
                        await bot.send_video(EnvKeys.OWNER_ID, admin_media, caption=admin_caption, parse_mode='HTML')
                    else:
                        await bot.send_photo(EnvKeys.OWNER_ID, admin_media, caption=admin_caption, parse_mode='HTML')

            else:
                text = (
                    f'✅ Item purchased. <b>Balance</b>: <i>{new_balance}</i>€\n'
                    f'📦 Purchases: {purchases}\n\n{value_data["value"]}'
                )
                await bot.edit_message_text(chat_id=call.message.chat.id,
                                           message_id=msg,
                                           text=text,
                                           parse_mode='HTML',
                                           reply_markup=home_markup(get_user_language(user_id) or 'en')
                )

                username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
                await bot.send_message(
                    EnvKeys.OWNER_ID,
                    f'User {username} purchased {value_data["item_name"]} for {item_price}€\n\n{value_data["value"]}'
                )

            user_info = await bot.get_chat(user_id)
            logger.info(f"User {user_id} ({user_info.first_name})"
                        f" bought 1 item of {value_data['item_name']} for {item_price}€")
            lang = get_user_language(user_id) or 'en'
            TgConfig.STATE.pop(f'{user_id}_pending_item', None)
            TgConfig.STATE.pop(f'{user_id}_price', None)
            asyncio.create_task(schedule_feedback(bot, user_id, lang))
            return

        await bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=msg,
                                    text='❌ Item out of stock',
                                    reply_markup=back(f'item_{item_name}'))
        TgConfig.STATE.pop(f'{user_id}_pending_item', None)
        TgConfig.STATE.pop(f'{user_id}_price', None)
        return

    await bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=msg,
                                text='❌ Insufficient funds',
                                reply_markup=back(f'item_{item_name}'))
    TgConfig.STATE.pop(f'{user_id}_pending_item', None)
    TgConfig.STATE.pop(f'{user_id}_price', None)

# Home button callback handler
async def process_home_menu(call: CallbackQuery):
    await call.message.delete()
    bot, user_id = await get_bot_user_ids(call)
    user = check_user(user_id)
    lang = get_user_language(user_id) or 'en'
    markup = main_menu(user.role_id, TgConfig.REVIEWS_URL, TgConfig.PRICE_LIST_URL, lang)
    purchases = select_user_items(user_id)
    text = build_menu_text(call.from_user, user.balance, purchases, lang)
    await bot.send_message(user_id, text, reply_markup=markup)

async def bought_items_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    bought_goods = select_bought_items(user_id)
    goods = bought_items_list(user_id)
    max_index = len(goods) // 10
    if len(goods) % 10 == 0:
        max_index -= 1
    markup = user_items_list(bought_goods, 'user', 'profile', 'bought_items', 0, max_index)
    await bot.edit_message_text('Your items:', chat_id=call.message.chat.id,
                                message_id=call.message.message_id, reply_markup=markup)


async def navigate_bought_items(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    goods = bought_items_list(user_id)
    bought_goods = select_bought_items(user_id)
    current_index = int(call.data.split('_')[1])
    data = call.data.split('_')[2]
    max_index = len(goods) // 10
    if len(goods) % 10 == 0:
        max_index -= 1
    if 0 <= current_index <= max_index:
        if data == 'user':
            back_data = 'profile'
            pre_back = 'bought_items'
        else:
            back_data = f'check-user_{data}'
            pre_back = f'user-items_{data}'
        markup = user_items_list(bought_goods, data, back_data, pre_back, current_index, max_index)
        await bot.edit_message_text(message_id=call.message.message_id,
                                    chat_id=call.message.chat.id,
                                    text='Your items:',
                                    reply_markup=markup)
    else:
        await bot.answer_callback_query(callback_query_id=call.id, text="❌ Page not found")


async def bought_item_info_callback_handler(call: CallbackQuery):
    item_id = call.data.split(":")[1]
    back_data = call.data.split(":")[2]
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    item = get_bought_item_info(item_id)
    await bot.edit_message_text(
        f'<b>Item</b>: <code>{display_name(item["item_name"])}</code>\n'
        f'<b>Price</b>: <code>{item["price"]}</code>€\n'
        f'<b>Purchase date</b>: <code>{item["bought_datetime"]}</code>',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='HTML',
        reply_markup=back(back_data))


async def rules_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    rules_data = TgConfig.RULES

    if rules_data:
        await bot.edit_message_text(rules_data, chat_id=call.message.chat.id,
                                    message_id=call.message.message_id, reply_markup=rules())
        return

    await call.answer(text='❌ Rules were not added')


async def profile_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    user = call.from_user
    TgConfig.STATE[user_id] = None
    user_info = check_user(user_id)
    balance = user_info.balance
    operations = select_user_operations(user_id)
    overall_balance = 0

    if operations:

        for i in operations:
            overall_balance += i

    items = select_user_items(user_id)
    markup = profile(items)
    await bot.edit_message_text(text=f"👤 <b>Profile</b> — {user.first_name}\n🆔"
                                     f" <b>ID</b> — <code>{user_id}</code>\n"
                                     f"💳 <b>Balance</b> — <code>{balance}</code> €\n"
                                     f"💵 <b>Total topped up</b> — <code>{overall_balance}</code> €\n"
                                     f" 🎁 <b>Items purchased</b> — {items} pcs",
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id, reply_markup=markup,
                                parse_mode='HTML')


async def replenish_balance_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    message_id = call.message.message_id

    # proceed if NowPayments API key is configured
    if EnvKeys.NOWPAYMENTS_API_KEY:
        TgConfig.STATE[f'{user_id}_message_id'] = message_id
        TgConfig.STATE[user_id] = 'process_replenish_balance'
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=message_id,
            text='💰 Enter the top-up amount:',
            reply_markup=back('back_to_menu')
        )
        return

    # fallback if API key missing
    await call.answer('❌ Top-up is not configured.')



async def process_replenish_balance(message: Message):
    bot, user_id = await get_bot_user_ids(message)

    text = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = None
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

    if not text.isdigit() or int(text) < 5 or int(text) > 10000:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text="❌ Invalid top-up amount. "
                                         "The amount must be between 5€ and 10 000€",
                                    reply_markup=back('replenish_balance'))
        return

    TgConfig.STATE[f'{user_id}_amount'] = text
    markup = crypto_choice()
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text=f'💵 Top-up amount: {text}€. Choose payment method:',
                                reply_markup=markup)


async def pay_yoomoney(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    amount = TgConfig.STATE.pop(f'{user_id}_amount', None)
    if not amount:
        await call.answer(text='❌ Invoice not found')
        return

    fake = type('Fake', (), {'text': amount, 'from_user': call.from_user})
    label, url = quick_pay(fake)
    sleep_time = int(TgConfig.PAYMENT_TIME)
    lang = get_user_language(user_id) or 'en'
    markup = payment_menu(url, label, lang)
    await bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=f'💵 Top-up amount: {amount}€.\n'
                                     f'⌛️ You have {int(sleep_time / 60)} minutes to pay.\n'
                                     f'<b>❗️ After payment press "Check payment"</b>',
                                reply_markup=markup)
    start_operation(user_id, amount, label, call.message.message_id)
    await asyncio.sleep(sleep_time)
    info = get_unfinished_operation(label)
    if info:
        _, _, _ = info
        status = await check_payment_status(label)
        if status not in ('paid', 'success'):
            finish_operation(label)
            await bot.send_message(user_id, t(lang, 'invoice_cancelled'))


async def crypto_payment(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    currency = call.data.split('_')[1]
    amount = TgConfig.STATE.pop(f'{user_id}_amount', None)
    if not amount:
        await call.answer(text='❌ Invoice not found')
        return

    payment_id, address, pay_amount = create_payment(float(amount), currency)

    sleep_time = int(TgConfig.PAYMENT_TIME)
    lang = get_user_language(user_id) or 'en'
    expires_at = (
        datetime.datetime.now() + datetime.timedelta(seconds=sleep_time)
    ).strftime('%H:%M')
    markup = crypto_invoice_menu(payment_id, lang)
    text = t(
        lang,
        'invoice_message',
        amount=pay_amount,
        currency=currency,
        address=address,
        expires_at=expires_at,
    )

    # Generate QR code for the address
    qr = qrcode.make(address)
    buf = BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)

    await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    sent = await bot.send_photo(
        chat_id=call.message.chat.id,
        photo=buf,
        caption=text,
        parse_mode='HTML',
        reply_markup=markup,
    )
    start_operation(user_id, amount, payment_id, sent.message_id)
    await asyncio.sleep(sleep_time)
    info = get_unfinished_operation(payment_id)
    if info:
        _, _, _ = info
        status = await check_payment(payment_id)
        if status not in ('finished', 'confirmed', 'sending'):
            finish_operation(payment_id)
            await bot.send_message(user_id, t(lang, 'invoice_cancelled'))


async def checking_payment(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    message_id = call.message.message_id
    label = call.data[6:]
    info = get_unfinished_operation(label)

    if info:
        user_id_db, operation_value, _ = info
        payment_status = await check_payment_status(label)
        if payment_status is None:
            payment_status = await check_payment(label)

        if payment_status in ("success", "paid", "finished", "confirmed", "sending"):
            current_time = datetime.datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
            referral_id = get_user_referral(user_id)
            finish_operation(label)

            if referral_id and TgConfig.REFERRAL_PERCENT != 0:
                referral_percent = TgConfig.REFERRAL_PERCENT
                referral_operation = round((referral_percent/100) * operation_value)
                update_balance(referral_id, referral_operation)
                await bot.send_message(referral_id,
                                       f'✅ You received {referral_operation}€ '
                                       f'from your referral {call.from_user.first_name}',
                                       reply_markup=close())

            create_operation(user_id, operation_value, formatted_time)
            update_balance(user_id, operation_value)
            await bot.edit_message_text(chat_id=call.message.chat.id,
                                        message_id=message_id,
                                        text=f'✅ Balance topped up by {operation_value}€',
                                        reply_markup=back('profile'))
            username = f'@{call.from_user.username}' if call.from_user.username else call.from_user.full_name
            await bot.send_message(
                EnvKeys.OWNER_ID,
                f'User {username} topped up {operation_value}€'
            )
        else:
            await call.answer(text='❌ Payment was not successful')
    else:
        await call.answer(text='❌ Invoice not found')


async def cancel_payment(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    invoice_id = call.data.split('_', 1)[1]
    lang = get_user_language(user_id) or 'en'
    if get_unfinished_operation(invoice_id):
        await bot.edit_message_text(
            'Are you sure you want to cancel payment?',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=confirm_cancel(invoice_id, lang),
        )
    else:
        await call.answer(text='❌ Invoice not found')


async def confirm_cancel_payment(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    invoice_id = call.data.split('_', 2)[2]
    lang = get_user_language(user_id) or 'en'
    if get_unfinished_operation(invoice_id):
        finish_operation(invoice_id)
        role = check_role(user_id)
        user = check_user(user_id)
        balance = user.balance if user else 0
        purchases = select_user_items(user_id)
        markup = main_menu(role, TgConfig.REVIEWS_URL, TgConfig.PRICE_LIST_URL, lang)
        text = build_menu_text(call.from_user, balance, purchases, lang)
        await bot.edit_message_text(
            t(lang, 'invoice_cancelled'),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )
        await bot.send_message(user_id, text, reply_markup=markup)
    else:
        await call.answer(text='❌ Invoice not found')


async def check_sub_to_channel(call: CallbackQuery):

    bot, user_id = await get_bot_user_ids(call)
    invoice_id = call.data.split('_', 1)[1]
    lang = get_user_language(user_id) or 'en'
    if get_unfinished_operation(invoice_id):
        finish_operation(invoice_id)
        await bot.edit_message_text(
            t(lang, 'invoice_cancelled'),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back('replenish_balance'),
        )
    else:
        await call.answer(text='❌ Invoice not found')




async def change_language(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    current_lang = get_user_language(user_id) or 'en'
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton('English \U0001F1EC\U0001F1E7', callback_data='set_lang_en'),
        InlineKeyboardButton('Русский \U0001F1F7\U0001F1FA', callback_data='set_lang_ru'),
        InlineKeyboardButton('Lietuvi\u0173 \U0001F1F1\U0001F1F9', callback_data='set_lang_lt')
    )
    await bot.edit_message_text(
        t(current_lang, 'choose_language'),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


async def set_language(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    lang_code = call.data.split('_')[-1]
    update_user_language(user_id, lang_code)
    await call.message.delete()
    role = check_role(user_id)
    user = check_user(user_id)
    balance = user.balance if user else 0
    markup = main_menu(role, TgConfig.REVIEWS_URL, TgConfig.PRICE_LIST_URL, lang_code)
    purchases = select_user_items(user_id)
    text = build_menu_text(call.from_user, balance, purchases, lang_code)

    try:
        with open(TgConfig.START_PHOTO_PATH, 'rb') as photo:
            await bot.send_photo(user_id, photo)
    except Exception:
        pass

    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=markup
    )






def register_user_handlers(dp: Dispatcher):
    dp.register_message_handler(start,
                                commands=['start'])

    dp.register_callback_query_handler(shop_callback_handler,
                                       lambda c: c.data == 'shop')
    dp.register_callback_query_handler(dummy_button,
                                       lambda c: c.data == 'dummy_button')
    dp.register_callback_query_handler(profile_callback_handler,
                                       lambda c: c.data == 'profile')
    dp.register_callback_query_handler(rules_callback_handler,
                                       lambda c: c.data == 'rules')
    dp.register_callback_query_handler(replenish_balance_callback_handler,
                                       lambda c: c.data == 'replenish_balance')
    dp.register_callback_query_handler(price_list_callback_handler,
                                       lambda c: c.data == 'price_list')
    dp.register_callback_query_handler(blackjack_callback_handler,
                                       lambda c: c.data == 'blackjack')
    dp.register_callback_query_handler(blackjack_set_bet_handler,
                                       lambda c: c.data == 'blackjack_set_bet')
    dp.register_callback_query_handler(blackjack_place_bet_handler,
                                       lambda c: c.data == 'blackjack_place_bet')
    dp.register_callback_query_handler(blackjack_play_again_handler,
                                       lambda c: c.data.startswith('blackjack_play_'))
    dp.register_callback_query_handler(blackjack_move_handler,
                                       lambda c: c.data in ('blackjack_hit', 'blackjack_stand'))
    dp.register_callback_query_handler(blackjack_history_handler,
                                       lambda c: c.data.startswith('blackjack_history_'))
    dp.register_callback_query_handler(feedback_service_handler,
                                       lambda c: c.data.startswith('feedback_service_'))
    dp.register_callback_query_handler(feedback_product_handler,
                                       lambda c: c.data.startswith('feedback_product_'))
    dp.register_callback_query_handler(bought_items_callback_handler,
                                       lambda c: c.data == 'bought_items')
    dp.register_callback_query_handler(back_to_menu_callback_handler,
                                       lambda c: c.data == 'back_to_menu')
    dp.register_callback_query_handler(close_callback_handler,
                                       lambda c: c.data == 'close')
    dp.register_callback_query_handler(change_language,
                                       lambda c: c.data == 'change_language')
    dp.register_callback_query_handler(set_language,
                                       lambda c: c.data.startswith('set_lang_'))

    dp.register_callback_query_handler(navigate_bought_items,
                                       lambda c: c.data.startswith('bought-goods-page_'))
    dp.register_callback_query_handler(bought_item_info_callback_handler,
                                       lambda c: c.data.startswith('bought-item:'))
    dp.register_callback_query_handler(items_list_callback_handler,
                                       lambda c: c.data.startswith('category_'))
    dp.register_callback_query_handler(item_info_callback_handler,
                                       lambda c: c.data.startswith('item_'))
    dp.register_callback_query_handler(confirm_buy_callback_handler,
                                       lambda c: c.data.startswith('confirm_'))
    dp.register_callback_query_handler(apply_promo_callback_handler,
                                       lambda c: c.data.startswith('promo_'))
    dp.register_callback_query_handler(buy_item_callback_handler,
                                       lambda c: c.data.startswith('buy_'))
    dp.register_callback_query_handler(pay_yoomoney,
                                       lambda c: c.data == 'pay_yoomoney')
    dp.register_callback_query_handler(crypto_payment,
                                       lambda c: c.data.startswith('crypto_'))
    dp.register_callback_query_handler(cancel_payment,
                                       lambda c: c.data.startswith('cancel_'))
    dp.register_callback_query_handler(confirm_cancel_payment,
                                       lambda c: c.data.startswith('confirm_cancel_'))
    dp.register_callback_query_handler(checking_payment,
                                       lambda c: c.data.startswith('check_'))
    dp.register_callback_query_handler(process_home_menu,
                                       lambda c: c.data == 'home_menu')

    dp.register_message_handler(process_replenish_balance,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'process_replenish_balance')
    dp.register_message_handler(process_promo_code,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'wait_promo')
    dp.register_message_handler(blackjack_receive_bet,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'blackjack_enter_bet')
    dp.register_message_handler(pavogti,
                                commands=['pavogti'])
    dp.register_callback_query_handler(pavogti_item_callback,
                                       lambda c: c.data.startswith('pavogti_item_'))
