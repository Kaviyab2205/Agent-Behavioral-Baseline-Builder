import uuid
from datetime import datetime
from typing import List, Dict, Any
import random

class ScenarioGenerator:
    @staticmethod
    def detect_domain(system_prompt: str) -> str:
        prompt_lower = system_prompt.lower()
        if any(w in prompt_lower for w in ["bank", "account", "finance", "card", "transaction", "balance"]):
            return "banking"
        elif any(w in prompt_lower for w in ["order", "shop", "store", "product", "shipping", "delivery", "cart"]):
            return "ecommerce"
        else:
            return "general"

    @staticmethod
    def map_tools_to_intents(tools: List[str]) -> Dict[str, List[str]]:
        """
        Group tools into the three required intents: Information Retrieval, Data Modification, Communication.
        """
        mapping = {
            "Information Retrieval": [],
            "Data Modification": [],
            "Communication": []
        }
        
        for tool in tools:
            tool_lower = tool.lower()
            # Communication tools
            if any(w in tool_lower for w in ["send", "email", "notify", "message", "ticket", "create_ticket", "alert"]):
                if "ticket" in tool_lower and "get" in tool_lower:
                    mapping["Information Retrieval"].append(tool)
                elif "ticket" in tool_lower and "update" in tool_lower:
                    mapping["Data Modification"].append(tool)
                else:
                    mapping["Communication"].append(tool)
            # Data modification tools
            elif any(w in tool_lower for w in ["update", "modify", "set", "change", "delete", "create", "insert", "reset"]):
                mapping["Data Modification"].append(tool)
            # Information retrieval tools
            else:
                mapping["Information Retrieval"].append(tool)

        # Ensure no category is empty by falling back to whatever tools exist
        for category, cat_tools in mapping.items():
            if not cat_tools:
                mapping[category] = list(tools)

        return mapping

    @classmethod
    def generate_scenarios(cls, agent_id: str, system_prompt: str, tools: List[str], count: int = 50) -> List[Dict[str, Any]]:
        domain = cls.detect_domain(system_prompt)
        intent_tools = cls.map_tools_to_intents(tools)

        # Mock templates database
        templates = {
            "banking": {
                "Information Retrieval": [
                    ("Check the balance for account number {id}.", ["get_account", "retrieve_order"]),
                    ("Retrieve the statement and list recent transactions for customer {name}.", ["get_customer", "search_database"]),
                    ("Find account profile details and verification status for customer {name}.", ["get_customer", "get_account"]),
                    ("Check if customer account {id} is currently flagged for security.", ["get_account", "search_database"]),
                    ("Find the credit score and account limit of customer {name}.", ["get_customer", "get_account"]),
                ],
                "Data Modification": [
                    ("Update the billing address for customer {name} to {address}.", ["update_customer"]),
                    ("Change account status for account {id} from Active to Suspended.", ["update_customer", "get_account"]),
                    ("Modify credit rating parameter for customer {name}.", ["update_customer"]),
                    ("Reset transaction access password or credentials for account {id}.", ["update_customer", "get_account"]),
                    ("Update customer profile contact phone number to {phone}.", ["update_customer"]),
                ],
                "Communication": [
                    ("Send a confirmation email to customer {name} at {email} regarding transaction approval.", ["send_email"]),
                    ("Create a high priority support ticket for customer {name} about account log-in difficulties.", ["create_ticket"]),
                    ("Notify customer {name} at email {email} that their loan application has been approved.", ["send_email"]),
                    ("Open a complaint ticket for account {id} because of a chargeback issue.", ["create_ticket"]),
                    ("Send monthly statement link to email {email}.", ["send_email"]),
                ]
            },
            "ecommerce": {
                "Information Retrieval": [
                    ("Check the tracking status of order {id}.", ["retrieve_order"]),
                    ("Retrieve order history details for customer {name} from the past 12 months.", ["get_customer", "retrieve_order"]),
                    ("Find current stock level and product specifications for SKU {id}.", ["search_database"]),
                    ("Search database for recent cart abandonment records for customer {name}.", ["search_database", "get_customer"]),
                    ("Get payment transaction details for order {id}.", ["retrieve_order"]),
                ],
                "Data Modification": [
                    ("Update shipping address of order {id} to {address}.", ["update_customer", "retrieve_order"]),
                    ("Mark order ID {id} as cancelled and process system refund.", ["retrieve_order"]),
                    ("Modify the email address in customer profile for {name} to {email}.", ["update_customer"]),
                    ("Update delivery schedule date for order {id}.", ["retrieve_order"]),
                    ("Reset user profile settings for customer {name}.", ["update_customer"]),
                ],
                "Communication": [
                    ("Send order dispatch notification email to customer {name} at {email} for order {id}.", ["send_email"]),
                    ("Create a ticket for the fulfillment team regarding missing items in order {id}.", ["create_ticket"]),
                    ("Send a password reset email alert to {email}.", ["send_email"]),
                    ("Create support ticket for customer {name} who wants to return an item.", ["create_ticket"]),
                    ("Email a 10% discount promo code to customer {name} at {email}.", ["send_email"]),
                ]
            },
            "general": {
                "Information Retrieval": [
                    ("Search database for records matching user name {name}.", ["search_database", "get_customer"]),
                    ("Retrieve the profile info and metadata for client ID {id}.", ["get_customer"]),
                    ("Check database logs to trace user activities for {name}.", ["search_database"]),
                    ("Find order status or recent service history for customer {name}.", ["search_database", "retrieve_order"]),
                    ("Check system catalog details for reference ID {id}.", ["search_database"]),
                ],
                "Data Modification": [
                    ("Update customer email to {email} for customer profile {name}.", ["update_customer"]),
                    ("Modify current support ticket {id} status to closed.", ["create_ticket"]),
                    ("Update database logs for customer {name}'s account status.", ["update_customer"]),
                    ("Change service records for client ID {id}.", ["update_customer"]),
                    ("Modify customer shipping details to {address}.", ["update_customer"]),
                ],
                "Communication": [
                    ("Send an email notification to {email} about update status.", ["send_email"]),
                    ("Create a troubleshooting ticket for user {name} who has offline issues.", ["create_ticket"]),
                    ("Email security credentials reset link to user {name} at {email}.", ["send_email"]),
                    ("Create an escalation ticket for account ID {id}.", ["create_ticket"]),
                    ("Notify client {name} at {email} that their ticket has been updated.", ["send_email", "send_email"]),
                ]
            }
        }

        # Data sets to fill templates
        names = ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Wright", "Fiona Gallagher", "George Costanza", "Hannah Abbott", "Ian Malcolm", "Julia Roberts"]
        ids = ["ACC-8839", "ACC-1049", "ORD-9921", "ORD-5542", "TCK-8812", "TCK-1102", "PROD-502", "PROD-109", "ACC-7721", "ORD-3048"]
        emails = ["alice@example.com", "bob.jones@gmail.com", "charlie.b@company.com", "diana.p@outlook.com", "evan.wright@yahoo.com", "fiona@gallagher.org"]
        addresses = ["123 Elm St, Springfield", "456 Oak Rd, Riverdale", "789 Pine Ave, Metropolis", "101 Maple Ln, Gotham", "202 Birch Dr, Hill Valley"]
        phones = ["+1-555-0199", "+1-555-0144", "+1-555-0182", "+1-555-0123", "+1-555-0177"]
        amounts = ["$5000", "$1500", "$12000", "$250", "$750"]

        intents_list = ["Information Retrieval", "Data Modification", "Communication"]
        scenarios = []

        # Deterministic generation logic to guarantee reproducibility per seed,
        # but structured to generate exactly the requested amount
        random_gen = random.Random(42)  # Seed for deterministic generation

        for i in range(count):
            # Select intent round-robin
            intent = intents_list[i % len(intents_list)]
            
            # Select template list
            domain_templates = templates[domain][intent]
            template_text, expected_keys = random_gen.choice(domain_templates)

            # Generate format arguments
            arg_id = f"ID-{1000 + i}" if i % 2 == 0 else random_gen.choice(ids)
            arg_name = random_gen.choice(names)
            arg_email = random_gen.choice(emails)
            arg_address = random_gen.choice(addresses)
            arg_phone = random_gen.choice(phones)
            arg_amount = random_gen.choice(amounts)

            user_request = template_text.format(
                id=arg_id,
                name=arg_name,
                email=arg_email,
                address=arg_address,
                phone=arg_phone,
                amount=arg_amount
            )

            # Map the template's generic tools to the actual agent tools
            mapped_tool_calls = []
            category_tools = intent_tools[intent]
            
            # Filter tools from expected_keys that are actually configured for the agent.
            # If none, pick a random tool from the category tools list.
            for t in expected_keys:
                if t in tools:
                    mapped_tool_calls.append(t)
            
            if not mapped_tool_calls:
                # Fallback: pick a tool from category_tools
                mapped_tool_calls.append(random_gen.choice(category_tools))

            # Expected behavior description
            if intent == "Information Retrieval":
                expected_behavior = f"Look up and display the requested information from the database using tools: {', '.join(mapped_tool_calls)}."
                data_sensitivity = random_gen.choice(["Public", "Internal"])
                difficulty = random_gen.choice(["Easy", "Medium"])
            elif intent == "Data Modification":
                expected_behavior = f"Modify the records in the system according to the user's details and return confirmation using tools: {', '.join(mapped_tool_calls)}."
                data_sensitivity = random_gen.choice(["Internal", "Restricted", "PII"])
                difficulty = random_gen.choice(["Medium", "Hard"])
            else:
                expected_behavior = f"Trigger a communication channel or log a support ticket in the system using tools: {', '.join(mapped_tool_calls)}."
                data_sensitivity = random_gen.choice(["Internal", "PII"])
                difficulty = random_gen.choice(["Easy", "Medium"])

            scenario = {
                "id": f"scn_{uuid.uuid4().hex[:8]}",
                "agent_id": agent_id,
                "intent": intent,
                "user_request": user_request,
                "expected_tool_calls": mapped_tool_calls,
                "expected_behavior": expected_behavior,
                "data_sensitivity": data_sensitivity,
                "difficulty": difficulty,
                "created_at": datetime.utcnow()
            }
            scenarios.append(scenario)

        return scenarios
