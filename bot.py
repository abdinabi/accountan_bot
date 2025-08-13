import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# ==== НАСТРОЙКИ ====
TOKEN = "8371020691:AAFdajHmJH00rLquuc_OEJB8ngqaVvTvTq8"

# ==== СОЗДАЁМ БАЗУ ====
conn = sqlite3.connect("finance.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT, -- income / expense
    amount REAL,
    category TEXT,
    date TEXT
)
""")
conn.commit()

# ==== КНОПКИ ====
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Доход"), KeyboardButton(text="💸 Расход")],
        [KeyboardButton(text="📊 Баланс"), KeyboardButton(text="🗓 Остатки по периодам")]
    ],
    resize_keyboard=True
)

# ==== СОСТОЯНИЕ ВВОДА ====
user_state = {}  # user_id -> "income" / "expense"

# ==== ЛОГИКА БОТА ====
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот для учёта доходов и расходов 💵", reply_markup=main_kb)

@dp.message(F.text == "💰 Доход")
async def income_start(message: types.Message):
    user_state[message.from_user.id] = "income"
    await message.answer("Введите сумму и категорию (например: 5000 Зарплата)")

@dp.message(F.text == "💸 Расход")
async def expense_start(message: types.Message):
    user_state[message.from_user.id] = "expense"
    await message.answer("Введите сумму и категорию (например: 1200 Продукты)")

@dp.message(F.text == "📊 Баланс")
async def show_balance(message: types.Message):
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income'")
    total_income = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense'")
    total_expense = cursor.fetchone()[0] or 0

    balance = total_income - total_expense
    await message.answer(f"💵 Текущий баланс: {balance:.2f} ₸")

@dp.message(F.text == "🗓 Остатки по периодам")
async def monthly_stats(message: types.Message):
    cursor.execute("""
        SELECT strftime('%Y-%m', date) as period,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM transactions
        GROUP BY period
        ORDER BY period
    """)
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Данных пока нет 📭")
        return

    text = ""
    for period, income, expense in rows:
        balance = (income or 0) - (expense or 0)
        text += f"📅 {period}\nДоход: +{income:.2f} ₸\nРасход: -{expense:.2f} ₸\nОстаток: {balance:.2f} ₸\n\n"
    await message.answer(text)

@dp.message()
async def handle_amount(message: types.Message):
    if message.from_user.id not in user_state:
        return  # игнор, если бот не ждет ввода суммы

    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0])
        category = parts[1] if len(parts) > 1 else "Без категории"

        t_type = user_state.pop(message.from_user.id)
        cursor.execute(
            "INSERT INTO transactions (type, amount, category, date) VALUES (?, ?, ?, datetime('now'))",
            (t_type, amount, category)
        )
        conn.commit()
        await message.answer(f"✅ Записано: {amount:.2f} ₸ ({category})")
    except Exception as e:
        await message.answer("❌ Ошибка ввода. Пример: 5000 Зарплата")

# ==== ЗАПУСК ====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
