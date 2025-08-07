from fastapi import FastAPI, Request
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
from app import (
    greet_handoff, menu_handoff, order_handoff, repeat_handoff,
    price_handoff, billing_handoff, order_type_handoff,
    hospitality_handoff, memory_handoff, monitor_handoff
)

app = FastAPI()

class OrderRequest(BaseModel):
    name: str
    phone: str
    order_text: str
    order_type: str  # dine in / takeaway / delivery

@app.post("/order")
async def handle_order(req: OrderRequest):
    session_id = str(uuid4())

    context = {
        "session_id": session_id,
        "name": req.name,
        "phone": req.phone,
        "order_text": req.order_text,
        "order": {},
        "subtotal": 0,
        "total": 0,
        "tax": 0,
        "discount": 0,
        "order_type": req.order_type,
        "timestamp": str(datetime.utcnow())
    }

    greeting = await greet_handoff.on_invoke_handoff(context, req.name)
    menu = await menu_handoff.on_invoke_handoff(context, "")
    order = await order_handoff.on_invoke_handoff(context, req.order_text)
    context["order"] = order

    order_summary = await repeat_handoff.on_invoke_handoff(context, order)
    subtotal = await price_handoff.on_invoke_handoff(context, order)
    context["subtotal"] = subtotal

    billing = await billing_handoff.on_invoke_handoff(context, order)
    if isinstance(billing, dict):
        context["total"] = billing.get("total", 0)
        context["tax"] = billing.get("tax", 0)
        context["discount"] = billing.get("discount", 0)

    friendly_summary = await hospitality_handoff.on_invoke_handoff(context, f"Subtotal: Rs{subtotal}, Tax: Rs{context['tax']}, Discount: Rs{context['discount']}, Total: Rs{context['total']}")

    await memory_handoff.on_invoke_handoff(context, {"name": req.name, "phone": req.phone})
    await monitor_handoff.on_invoke_handoff(context, {
        "session_id": session_id,
        "order": order,
        "total": context["total"],
        "timestamp": context["timestamp"]
    })

    return {
        "message": "✅ Order Complete!",
        "greeting": greeting,
        "menu": menu,
        "order_summary": order_summary,
        "billing": billing,
        "friendly_summary": friendly_summary
    }
