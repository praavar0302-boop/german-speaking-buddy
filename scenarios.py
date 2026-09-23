"""Roleplay scenarios for GermanSpeakingBuddy."""

from __future__ import annotations

import random
import re


SCENARIOS = {
    "Café": {
        "title": "At a Café",
        "learner_role": "You are a customer ordering at a café.",
        "ai_role": "The AI is the café server.",
        "opening_lines": {
            "A1": "Guten Tag! Was möchten Sie trinken?",
            "A2": "Guten Tag! Möchten Sie etwas essen oder trinken?",
        },
        "fallback_closing": "Danke! Einen schönen Tag noch!",
        "objectives": [
            {"id": "greet", "text": "Greet the server."},
            {"id": "order_drink", "text": "Order a drink."},
            {"id": "ask_price", "text": "Ask for the price."},
            {"id": "pay_goodbye", "text": "Pay and say goodbye."},
        ],
        "completion_condition": "The order is paid for and both people say goodbye.",
    },
    "Restaurant": {
        "title": "At a Restaurant",
        "learner_role": "You are a guest having a meal at a restaurant.",
        "ai_role": "The AI is the restaurant server.",
        "opening_lines": {
            "A1": "Guten Tag! Haben Sie einen Tisch?",
            "A2": "Guten Tag! Haben Sie schon einen Tisch?",
        },
        "fallback_closing": "Danke! Auf Wiedersehen!",
        "objectives": [
            {"id": "ask_table", "text": "Ask for a table."},
            {"id": "order_meal", "text": "Order food and a drink."},
            {"id": "ask_meal", "text": "Ask one simple question about the meal."},
            {"id": "bill_goodbye", "text": "Ask for the bill and finish politely."},
        ],
        "completion_condition": "The learner has asked for the bill and the meal is finished.",
    },
    "Supermarket": {
        "title": "At a Supermarket",
        "learner_role": "You are a customer shopping for a few everyday items.",
        "ai_role": "The AI is a supermarket employee.",
        "opening_lines": {
            "A1": "Guten Tag! Was suchen Sie?",
            "A2": "Guten Tag! Wie kann ich Ihnen helfen?",
        },
        "fallback_closing": "Danke! Einen schönen Tag noch!",
        "objectives": [
            {"id": "find_item", "text": "Ask where an item is."},
            {"id": "ask_price", "text": "Ask about its price."},
            {"id": "state_quantity", "text": "Say how much or how many you need."},
            {"id": "thank_finish", "text": "Thank the employee and finish shopping."},
        ],
        "completion_condition": "The learner has found the item and finished the exchange.",
    },
    "Asking for Directions": {
        "title": "Asking for Directions",
        "learner_role": "You are a visitor looking for a nearby place.",
        "ai_role": "The AI is a local person giving directions.",
        "opening_lines": {
            "A1": "Guten Tag! Wohin möchten Sie gehen?",
            "A2": "Guten Tag! Wohin möchten Sie heute gehen?",
        },
        "fallback_closing": "Danke! Gute Reise!",
        "objectives": [
            {"id": "ask_route", "text": "Ask how to get to a place."},
            {"id": "understand_directions", "text": "Understand at least two simple directions."},
            {"id": "confirm_route", "text": "Confirm the destination or route."},
            {"id": "thank_local", "text": "Thank the local person."},
        ],
        "completion_condition": "The learner confirms the route and thanks the local person.",
    },
    "Train Station": {
        "title": "At the Train Station",
        "learner_role": "You are a traveler planning a train journey.",
        "ai_role": "The AI is a station employee.",
        "opening_lines": {
            "A1": "Guten Tag! Wohin möchten Sie fahren?",
            "A2": "Guten Tag! Wohin möchten Sie heute fahren?",
        },
        "fallback_closing": "Danke! Gute Fahrt!",
        "objectives": [
            {"id": "destination", "text": "Say where you want to travel."},
            {"id": "time_platform", "text": "Ask about the departure time or platform."},
            {"id": "ticket", "text": "Ask for a suitable ticket."},
            {"id": "confirm_journey", "text": "Confirm the important journey details."},
        ],
        "completion_condition": "The learner has the ticket information and confirms the journey.",
    },
    "Pharmacy": {
        "title": "At a Pharmacy",
        "learner_role": "You are a customer asking about a simple everyday health need.",
        "ai_role": "The AI is the pharmacist.",
        "opening_lines": {
            "A1": "Guten Tag! Was brauchen Sie?",
            "A2": "Guten Tag! Was kann ich für Sie tun?",
        },
        "fallback_closing": "Gute Besserung! Auf Wiedersehen!",
        "objectives": [
            {"id": "describe_need", "text": "Describe a simple symptom or need."},
            {"id": "duration", "text": "Say how long you have had it."},
            {"id": "ask_product", "text": "Ask for a suitable everyday product."},
            {"id": "use_goodbye", "text": "Ask how to use it and finish politely."},
        ],
        "completion_condition": "The learner understands the basic product instructions and closes the exchange.",
    },
    "Hotel": {
        "title": "At a Hotel",
        "learner_role": "You are a hotel guest checking in.",
        "ai_role": "The AI is the hotel receptionist.",
        "opening_lines": {
            "A1": "Guten Tag! Haben Sie ein Zimmer?",
            "A2": "Guten Tag! Haben Sie ein Zimmer bestellt?",
        },
        "fallback_closing": "Ihr Zimmer ist hier. Auf Wiedersehen!",
        "objectives": [
            {"id": "reservation", "text": "Give your name or reservation details."},
            {"id": "ask_room", "text": "Ask about the room."},
            {"id": "breakfast_wifi", "text": "Ask about breakfast or Wi-Fi."},
            {"id": "confirm_checkin", "text": "Confirm the key information and finish check-in."},
        ],
        "completion_condition": "Check-in is complete and the learner has the room information.",
    },
    "Airport": {
        "title": "At the Airport",
        "learner_role": "You are a passenger preparing for a flight.",
        "ai_role": "The AI is an airline employee.",
        "opening_lines": {
            "A1": "Guten Tag! Wohin fliegen Sie?",
            "A2": "Guten Tag! Wohin geht Ihre Reise?",
        },
        "fallback_closing": "Danke! Guten Flug!",
        "objectives": [
            {"id": "flight_details", "text": "Give your destination or flight details."},
            {"id": "ask_luggage", "text": "Ask about your luggage."},
            {"id": "gate_time", "text": "Ask for the gate or boarding time."},
            {"id": "confirm_flight", "text": "Confirm the important flight information."},
        ],
        "completion_condition": "The learner confirms the gate, time, and luggage information.",
    },
}

SCENARIO_OPTIONS = [*SCENARIOS, "Random"]


def choose_random_scenario():
    """Return the name of one real scenario."""
    return random.choice(list(SCENARIOS))


def scenario_is_complete(scenario, progress):
    """Return True only when every objective is marked complete."""
    return len(progress) == len(scenario["objectives"]) and all(progress)


def opening_line(scenario, level):
    """Return the reviewed opening for the selected scenario and level."""
    return scenario["opening_lines"][level.upper()]


def is_closing_reply(text):
    """Accept a short farewell, not another question or task."""
    reply = text.strip().casefold()
    if not reply or "?" in reply or "[[" in reply or len(reply.split()) > 25:
        return False
    sentences = [part.strip() for part in re.split(r"[.!]+", reply) if part.strip()]
    if not sentences or len(sentences) > 3:
        return False
    final_sentence = sentences[-1]
    return any(
        phrase in final_sentence
        for phrase in (
            "auf wiedersehen",
            "tschüss",
            "schönen tag",
            "gute reise",
            "gute fahrt",
            "gute besserung",
            "guten flug",
            "bis bald",
        )
    )


def format_scenario_prompt(scenario, progress):
    """Format the selected scenario and current progress for the model."""
    objective_lines = [
        f"- [{'done' if done else 'remaining'}] {objective['id']}: {objective['text']}"
        for objective, done in zip(scenario["objectives"], progress)
    ]
    guidance = (
        "Guide the learner naturally toward remaining objectives. Do not mention "
        "the checklist. If the learner's latest message completes the last remaining "
        "objective, answer with a brief, natural goodbye in your assigned role. "
        "Do not introduce another task or ask a new question after that."
    )
    return "\n".join(
        [
            "ROLEPLAY SCENARIO:",
            f"Title: {scenario['title']}",
            f"Learner role: {scenario['learner_role']}",
            f"Your role: {scenario['ai_role']}",
            "Stay in this role throughout the conversation. Speak as the character, "
            "not as a generic assistant or language tutor.",
            "Respond directly to the learner's most recent message and its context "
            "before moving toward another objective.",
            "Do not explain the exercise or list objectives unless the learner asks.",
            "Move naturally, one small step at a time; do not skip ahead or repeat "
            "the opening line.",
            "Objectives:",
            *objective_lines,
            f"Completion condition: {scenario['completion_condition']}",
            guidance,
        ]
    )
