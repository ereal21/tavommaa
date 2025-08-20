import datetime
import os
import shutil
import datetime

from aiogram import Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import ChatNotFound


from bot.database.methods import (
    add_values_to_item,
    check_category,
    check_item,
    check_role,
    check_value,
    create_category,
    create_item,
    delete_category,
    delete_item,
    delete_only_items,
    get_all_categories,
    get_all_category_names,
    get_all_item_names,
    get_all_items,
    get_all_subcategories,
    get_user_count,
    select_admins,
    select_all_operations,
    select_all_orders,
    select_bought_item,
    select_count_bought_items,
    select_count_categories,
    select_count_goods,
    select_count_items,
    select_today_operations,
    select_today_orders,
    select_today_users,
    select_users_balance,
    update_category,
    update_item,
    create_promocode,
    delete_promocode,
    get_promocode,
    get_all_promocodes,
    update_promocode,
)
from bot.utils import generate_internal_name, display_name


from bot.utils.files import get_next_file_path
from bot.database.models import Permission
from bot.handlers.other import get_bot_user_ids
from bot.keyboards import (shop_management, goods_management, categories_management, back, item_management,
                           question_buttons, promo_codes_management, promo_expiry_keyboard, promo_codes_list,
                           promo_manage_actions)
from bot.logger_mesh import logger
from bot.misc import TgConfig


async def shop_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('⛩️ Shop management menu',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=shop_management())
        return
    await call.answer('Insufficient rights')


async def logs_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    file_path = 'bot.log'
    if role >= Permission.SHOP_MANAGE:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'rb') as document:
                await bot.send_document(chat_id=call.message.chat.id,
                                        document=document)
                return
        else:
            await call.answer(text="❗️ Kolkas nėra logų")
            return
    await call.answer('Insufficient rights')


async def goods_management_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🛒 Prekių valdymo meniu',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=goods_management())
        return
    await call.answer('Insufficient rights')


async def promo_management_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🏷 Promo codes menu',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=promo_codes_management())
        return
    await call.answer('Insufficient rights')


async def create_promo_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'promo_create_code'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    await bot.edit_message_text('Enter promo code:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=back('promo_management'))


async def promo_code_receive_code(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'promo_create_code':
        return
    code = message.text.strip()
    TgConfig.STATE[f'{user_id}_promo_code'] = code
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = 'promo_create_discount'
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await bot.edit_message_text('Enter discount percent:',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=back('promo_management'))


async def promo_code_receive_discount(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'promo_create_discount':
        return
    discount = int(message.text.strip())
    TgConfig.STATE[f'{user_id}_promo_discount'] = discount
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = 'promo_create_expiry_type'
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await bot.edit_message_text('Choose expiry type:',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=promo_expiry_keyboard('promo_management'))


async def promo_create_expiry_type_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    if TgConfig.STATE.get(user_id) != 'promo_create_expiry_type':
        return
    unit = call.data[len('promo_expiry_'):]
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    if unit == 'none':
        code = TgConfig.STATE.get(f'{user_id}_promo_code')
        discount = TgConfig.STATE.get(f'{user_id}_promo_discount')
        create_promocode(code, discount, None)
        TgConfig.STATE[user_id] = None
        await bot.edit_message_text('✅ Promo code created',
                                    chat_id=call.message.chat.id,
                                    message_id=message_id,
                                    reply_markup=back('promo_management'))
        admin_info = await bot.get_chat(user_id)
        logger.info(f"User {user_id} ({admin_info.first_name}) created promo code {code}")
        return
    TgConfig.STATE[f'{user_id}_promo_expiry_unit'] = unit
    TgConfig.STATE[user_id] = 'promo_create_expiry_number'
    await bot.edit_message_text(f'Enter number of {unit}:',
                                chat_id=call.message.chat.id,
                                message_id=message_id,
                                reply_markup=back('promo_management'))


async def promo_code_receive_expiry_number(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'promo_create_expiry_number':
        return
    number = int(message.text.strip())
    unit = TgConfig.STATE.get(f'{user_id}_promo_expiry_unit')
    code = TgConfig.STATE.get(f'{user_id}_promo_code')
    discount = TgConfig.STATE.get(f'{user_id}_promo_discount')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if number <= 0:
        expiry = None
    else:
        days = {'days': number, 'weeks': number * 7, 'months': number * 30}[unit]
        expiry_date = datetime.date.today() + datetime.timedelta(days=days)
        expiry = expiry_date.strftime('%Y-%m-%d')
    create_promocode(code, discount, expiry)
    TgConfig.STATE[user_id] = None
    TgConfig.STATE.pop(f'{user_id}_promo_expiry_unit', None)
    await bot.edit_message_text('✅ Promo code created',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=back('promo_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) created promo code {code}")


async def delete_promo_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    codes = [p.code for p in get_all_promocodes()]
    if codes:
        await bot.edit_message_text('Select promo code to delete:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=promo_codes_list(codes, 'delete_promo_code', 'promo_management'))
    else:
        await call.answer('No promo codes available', show_alert=True)


async def promo_code_delete_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    code = call.data[len('delete_promo_code_'):]
    delete_promocode(code)
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) deleted promo code {code}")
    codes = [p.code for p in get_all_promocodes()]
    if codes:
        await bot.edit_message_text('Select promo code to delete:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=promo_codes_list(codes, 'delete_promo_code', 'promo_management'))
    else:
        await bot.edit_message_text('✅ Promo code deleted',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back('promo_management'))


async def manage_promo_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    codes = [p.code for p in get_all_promocodes()]
    if codes:
        await bot.edit_message_text('Select promo code:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=promo_codes_list(codes, 'manage_promo_code', 'promo_management'))
    else:
        await call.answer('No promo codes available', show_alert=True)


async def promo_manage_select_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    code = call.data[len('manage_promo_code_'):]
    await bot.edit_message_text(f'Promo code: {code}',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=promo_manage_actions(code))


async def promo_manage_discount_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    code = call.data[len('promo_manage_discount_'):]
    TgConfig.STATE[user_id] = 'promo_manage_discount'
    TgConfig.STATE[f'{user_id}_promo_manage_code'] = code
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    await bot.edit_message_text('Enter new discount percent:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=back(f'manage_promo_code_{code}'))


async def promo_manage_receive_discount(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'promo_manage_discount':
        return
    code = TgConfig.STATE.get(f'{user_id}_promo_manage_code')
    new_discount = int(message.text.strip())
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    update_promocode(code, discount=new_discount)
    TgConfig.STATE[user_id] = None
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) updated promo code {code} discount to {new_discount}")
    await bot.edit_message_text('✅ Discount updated',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=promo_manage_actions(code))


async def promo_manage_expiry_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    code = call.data[len('promo_manage_expiry_'):]
    TgConfig.STATE[user_id] = 'promo_manage_expiry_type'
    TgConfig.STATE[f'{user_id}_promo_manage_code'] = code
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    await bot.edit_message_text('Choose expiry type:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=promo_expiry_keyboard(f'manage_promo_code_{code}'))


async def promo_manage_expiry_type_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    if TgConfig.STATE.get(user_id) != 'promo_manage_expiry_type':
        return
    unit = call.data[len('promo_expiry_'):]
    code = TgConfig.STATE.get(f'{user_id}_promo_manage_code')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    if unit == 'none':
        update_promocode(code, expires_at=None)
        TgConfig.STATE[user_id] = None
        admin_info = await bot.get_chat(user_id)
        logger.info(f"User {user_id} ({admin_info.first_name}) updated promo code {code} expiry")
        await bot.edit_message_text('✅ Expiry updated',
                                    chat_id=call.message.chat.id,
                                    message_id=message_id,
                                    reply_markup=promo_manage_actions(code))
        return
    TgConfig.STATE[f'{user_id}_promo_expiry_unit'] = unit
    TgConfig.STATE[user_id] = 'promo_manage_expiry_number'
    await bot.edit_message_text(f'Enter number of {unit}:',
                                chat_id=call.message.chat.id,
                                message_id=message_id,
                                reply_markup=back(f'manage_promo_code_{code}'))


async def promo_manage_receive_expiry_number(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if TgConfig.STATE.get(user_id) != 'promo_manage_expiry_number':
        return
    number = int(message.text.strip())
    unit = TgConfig.STATE.get(f'{user_id}_promo_expiry_unit')
    code = TgConfig.STATE.get(f'{user_id}_promo_manage_code')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if number <= 0:
        expiry = None
    else:
        days = {'days': number, 'weeks': number * 7, 'months': number * 30}[unit]
        expiry_date = datetime.date.today() + datetime.timedelta(days=days)
        expiry = expiry_date.strftime('%Y-%m-%d')
    update_promocode(code, expires_at=expiry)
    TgConfig.STATE[user_id] = None
    TgConfig.STATE.pop(f'{user_id}_promo_expiry_unit', None)
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) updated promo code {code} expiry")
    await bot.edit_message_text('✅ Expiry updated',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=promo_manage_actions(code))


async def promo_manage_delete_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    code = call.data[len('promo_manage_delete_'):]
    delete_promocode(code)
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) deleted promo code {code}")
    codes = [p.code for p in get_all_promocodes()]
    if codes:
        await bot.edit_message_text('Select promo code:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=promo_codes_list(codes, 'manage_promo_code', 'promo_management'))
    else:
        await bot.edit_message_text('✅ Promo code deleted',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back('promo_management'))


async def assign_photos_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    role = check_role(user_id)
    if role < Permission.SHOP_MANAGE:
        await call.answer('Insufficient rights')
        return
    TgConfig.STATE[user_id] = None
    categories = get_all_category_names()
    markup = InlineKeyboardMarkup()
    for cat in categories:
        markup.add(InlineKeyboardButton(cat, callback_data=f'assign_photo_cat_{cat}'))
    markup.add(InlineKeyboardButton('🔙 Back', callback_data='goods_management'))
    await bot.edit_message_text('Choose category:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def assign_photo_category_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    category = call.data[len('assign_photo_cat_'):]
    subcats = get_all_subcategories(category)
    markup = InlineKeyboardMarkup()
    for sub in subcats:
        markup.add(InlineKeyboardButton(sub, callback_data=f'assign_photo_sub_{sub}'))
    items = get_all_item_names(category)
    for item in items:
        markup.add(InlineKeyboardButton(display_name(item), callback_data=f'assign_photo_item_{item}'))
    markup.add(InlineKeyboardButton('🔙 Back', callback_data='assign_photos'))
    await bot.edit_message_text('Choose subcategory or item:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def assign_photo_subcategory_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    sub = call.data[len('assign_photo_sub_'):]
    items = get_all_item_names(sub)
    markup = InlineKeyboardMarkup()
    for item in items:
        markup.add(InlineKeyboardButton(display_name(item), callback_data=f'assign_photo_item_{item}'))
    markup.add(InlineKeyboardButton('🔙 Back', callback_data='assign_photos'))
    await bot.edit_message_text('Choose item:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def assign_photo_item_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    item = call.data[len('assign_photo_item_'):]
    TgConfig.STATE[user_id] = 'assign_photo_wait_media'
    TgConfig.STATE[f'{user_id}_item'] = item
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    await bot.edit_message_text('Send photo or video for this item:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=back('assign_photos'))


async def assign_photo_receive_media(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    item = TgConfig.STATE.get(f'{user_id}_item')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    if not item:
        return
    preview_folder = os.path.join('assets', 'product_photos', item)
    os.makedirs(preview_folder, exist_ok=True)
    if message.photo:
        file = message.photo[-1]
        ext = 'jpg'
    elif message.video:
        file = message.video
        ext = 'mp4'
    else:
        await bot.send_message(user_id, '❌ Send a photo or video')
        return
    stock_path = get_next_file_path(item, ext)
    await file.download(destination_file=stock_path)
    preview_path = os.path.join(preview_folder, os.path.basename(stock_path))
    shutil.copy(stock_path, preview_path)
    TgConfig.STATE[f'{user_id}_stock_path'] = stock_path
    TgConfig.STATE[user_id] = 'assign_photo_wait_desc'
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await bot.edit_message_text('Send description for this media:',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=back('assign_photos'))


async def assign_photo_receive_desc(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    item = TgConfig.STATE.get(f'{user_id}_item')
    stock_path = TgConfig.STATE.get(f'{user_id}_stock_path')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    if not item or not stock_path:
        return
    preview_folder = os.path.join('assets', 'product_photos', item)
    with open(os.path.join(preview_folder, 'description.txt'), 'w') as f:
        f.write(message.text)
    with open(f'{stock_path}.txt', 'w') as f:
        f.write(message.text)
    add_values_to_item(item, stock_path, False)
    TgConfig.STATE[user_id] = None
    TgConfig.STATE.pop(f'{user_id}_stock_path', None)
    TgConfig.STATE.pop(f'{user_id}_item', None)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await bot.edit_message_text('✅ Photo assigned',
                                chat_id=message.chat.id,
                                message_id=message_id,
                                reply_markup=goods_management())


async def categories_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🧾 Kategorijų valdymo meniu',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=categories_management())
        return
    await call.answer('Insufficient rights')


async def add_category_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'add_category'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('Enter category name',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("categories_management"))
        return
    await call.answer('Insufficient rights')


async def add_subcategory_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        categories = get_all_category_names()
        markup = InlineKeyboardMarkup()
        for cat in categories:
            markup.add(InlineKeyboardButton(cat, callback_data=f'choose_sub_parent_{cat}'))
        markup.add(InlineKeyboardButton('🔙 Back', callback_data='categories_management'))
        await bot.edit_message_text('Select parent category:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=markup)
        return
    await call.answer('Insufficient rights')


async def choose_subcategory_parent(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    parent = call.data[len('choose_sub_parent_'):]
    TgConfig.STATE[user_id] = 'add_subcategory_name'
    TgConfig.STATE[f'{user_id}_parent'] = parent
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    if not check_category(parent):
        await bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=message_id,
                                    text='❌ Parent category does not exist',
                                    reply_markup=back('categories_management'))
        TgConfig.STATE[user_id] = None
        return
    await bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=message_id,
                                text='Enter subcategory name',
                                reply_markup=back('categories_management'))


async def statistics_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        await bot.edit_message_text('Shop statistics:\n'
                                    '➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
                                    '<b>◽USERS</b>\n'
                                    f'◾️Users in last 24h: {select_today_users(today)}\n'
                                    f'◾️Total administrators: {select_admins()}\n'
                                    f'◾️Total users: {get_user_count()}\n'
                                    '➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
                                    '◽<b>FUNDS</b>\n'
                                    f'◾Sales in 24h: {select_today_orders(today)}€\n'
                                    f'◾Items sold for: {select_all_orders()}€\n'
                                    f'◾Top-ups in 24h: {select_today_operations(today)}€\n'
                                    f'◾Funds in system: {select_users_balance()}€\n'
                                    f'◾Total topped up: {select_all_operations()}€\n'
                                    '➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
                                    '◽<b>OTHER</b>\n'
                                    f'◾Items: {select_count_items()}pcs.\n'
                                    f'◾Positions: {select_count_goods()}pcs.\n'
                                    f'◾Categories: {select_count_categories()}pcs.\n'
                                    f'◾Items sold: {select_count_bought_items()}pcs.',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back('shop_management'),
                                    parse_mode='HTML')
        return
    await call.answer('Insufficient rights')


async def process_category_for_add(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    msg = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = None
    category = check_category(msg)
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if category:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Category not created (already exists)',
                                    reply_markup=back('categories_management'))
        return
    create_category(msg)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Category created',
                                reply_markup=back('categories_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'created new category "{msg}"')


async def process_subcategory_name(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    sub = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    parent = TgConfig.STATE.get(f'{user_id}_parent')
    TgConfig.STATE[user_id] = None
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if check_category(sub):
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Subcategory already exists',
                                    reply_markup=back('categories_management'))
        return
    create_category(sub, parent)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Subcategory created',
                                reply_markup=back('categories_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'created subcategory "{sub}" under "{parent}"')


async def delete_category_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'delete_category'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('Enter category name',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("categories_management"))
        return
    await call.answer('Insufficient rights')


async def process_category_for_delete(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    msg = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = None
    category = check_category(msg)
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if not category:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Category not deleted (does not exist)',
                                    reply_markup=back('categories_management'))
        return
    delete_category(msg)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Category deleted',
                                reply_markup=back('categories_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'deleted category "{category["name"]}"')


async def update_category_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    TgConfig.STATE[user_id] = 'check_category'
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('Enter category name to update:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("categories_management"))
        return
    await call.answer('Insufficient rights')


async def check_category_for_update(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    category_name = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    category = check_category(category_name)
    if not category:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Category cannot be updated (does not exist)',
                                    reply_markup=back('categories_management'))
        return
    TgConfig.STATE[user_id] = 'update_category_name'
    TgConfig.STATE[f'{user_id}_check_category'] = message.text
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Enter new category name:',
                                reply_markup=back('categories_management'))


async def check_category_name_for_update(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    category = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    old_name = TgConfig.STATE.get(f'{user_id}_check_category')
    TgConfig.STATE[user_id] = None
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    update_category(old_name, category)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text=f'✅ Category "{category}" updated successfully.',
                                reply_markup=back('categories_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'changed category "{old_name}" to "{category}"')


async def goods_settings_menu_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🛒 Pasirinkite veiksmą šiai prekei',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=item_management())
        return
    await call.answer('Insufficient rights')


async def add_item_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    TgConfig.STATE[user_id] = 'create_item_name'
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🏷️ Įveskite prekės pavadinimą',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("item-management"))
        return
    await call.answer('Insufficient rights')


async def check_item_name_for_add(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    item_name = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    item = check_item(item_name)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if item:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Item cannot be created (already exists)',
                                    reply_markup=back('item-management'))
        return
    TgConfig.STATE[user_id] = 'create_item_description'
    TgConfig.STATE[f'{user_id}_name'] = message.text
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Enter description for item:',
                                reply_markup=back('item-management'))


async def add_item_description(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    TgConfig.STATE[f'{user_id}_description'] = message.text
    TgConfig.STATE[user_id] = 'create_item_price'
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Enter price for item:',
                                reply_markup=back('item-management'))


async def add_item_price(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if not message.text.isdigit():
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='⚠️ Invalid price value.',
                                    reply_markup=back('item-management'))
        return
    TgConfig.STATE[f'{user_id}_price'] = message.text
    categories = get_all_category_names()
    markup = InlineKeyboardMarkup()
    for cat in categories:
        markup.add(InlineKeyboardButton(cat, callback_data=f'add_item_cat_{cat}'))
    markup.add(InlineKeyboardButton('🔙 Back', callback_data='item-management'))
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Select category:',
                                reply_markup=markup)


async def add_item_choose_category(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    categories = get_all_category_names()
    markup = InlineKeyboardMarkup()
    for cat in categories:
        markup.add(InlineKeyboardButton(cat, callback_data=f'add_item_cat_{cat}'))
    markup.add(InlineKeyboardButton('🔙 Back', callback_data='item-management'))
    await bot.edit_message_text('Select category:',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def add_item_category_selected(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    category = call.data[len('add_item_cat_'):]
    subs = get_all_subcategories(category)
    if subs:
        markup = InlineKeyboardMarkup()
        for sub in subs:
            markup.add(InlineKeyboardButton(sub, callback_data=f'add_item_sub_{sub}'))
        markup.add(InlineKeyboardButton('🔙 Back', callback_data='add_item_choose_cat'))
        await bot.edit_message_text('Select subcategory:',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=markup)
        return
    item_name = TgConfig.STATE.get(f'{user_id}_name')
    item_description = TgConfig.STATE.get(f'{user_id}_description')
    item_price = TgConfig.STATE.get(f'{user_id}_price')
    internal_name = generate_internal_name(item_name)
    create_item(internal_name, item_description, item_price, category, None)
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) created new item \"{internal_name}\"")
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton('✅ Yes', callback_data='add_item_more_yes'),
        InlineKeyboardButton('❌ No', callback_data='add_item_more_no')
    )
    await bot.edit_message_text('Add this product somewhere else?',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def add_item_subcategory_selected(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    sub = call.data[len('add_item_sub_'):]
    item_name = TgConfig.STATE.get(f'{user_id}_name')
    item_description = TgConfig.STATE.get(f'{user_id}_description')
    item_price = TgConfig.STATE.get(f'{user_id}_price')
    internal_name = generate_internal_name(item_name)
    create_item(internal_name, item_description, item_price, sub, None)
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) created new item \"{internal_name}\"")
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton('✅ Yes', callback_data='add_item_more_yes'),
        InlineKeyboardButton('❌ No', callback_data='add_item_more_no')
    )
    await bot.edit_message_text('Add this product somewhere else?',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup)


async def add_item_more_yes(call: CallbackQuery):
    await add_item_choose_category(call)


async def add_item_more_no(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    for key in ('name', 'description', 'price'):
        TgConfig.STATE.pop(f'{user_id}_{key}', None)
    TgConfig.STATE.pop(f'{user_id}_message_id', None)
    await bot.edit_message_text('✅ Items created, products added',
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=back('item-management'))


async def update_item_amount_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    TgConfig.STATE[user_id] = 'update_amount_of_item'
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🏷️ Įveskite prekės pavadinimą',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("item-management"))
        return
    await call.answer('Insufficient rights')


async def check_item_name_for_amount_upd(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    item_name = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    item = check_item(item_name)
    if not item:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Товар не может быть добавлен (Такой позиции не существует)',
                                    reply_markup=back('goods_management'))
    else:
        if check_value(item_name) is False:
            TgConfig.STATE[user_id] = 'add_new_amount'
            TgConfig.STATE[f'{user_id}_name'] = message.text
            await bot.edit_message_text(chat_id=message.chat.id,
                                        message_id=message_id,
                                        text='Send folder path with product files or list values separated by ;:',
                                        reply_markup=back('goods_management'))
        else:
            await bot.edit_message_text(chat_id=message.chat.id,
                                        message_id=message_id,
                                        text='❌ Товар не может быть добавлен (У данной позиции бесконечный товар)',
                                        reply_markup=back('goods_management'))


async def updating_item_amount(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if message.photo:
        file_path = get_next_file_path(TgConfig.STATE.get(f'{user_id}_name'))
        file_name = f"{TgConfig.STATE.get(f'{user_id}_name')}_{int(datetime.datetime.now().timestamp())}.jpg"
        file_path = os.path.join('assets', 'uploads', file_name)
        await message.photo[-1].download(destination_file=file_path)
        values_list = [file_path]
    else:
        if os.path.isdir(message.text):
            folder = message.text
            values_list = [os.path.join(folder, f) for f in os.listdir(folder)]
        else:
            values_list = message.text.split(';')
    TgConfig.STATE[user_id] = None
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    item_name = TgConfig.STATE.get(f'{user_id}_name')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    for i in values_list:
        add_values_to_item(item_name, i, False)
    group_id = TgConfig.GROUP_ID if TgConfig.GROUP_ID != -988765433 else None
    if group_id:
        try:
            await bot.send_message(chat_id=group_id,
                                   text=f'🎁 Upload\n'
                                        f'🏷️ Item: <b>{item_name}</b>'
                                        f'\n📦 Quantity: <b>{len(values_list)}</b>',
                                   parse_mode='HTML')
        except ChatNotFound:
            pass
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Товар добавлен',
                                reply_markup=back('goods_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'добавил товары к позиции "{item_name}" в количестве {len(values_list)} шт')


async def update_item_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'check_item_name'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🏷️ Įveskite prekės pavadinimą',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("goods_management"))
        return
    await call.answer('Insufficient rights')


async def check_item_name_for_update(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    item_name = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    item = check_item(item_name)
    if not item:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Item cannot be changed (does not exist)',
                                    reply_markup=back('goods_management'))
        return
    TgConfig.STATE[user_id] = 'update_item_name'
    TgConfig.STATE[f'{user_id}_old_name'] = message.text
    TgConfig.STATE[f'{user_id}_category'] = item['category_name']
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Введите новое имя для позиции:',
                                reply_markup=back('goods_management'))


async def update_item_name(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    TgConfig.STATE[f'{user_id}_name'] = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = 'update_item_description'
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Enter description for item:',
                                reply_markup=back('goods_management'))


async def update_item_description(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    TgConfig.STATE[f'{user_id}_description'] = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = 'update_item_price'
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='Enter price for item:',
                                reply_markup=back('goods_management'))


async def update_item_price(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    TgConfig.STATE[user_id] = None
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if not message.text.isdigit():
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='⚠️ Invalid price value.',
                                    reply_markup=back('goods_management'))
        return
    TgConfig.STATE[f'{user_id}_price'] = message.text
    item_old_name = TgConfig.STATE.get(f'{user_id}_old_name')
    if check_value(item_old_name) is False:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='Do you want to make unlimited goods?',
                                    reply_markup=question_buttons('change_make_infinity', 'goods_management'))
    else:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='Do you want to disable unlimited goods?',
                                    reply_markup=question_buttons('change_deny_infinity', 'goods_management'))


async def update_item_process(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    answer = call.data.split('_')
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    item_old_name = TgConfig.STATE.get(f'{user_id}_old_name')
    item_new_name = TgConfig.STATE.get(f'{user_id}_name')
    item_description = TgConfig.STATE.get(f'{user_id}_description')
    category = TgConfig.STATE.get(f'{user_id}_category')
    price = TgConfig.STATE.get(f'{user_id}_price')
    if answer[3] == 'no':
        TgConfig.STATE[user_id] = None
        delivery_desc = check_item(item_old_name).get('delivery_description')
        update_item(item_old_name, item_new_name, item_description, price, category, delivery_desc)
        await bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=message_id,
                                    text='✅ Item updated',
                                    reply_markup=back('goods_management'))
        admin_info = await bot.get_chat(user_id)
        logger.info(f"User {user_id} ({admin_info.first_name}) "
                    f'обновил позицию "{item_old_name}" на "{item_new_name}"')
    else:
        if answer[1] == 'make':
            await bot.edit_message_text(chat_id=call.message.chat.id,
                                        message_id=message_id,
                                        text='Enter item value:',
                                        reply_markup=back('goods_management'))
            TgConfig.STATE[f'{user_id}_change'] = 'make'
        elif answer[1] == 'deny':
            await bot.edit_message_text(chat_id=call.message.chat.id,
                                        message_id=message_id,
                                        text='Send folder path with product files or list values separated by ;:',
                                        reply_markup=back('goods_management'))
            TgConfig.STATE[f'{user_id}_change'] = 'deny'
    TgConfig.STATE[user_id] = 'apply_change'


async def update_item_infinity(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    if message.photo:
        file_path = get_next_file_path(TgConfig.STATE.get(f'{user_id}_old_name'))
        file_name = f"{TgConfig.STATE.get(f'{user_id}_old_name')}_{int(datetime.datetime.now().timestamp())}.jpg"
        file_path = os.path.join('assets', 'uploads', file_name)
        await message.photo[-1].download(destination_file=file_path)
        msg = file_path
    else:
        msg = message.text
    change = TgConfig.STATE[f'{user_id}_change']
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    item_old_name = TgConfig.STATE.get(f'{user_id}_old_name')
    item_new_name = TgConfig.STATE.get(f'{user_id}_name')
    item_description = TgConfig.STATE.get(f'{user_id}_description')
    category = TgConfig.STATE.get(f'{user_id}_category')
    price = TgConfig.STATE.get(f'{user_id}_price')
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if change == 'make':
        delete_only_items(item_old_name)
        add_values_to_item(item_old_name, msg, False)
    elif change == 'deny':
        delete_only_items(item_old_name)
        if os.path.isdir(msg):
            values_list = [os.path.join(msg, f) for f in os.listdir(msg)]
        else:
            values_list = msg.split(';')
        for i in values_list:
            add_values_to_item(item_old_name, i, False)
    TgConfig.STATE[user_id] = None
    delivery_desc = check_item(item_old_name).get('delivery_description')
    update_item(item_old_name, item_new_name, item_description, price, category, delivery_desc)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Item updated',
                                reply_markup=back('goods_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'обновил позицию "{item_old_name}" на "{item_new_name}"')


async def delete_item_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    TgConfig.STATE[user_id] = 'process_removing_item'
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text('🏷️ Įveskite prekės pavadinimą',
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=back("goods_management"))
        return
    await call.answer('Insufficient rights')


async def delete_str_item(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    msg = message.text
    TgConfig.STATE[user_id] = None
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    item = check_item(msg)
    await bot.delete_message(chat_id=message.chat.id,
                             message_id=message.message_id)
    if not item:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text='❌ Item not deleted (does not exist)',
                                    reply_markup=back('goods_management'))
        return
    delete_item(msg)
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=message_id,
                                text='✅ Item deleted',
                                reply_markup=back('goods_management'))
    admin_info = await bot.get_chat(user_id)
    logger.info(f"User {user_id} ({admin_info.first_name}) "
                f'удалил позицию "{msg}"')


async def show_bought_item_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'show_item'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role >= Permission.SHOP_MANAGE:
        await bot.edit_message_text(
            '🔍 Enter the unique ID of the purchased item',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back("goods_management"))
        return
    await call.answer('Insufficient rights')


async def process_item_show(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    msg = message.text
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = None
    item = select_bought_item(msg)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if item:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message_id,
            text=f'<b>Item</b>: <code>{item["item_name"]}</code>\n'
                 f'<b>Price</b>: <code>{item["price"]}</code>€\n'
                 f'<b>Purchase date</b>: <code>{item["bought_datetime"]}</code>\n'
                 f'<b>Buyer</b>: <code>{item["buyer_id"]}</code>\n'
                 f'<b>Unique operation ID</b>: <code>{item["unique_id"]}</code>\n'
                 f'<b>Value</b>:\n<code>{item["value"]}</code>',
            parse_mode='HTML',
            reply_markup=back('show_bought_item')
        )
        return
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message_id,
        text='❌ Item with the specified unique ID was not found',
        reply_markup=back('show_bought_item')
    )



def register_shop_management(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(statistics_callback_handler,
                                       lambda c: c.data == 'statistics')
    dp.register_callback_query_handler(goods_settings_menu_callback_handler,
                                       lambda c: c.data == 'item-management')
    dp.register_callback_query_handler(add_item_callback_handler,
                                       lambda c: c.data == 'add_item')
    dp.register_callback_query_handler(update_item_amount_callback_handler,
                                       lambda c: c.data == 'update_item_amount')
    dp.register_callback_query_handler(update_item_callback_handler,
                                       lambda c: c.data == 'update_item')
    dp.register_callback_query_handler(delete_item_callback_handler,
                                       lambda c: c.data == 'delete_item')
    dp.register_callback_query_handler(show_bought_item_callback_handler,
                                       lambda c: c.data == 'show_bought_item')
    dp.register_callback_query_handler(assign_photos_callback_handler,
                                       lambda c: c.data == 'assign_photos')
    dp.register_callback_query_handler(assign_photo_category_handler,
                                       lambda c: c.data.startswith('assign_photo_cat_'))
    dp.register_callback_query_handler(assign_photo_subcategory_handler,
                                       lambda c: c.data.startswith('assign_photo_sub_'))
    dp.register_callback_query_handler(assign_photo_item_handler,
                                       lambda c: c.data.startswith('assign_photo_item_'))
    dp.register_callback_query_handler(shop_callback_handler,
                                       lambda c: c.data == 'shop_management')
    dp.register_callback_query_handler(logs_callback_handler,
                                       lambda c: c.data == 'show_logs')
    dp.register_callback_query_handler(goods_management_callback_handler,
                                       lambda c: c.data == 'goods_management')
    dp.register_callback_query_handler(promo_management_callback_handler,
                                       lambda c: c.data == 'promo_management')
    dp.register_callback_query_handler(categories_callback_handler,
                                       lambda c: c.data == 'categories_management')
    dp.register_callback_query_handler(add_category_callback_handler,
                                       lambda c: c.data == 'add_category')
    dp.register_callback_query_handler(add_subcategory_callback_handler,
                                       lambda c: c.data == 'add_subcategory')
    dp.register_callback_query_handler(choose_subcategory_parent,
                                       lambda c: c.data.startswith('choose_sub_parent_'))
    dp.register_callback_query_handler(add_item_category_selected,
                                       lambda c: c.data.startswith('add_item_cat_'))
    dp.register_callback_query_handler(add_item_subcategory_selected,
                                       lambda c: c.data.startswith('add_item_sub_'))
    dp.register_callback_query_handler(add_item_more_yes,
                                       lambda c: c.data == 'add_item_more_yes')
    dp.register_callback_query_handler(add_item_more_no,
                                       lambda c: c.data == 'add_item_more_no')
    dp.register_callback_query_handler(add_item_choose_category,
                                       lambda c: c.data == 'add_item_choose_cat')
    dp.register_callback_query_handler(delete_category_callback_handler,
                                       lambda c: c.data == 'delete_category')
    dp.register_callback_query_handler(update_category_callback_handler,
                                       lambda c: c.data == 'update_category')
    dp.register_callback_query_handler(create_promo_callback_handler,
                                       lambda c: c.data == 'create_promo')
    dp.register_callback_query_handler(delete_promo_callback_handler,
                                       lambda c: c.data == 'delete_promo')
    dp.register_callback_query_handler(manage_promo_callback_handler,
                                       lambda c: c.data == 'manage_promo')
    dp.register_callback_query_handler(promo_code_delete_callback_handler,
                                       lambda c: c.data.startswith('delete_promo_code_'))
    dp.register_callback_query_handler(promo_manage_select_handler,
                                       lambda c: c.data.startswith('manage_promo_code_'))
    dp.register_callback_query_handler(promo_manage_discount_handler,
                                       lambda c: c.data.startswith('promo_manage_discount_'))
    dp.register_callback_query_handler(promo_manage_expiry_handler,
                                       lambda c: c.data.startswith('promo_manage_expiry_'))
    dp.register_callback_query_handler(promo_manage_delete_handler,
                                       lambda c: c.data.startswith('promo_manage_delete_'))
    dp.register_callback_query_handler(promo_create_expiry_type_handler,
                                       lambda c: c.data.startswith('promo_expiry_') and TgConfig.STATE.get(c.from_user.id) == 'promo_create_expiry_type')
    dp.register_callback_query_handler(promo_manage_expiry_type_handler,
                                       lambda c: c.data.startswith('promo_expiry_') and TgConfig.STATE.get(c.from_user.id) == 'promo_manage_expiry_type')

    dp.register_message_handler(check_item_name_for_amount_upd,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'update_amount_of_item')
    dp.register_message_handler(updating_item_amount,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'add_new_amount')
    dp.register_message_handler(check_item_name_for_add,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'create_item_name')
    dp.register_message_handler(add_item_description,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'create_item_description')
    dp.register_message_handler(add_item_price,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'create_item_price')
    dp.register_message_handler(assign_photo_receive_media,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'assign_photo_wait_media',
                                content_types=['photo', 'video'])
    dp.register_message_handler(assign_photo_receive_desc,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'assign_photo_wait_desc')
    dp.register_message_handler(check_item_name_for_update,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'check_item_name')
    dp.register_message_handler(update_item_name,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'update_item_name')
    dp.register_message_handler(update_item_description,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'update_item_description')
    dp.register_message_handler(update_item_price,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'update_item_price')
    dp.register_message_handler(delete_str_item,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'process_removing_item')
    dp.register_message_handler(process_item_show,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'show_item')
    dp.register_message_handler(process_category_for_add,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'add_category')
    dp.register_message_handler(process_subcategory_name,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'add_subcategory_name')
    dp.register_message_handler(process_category_for_delete,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'delete_category')
    dp.register_message_handler(check_category_for_update,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'check_category')
    dp.register_message_handler(check_category_name_for_update,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'update_category_name')
    dp.register_message_handler(update_item_infinity,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'apply_change')
    dp.register_message_handler(promo_code_receive_code,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'promo_create_code')
    dp.register_message_handler(promo_code_receive_discount,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'promo_create_discount')
    dp.register_message_handler(promo_code_receive_expiry_number,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'promo_create_expiry_number')
    dp.register_message_handler(promo_manage_receive_discount,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'promo_manage_discount')
    dp.register_message_handler(promo_manage_receive_expiry_number,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'promo_manage_expiry_number')

    dp.register_callback_query_handler(update_item_process,
                                       lambda c: c.data.startswith('change_'))
