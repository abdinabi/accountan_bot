import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import asyncpg
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ==== КНОПКИ ====
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Доход"), KeyboardButton(text="💸 Расход")],
        [KeyboardButton(text="📊 Баланс"), KeyboardButton(text="🗓 Остатки по периодам")]
    ],
    resize_keyboard=True
)

user_state = {}  # chat_id -> "income"/"expense"

# ==== Подключение к БД ====
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    return conn

async def init_table(conn, chat_id):
    table_name = f"transactions_{str(chat_id).replace('-', '')}"
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            type TEXT,
            amount REAL,
            category TEXT,
            date TIMESTAMP DEFAULT NOW()
        )
    """)
    return table_name

# ==== БОТ ====
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = await init_db()
    await init_table(conn, message.chat.id)
    await conn.close()
    await message.answer("Привет! Я бот для учёта доходов и расходов 💵", reply_markup=main_kb)

@dp.message(F.text == "💰 Доход")
async def income_start(message: types.Message):
    user_state[message.chat.id] = "income"
    await message.answer("Введите сумму и категорию (например: 5000 Зарплата)")

@dp.message(F.text == "💸 Расход")
async def expense_start(message: types.Message):
    user_state[message.chat.id] = "expense"
    await message.answer("Введите сумму и категорию (например: 1200 Продукты)")

@dp.message(F.text == "📊 Баланс")
async def show_balance(message: types.Message):
    conn = await init_db()
    table = await init_table(conn, message.chat.id)

    total_income = await conn.fetchval(f"SELECT SUM(amount) FROM {table} WHERE type='income'")
    total_expense = await conn.fetchval(f"SELECT SUM(amount) FROM {table} WHERE type='expense'")
    await conn.close()

    balance = (total_income or 0) - (total_expense or 0)
    await message.answer(f"💵 Текущий баланс: {balance:.2f} ₸")

@dp.message(F.text == "🗓 Остатки по периодам")
async def monthly_stats(message: types.Message):
    conn = await init_db()
    table = await init_table(conn, message.chat.id)

    rows = await conn.fetch(f"""
        SELECT to_char(date, 'YYYY-MM') as period,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM {table}
        GROUP BY period
        ORDER BY period
    """)
    await conn.close()

    if not rows:
        await message.answer("Данных пока нет 📭")
        return

    text = ""
    for row in rows:
        balance = (row['income'] or 0) - (row['expense'] or 0)
        text += f"📅 {row['period']}\nДоход: +{row['income']:.2f} ₸\nРасход: -{row['expense']:.2f} ₸\nОстаток: {balance:.2f} ₸\n\n"
    await message.answer(text)

@dp.message()
async def handle_amount(message: types.Message):
    if message.chat.id not in user_state:
        return

    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0])
        category = parts[1] if len(parts) > 1 else "Без категории"

        t_type = user_state.pop(message.chat.id)
        conn = await init_db()
        table = await init_table(conn, message.chat.id)

        await conn.execute(
            f"INSERT INTO {table} (type, amount, category) VALUES ($1, $2, $3)",
            t_type, amount, category
        )
        await conn.close()
        await message.answer(f"✅ Записано: {amount:.2f} ₸ ({category})")
    except:
        await message.answer("❌ Ошибка ввода. Пример: 5000 Зарплата")

# ==== ЗАПУСК ====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
