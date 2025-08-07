# app.py

import asyncio
import os
import uuid
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv

from agents import Agent, handoff
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

# ========== Environment ========== #
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY is missing in .env")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.0-flash"

external_client = AsyncOpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL)
model = OpenAIChatCompletionsModel(model=GEMINI_MODEL, openai_client=external_client)

# ========== Shared Memory ========== #
customer_memory: Dict[str, str] = {}
order_logs: List[Dict] = []

# ========== Agents ========== #
menu_agent = Agent(name="Menu Agent", instructions="Return the current fast food menu as a dictionary: Burger, Fries, Coke, Deal.")
order_parser_agent = Agent(name="Order Parser Agent", instructions="Parse the user's text and return an order dictionary with quantities of Burger, Fries, Coke, and Deal.")
greeter_agent = Agent(name="Greeter Agent", instructions="Greet the user warmly. If name is provided, personalize the greeting.")
order_repeater_agent = Agent(name="Repeat Agent", instructions="Summarize the parsed order in natural language, listing quantities and items.")
price_agent = Agent(name="Subtotal Agent", instructions="Calculate the subtotal from the parsed order using the fixed prices: Burger=500, Fries=200, Coke=150, Deal=800.")
billing_agent = Agent(name="Billing Agent", instructions="Given the parsed order, calculate subtotal, 13% tax, and 10% discount per Deal item. Return total, tax, discount.")
memory_agent = Agent(name="Memory Agent", instructions="Save the user's name and phone number in shared memory.")
hospitality_agent = Agent(name="Hospitality Agent", instructions="Add a polite tone to the given message. Add emojis or warm phrases.")
order_type_agent = Agent(name="Order Type Agent", instructions="Ask the customer whether they would like to dine in, takeaway, or get delivery.")
monitor_agent = Agent(name="Monitor Agent", instructions="Log the session ID, order, total, and timestamp into a log list.")

# ========== Handoffs ========== #
menu_handoff = handoff(menu_agent, "menu", "Show the menu")
order_handoff = handoff(order_parser_agent, "order_parser", "Parse user's order")
greet_handoff = handoff(greeter_agent, "greeter", "Greet the customer")
repeat_handoff = handoff(order_repeater_agent, "repeat", "Repeat the order")
price_handoff = handoff(price_agent, "subtotal", "Calculate subtotal")
billing_handoff = handoff(billing_agent, "billing", "Generate final bill")
memory_handoff = handoff(memory_agent, "memory", "Remember customer")
hospitality_handoff = handoff(hospitality_agent, "hospitality", "Add friendly tone")
order_type_handoff = handoff(order_type_agent, "order_type", "Ask about order type")
monitor_handoff = handoff(monitor_agent, "monitor", "Log the order session")

# ========== Triage Agent ========== #
triage_agent = Agent(
    name="Triage Agent",
    instructions="Coordinate the fast food order process by invoking appropriate handoffs in order.",
    handoffs=[
        greet_handoff,
        menu_handoff,
        order_handoff,
        repeat_handoff,
        price_handoff,
        billing_handoff,
        order_type_handoff,
        hospitality_handoff,
        memory_handoff,
        monitor_handoff
    ]
)

# ========== Main App ========== #
async def main():
    print("\n🍔 FastFoodBot via Triage Agent")

    session_id = str(uuid.uuid4())
    name = input("Name: ")
    phone = input("Phone: ")
    order_text = input("What would you like to order? ")

    context = {
        "session_id": session_id,
        "name": name,
        "phone": phone,
        "order_text": order_text,
        "order": {},
        "subtotal": 0,
        "total": 0,
        "tax": 0,
        "discount": 0,
        "timestamp": str(datetime.utcnow())
    }

    print(await greet_handoff.on_invoke_handoff(context, name))
    print("📋 Menu:", await menu_handoff.on_invoke_handoff(context, ""))

    order = await order_handoff.on_invoke_handoff(context, order_text)
    context["order"] = order

    print(await repeat_handoff.on_invoke_handoff(context, order))

    subtotal = await price_handoff.on_invoke_handoff(context, order)
    context["subtotal"] = subtotal

    billing = await billing_handoff.on_invoke_handoff(context, order)

    if isinstance(billing, dict):
        context["total"] = billing.get("total", 0)
        context["tax"] = billing.get("tax", 0)
        context["discount"] = billing.get("discount", 0)
    else:
        print("❌ Billing agent returned unexpected format:", billing)

    print(await order_type_handoff.on_invoke_handoff(context, ""))
    context["order_type"] = input("Choose: Dine in / Takeaway / Delivery: ")

    summary = f"Subtotal: Rs{subtotal}, Tax: Rs{context['tax']}, Discount: Rs{context['discount']}, Total: Rs{context['total']}"
    print(await hospitality_handoff.on_invoke_handoff(context, summary))

    await memory_handoff.on_invoke_handoff(context, {"name": name, "phone": phone})

    await monitor_handoff.on_invoke_handoff(context, {
        "session_id": session_id,
        "order": order,
        "total": context["total"],
        "timestamp": context["timestamp"]
    })

    print("\n✅ Order Complete!")

if __name__ == "__main__":
    asyncio.run(main())
