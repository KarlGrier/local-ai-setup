"""Tool calls: 10 prompts sent with real tool definitions through each API (OpenAI `tools` / Anthropic `tools`).
Expected: the right tool(s) with arguments that validate against the schema and match the request, or no call at
all when no tool fits.  Matchers: eq (exact), ci (case-insensitive equal), contains (case-insensitive substring),
in (one of, case-insensitive for strings), num (numeric equality), startswith, set (same members, any order,
case-insensitive)."""

W = {"name": "get_weather", "description": "Current weather for a city.",
     "parameters": {"type": "object", "properties": {
         "city": {"type": "string", "description": "City name"},
         "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
         "required": ["city", "unit"], "additionalProperties": False}}
FORECAST = {"name": "get_forecast", "description": "Daily weather forecast for the next 1-7 days.",
            "parameters": {"type": "object", "properties": {
                "city": {"type": "string"}, "days": {"type": "integer", "minimum": 1, "maximum": 7}},
                "required": ["city", "days"], "additionalProperties": False}}
SEARCH = {"name": "search_web", "description": "Search the web and return result snippets.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                         "required": ["query"], "additionalProperties": False}}
CALC = {"name": "calculator", "description": "Evaluate an arithmetic expression.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"], "additionalProperties": False}}
EVENT = {"name": "create_event", "description": "Create a calendar event.",
         "parameters": {"type": "object", "properties": {
             "title": {"type": "string"},
             "start": {"type": "string", "description": "Local start time, format YYYY-MM-DDTHH:MM",
                       "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}"},
             "duration_minutes": {"type": "integer", "minimum": 5},
             "attendees": {"type": "array", "items": {"type": "string"}, "description": "E-mail addresses"}},
             "required": ["title", "start", "duration_minutes"], "additionalProperties": False}}
LIST_EVENTS = {"name": "list_events", "description": "List the calendar events of one day.",
               "parameters": {"type": "object", "properties": {"date": {"type": "string",
                                                                        "description": "YYYY-MM-DD"}},
                              "required": ["date"], "additionalProperties": False}}
CONVERT = {"name": "convert_currency", "description": "Convert an amount of money from one currency to another.",
           "parameters": {"type": "object", "properties": {
               "amount": {"type": "number"},
               "from_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "ISO 4217 code"},
               "to_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "ISO 4217 code"}},
               "required": ["amount", "from_currency", "to_currency"], "additionalProperties": False}}
RATE = {"name": "get_exchange_rate", "description": "Get the exchange rate between two currencies.",
        "parameters": {"type": "object", "properties": {
            "base": {"type": "string", "pattern": "^[A-Z]{3}$"}, "quote": {"type": "string", "pattern": "^[A-Z]{3}$"}},
            "required": ["base", "quote"], "additionalProperties": False}}
FLIGHTS = {"name": "search_flights", "description": "Search flights between two airports on a date.",
           "parameters": {"type": "object", "properties": {
               "origin": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "IATA airport or city code"},
               "destination": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "IATA airport or city code"},
               "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
               "adults": {"type": "integer", "minimum": 1}},
               "required": ["origin", "destination", "date", "adults"], "additionalProperties": False}}
HOTEL = {"name": "book_hotel", "description": "Book a hotel room.",
         "parameters": {"type": "object", "properties": {
             "city": {"type": "string"}, "check_in": {"type": "string"}, "nights": {"type": "integer", "minimum": 1}},
             "required": ["city", "check_in", "nights"], "additionalProperties": False}}
TICKET = {"name": "create_ticket", "description": "File an issue in the bug tracker.",
          "parameters": {"type": "object", "properties": {
              "title": {"type": "string"},
              "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
              "labels": {"type": "array", "items": {"type": "string"}},
              "reporter": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
                           "required": ["name", "email"], "additionalProperties": False}},
              "required": ["title", "priority", "reporter"], "additionalProperties": False}}
SEARCH_TICKETS = {"name": "search_tickets", "description": "Search existing issues.",
                  "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                                 "required": ["query"], "additionalProperties": False}}
EMAIL = {"name": "send_email", "description": "Send an e-mail.",
         "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"},
                                                         "body": {"type": "string"}},
                        "required": ["to", "subject", "body"], "additionalProperties": False}}
STOCK = {"name": "get_stock_price", "description": "Latest price of a stock ticker.",
         "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"], "additionalProperties": False}}
THERMO = {"name": "set_thermostat", "description": "Set a room's thermostat.",
          "parameters": {"type": "object", "properties": {
              "room": {"type": "string", "enum": ["living_room", "bedroom", "kitchen", "office"]},
              "temperature_c": {"type": "number", "minimum": 10, "maximum": 30},
              "mode": {"type": "string", "enum": ["heat", "cool", "auto"]}},
              "required": ["room", "temperature_c", "mode"], "additionalProperties": False}}
THERMO_GET = {"name": "get_thermostat", "description": "Read a room's thermostat setting.",
              "parameters": {"type": "object", "properties": {"room": {"type": "string", "enum": [
                  "living_room", "bedroom", "kitchen", "office"]}}, "required": ["room"],
                  "additionalProperties": False}}
UNITS_L = ["mm", "cm", "m", "km", "in", "ft", "yd", "mi"]
UNITS_W = ["g", "kg", "oz", "lb", "stone"]
LEN = {"name": "convert_length", "description": "Convert a length between units.",
       "parameters": {"type": "object", "properties": {"value": {"type": "number"},
                                                       "from_unit": {"type": "string", "enum": UNITS_L},
                                                       "to_unit": {"type": "string", "enum": UNITS_L}},
                      "required": ["value", "from_unit", "to_unit"], "additionalProperties": False}}
WEIGHT = {"name": "convert_weight", "description": "Convert a weight between units.",
          "parameters": {"type": "object", "properties": {"value": {"type": "number"},
                                                          "from_unit": {"type": "string", "enum": UNITS_W},
                                                          "to_unit": {"type": "string", "enum": UNITS_W}},
                         "required": ["value", "from_unit", "to_unit"], "additionalProperties": False}}
TEMP = {"name": "convert_temperature", "description": "Convert a temperature between C, F and K.",
        "parameters": {"type": "object", "properties": {"value": {"type": "number"},
                                                        "from_unit": {"type": "string", "enum": ["C", "F", "K"]},
                                                        "to_unit": {"type": "string", "enum": ["C", "F", "K"]}},
                       "required": ["value", "from_unit", "to_unit"], "additionalProperties": False}}
TRANSLATE = {"name": "translate_text", "description": "Translate text into another language.",
             "parameters": {"type": "object", "properties": {"text": {"type": "string"},
                                                             "target_language": {"type": "string"}},
                            "required": ["text", "target_language"], "additionalProperties": False}}

ITEMS = [
    {"id": "t01_weather_unit", "tools": [W, FORECAST, SEARCH],
     "prompt": "What's the temperature in Lisbon right now? I want it in Fahrenheit.",
     "expect": [{"name": "get_weather", "args": {"city": {"contains": "lisbon"}, "unit": {"eq": "fahrenheit"}}}],
     "good": [{"name": "get_weather", "arguments": '{"city": "Lisbon", "unit": "fahrenheit"}'}],
     "bad": [{"name": "get_forecast", "arguments": '{"city": "Lisbon", "days": 1}'}]},
    {"id": "t02_calendar_event", "tools": [EVENT, LIST_EVENTS],
     "prompt": "Put a 45-minute 'Budget review' on my calendar on 2026-11-04 at 14:30 with jana@example.com and "
               "li@example.com.",
     "expect": [{"name": "create_event", "args": {"title": {"contains": "budget review"},
                                                  "start": {"startswith": "2026-11-04T14:30"},
                                                  "duration_minutes": {"num": 45},
                                                  "attendees": {"set": ["jana@example.com", "li@example.com"]}}}],
     "good": [{"name": "create_event", "arguments": '{"title": "Budget review", "start": "2026-11-04T14:30", '
                                                    '"duration_minutes": 45, "attendees": ["jana@example.com", '
                                                    '"li@example.com"]}'}],
     "bad": [{"name": "create_event", "arguments": '{"title": "Budget review", "start": "2026-11-04 14:30", '
                                                   '"duration_minutes": 45}'}]},
    {"id": "t03_currency", "tools": [CONVERT, RATE],
     "prompt": "How many Japanese yen would I get for 250 euros?",
     "expect": [{"name": "convert_currency", "args": {"amount": {"num": 250}, "from_currency": {"eq": "EUR"},
                                                      "to_currency": {"eq": "JPY"}}}],
     "good": [{"name": "convert_currency", "arguments": '{"amount": 250, "from_currency": "EUR", "to_currency": "JPY"}'}],
     "bad": [{"name": "convert_currency", "arguments": '{"amount": 250, "from_currency": "JPY", "to_currency": "EUR"}'}]},
    {"id": "t04_no_tool_poem", "tools": [W, CALC],
     "prompt": "Write a two-line poem about autumn leaves.",
     "expect": None,
     "good": [], "bad": [{"name": "calculator", "arguments": '{"expression": "2"}'}]},
    {"id": "t05_flights_codes", "tools": [FLIGHTS, HOTEL],
     "prompt": "Find flights from Oslo to Rome on 3 November 2026 for two adults.",
     "expect": [{"name": "search_flights", "args": {"origin": {"in": ["OSL"]}, "destination": {"in": ["FCO", "CIA", "ROM"]},
                                                    "date": {"eq": "2026-11-03"}, "adults": {"num": 2}}}],
     "good": [{"name": "search_flights", "arguments": '{"origin": "OSL", "destination": "FCO", "date": "2026-11-03", '
                                                      '"adults": 2}'}],
     "bad": [{"name": "search_flights", "arguments": '{"origin": "Oslo", "destination": "Rome", "date": "2026-11-03", '
                                                     '"adults": 2}'}]},
    {"id": "t06_nested_ticket", "tools": [TICKET, SEARCH_TICKETS],
     "prompt": "File an urgent ticket titled 'Login page returns 500' with the labels auth and backend, reported by "
               "Mei Tanaka (mei.tanaka@example.org).",
     "expect": [{"name": "create_ticket", "args": {"title": {"ci": "Login page returns 500"},
                                                   "priority": {"eq": "urgent"},
                                                   "labels": {"set": ["auth", "backend"]},
                                                   "reporter": {"obj": {"name": {"ci": "Mei Tanaka"},
                                                                        "email": {"ci": "mei.tanaka@example.org"}}}}}],
     "good": [{"name": "create_ticket", "arguments": '{"title": "Login page returns 500", "priority": "urgent", '
                                                     '"labels": ["auth", "backend"], "reporter": {"name": "Mei Tanaka", '
                                                     '"email": "mei.tanaka@example.org"}}'}],
     "bad": [{"name": "create_ticket", "arguments": '{"title": "Login page returns 500", "priority": "high", '
                                                    '"labels": ["auth", "backend"], "reporter": "Mei Tanaka"}'}]},
    {"id": "t07_no_tool_fact", "tools": [EMAIL, STOCK],
     "prompt": "What is the capital city of Australia?",
     "expect": None,
     "good": [], "bad": [{"name": "get_stock_price", "arguments": '{"ticker": "AUS"}'}]},
    {"id": "t08_thermostat", "tools": [THERMO, THERMO_GET],
     "prompt": "Set the bedroom to 21.5 °C on heating.",
     "expect": [{"name": "set_thermostat", "args": {"room": {"eq": "bedroom"}, "temperature_c": {"num": 21.5},
                                                    "mode": {"eq": "heat"}}}],
     "good": [{"name": "set_thermostat", "arguments": '{"room": "bedroom", "temperature_c": 21.5, "mode": "heat"}'}],
     "bad": [{"name": "set_thermostat", "arguments": '{"room": "bedroom", "temperature_c": "21.5", "mode": "heat"}'}]},
    {"id": "t09_weight_units", "tools": [LEN, WEIGHT, TEMP],
     "prompt": "How many kilograms is 12 stone?",
     "expect": [{"name": "convert_weight", "args": {"value": {"num": 12}, "from_unit": {"eq": "stone"},
                                                    "to_unit": {"eq": "kg"}}}],
     "good": [{"name": "convert_weight", "arguments": '{"value": 12, "from_unit": "stone", "to_unit": "kg"}'}],
     "bad": [{"name": "convert_length", "arguments": '{"value": 12, "from_unit": "m", "to_unit": "km"}'}]},
    {"id": "t10_no_tool_reminder", "tools": [W, TRANSLATE],
     "prompt": "Remind me to call my sister tomorrow at 9.",
     "expect": None,
     "good": [], "bad": [{"name": "translate_text", "arguments": '{"text": "call my sister", "target_language": "en"}'}]},
]
