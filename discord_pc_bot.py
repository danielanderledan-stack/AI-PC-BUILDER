#!/usr/bin/env python3
"""
Discord PC Builder Bot
Progressive questioning system for AI PC builds
"""

import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
from datetime import datetime, timedelta
import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
import threading
import time
import logging
import atexit

# File locking for concurrency safety
class FileLock:
    """Simple file-based locking mechanism"""
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock = threading.Lock()
    
    def acquire(self, timeout=5):
        """Acquire lock with timeout"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file exclusively
                with open(self.lock_file, 'x') as f:
                    f.write(str(os.getpid()))
                return True
            except FileExistsError:
                # Lock file exists, wait and retry
                time.sleep(0.1)
            except Exception:
                return False
        return False
    
    def release(self):
        """Release lock"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass
    
    def __enter__(self):
        if not self.acquire():
            raise Exception(f"Could not acquire lock for {self.lock_file}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# Configuration
API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', 'YOUR_DISCORD_BOT_TOKEN_HERE')

# Instance ID for multiple bot instances (if needed)
INSTANCE_ID = f"{os.getpid()}_{int(time.time())}"

# File paths - use absolute paths based on script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARTS_DATA_FILE = os.path.join(SCRIPT_DIR, "latest_parts_formatted")
IMAGE_CACHE_FILE = os.path.join(SCRIPT_DIR, "image_cache.json")
USER_SESSIONS_FILE = os.path.join(SCRIPT_DIR, "discord_sessions.json")

# Lock file paths for concurrency safety
COLLECTIVE_LOCK_FILE = os.path.join(SCRIPT_DIR, '.collective_lock')
SESSIONS_LOCK_FILE = os.path.join(SCRIPT_DIR, '.sessions_lock')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cleanup function to remove lock files on exit
def cleanup_lock_files():
    """Remove lock files when bot shuts down"""
    try:
        if os.path.exists(COLLECTIVE_LOCK_FILE):
            os.remove(COLLECTIVE_LOCK_FILE)
        if os.path.exists(SESSIONS_LOCK_FILE):
            os.remove(SESSIONS_LOCK_FILE)
        logger.info("Lock files cleaned up on exit")
    except Exception as e:
        logger.error(f"Error cleaning up lock files: {e}")

# Register cleanup function
atexit.register(cleanup_lock_files)

class PCBuilderSession:
    """Manages a user's PC building session"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.chat_history = []
        self.answers = {}
        self.build_result = ""
        self.refinement_mode = False
        self.conversation_mode = False
        self.feedback_mode = False
        self.user_feedback = ""
        self.build_edits = []  # Track what user says when editing builds
        self.created_at = datetime.now().isoformat()
        self.last_activity = datetime.now().isoformat()
        
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'chat_history': self.chat_history,
            'answers': self.answers,
            'build_result': self.build_result,
            'refinement_mode': self.refinement_mode,
            'conversation_mode': self.conversation_mode,
            'feedback_mode': self.feedback_mode,
            'user_feedback': self.user_feedback,
            'build_edits': self.build_edits,
            'created_at': self.created_at,
            'last_activity': self.last_activity
        }
    
    @classmethod
    def from_dict(cls, data):
        session = cls(data['user_id'])
        session.chat_history = data.get('chat_history', [])
        session.answers = data.get('answers', {})
        session.build_result = data.get('build_result', '')
        session.refinement_mode = data.get('refinement_mode', False)
        session.conversation_mode = data.get('conversation_mode', False)
        session.feedback_mode = data.get('feedback_mode', False)
        session.user_feedback = data.get('user_feedback', '')
        session.build_edits = data.get('build_edits', [])
        session.created_at = data.get('created_at')
        session.last_activity = data.get('last_activity')
        return session
    
    def update_activity(self):
        self.last_activity = datetime.now().isoformat()

class SessionManager:
    """Manages user sessions with file persistence"""
    
    def __init__(self):
        self.sessions: Dict[int, PCBuilderSession] = {}
        self.load_sessions()
    
    def load_sessions(self):
        """Load sessions from file with file locking"""
        try:
            if os.path.exists(USER_SESSIONS_FILE):
                with FileLock(SESSIONS_LOCK_FILE):
                    with open(USER_SESSIONS_FILE, 'r') as f:
                        data = json.load(f)
                        for user_id_str, session_data in data.items():
                            user_id = int(user_id_str)
                            self.sessions[user_id] = PCBuilderSession.from_dict(session_data)
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    def save_sessions(self):
        """Save sessions to file with file locking"""
        try:
            data = {}
            for user_id, session in self.sessions.items():
                data[str(user_id)] = session.to_dict()
            with FileLock(SESSIONS_LOCK_FILE):
             with open(USER_SESSIONS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    def get_session(self, user_id: int) -> PCBuilderSession:
        """Get or create a session for a user"""
        if user_id not in self.sessions:
            self.sessions[user_id] = PCBuilderSession(user_id)
        
        session = self.sessions[user_id]
        session.update_activity()
        return session
    
    def clear_session(self, user_id: int):
        """Clear a user's session"""
        if user_id in self.sessions:
            del self.sessions[user_id]
        self.save_sessions()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove sessions older than max_age_hours"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []
        
        for user_id, session in self.sessions.items():
            try:
                last_activity = datetime.fromisoformat(session.last_activity)
                if last_activity < cutoff:
                    to_remove.append(user_id)
            except:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            del self.sessions[user_id]
        
        if to_remove:
            self.save_sessions()
            logger.info(f"Cleaned up {len(to_remove)} old sessions")

class ConversationalFlow:
    """Handles open-ended conversational PC building flow"""
    
    REQUIRED_FIELDS = ['budget', 'color', 'rgb_level', 'aesthetics', 'use_case', 'upgradeability', 'extra_notes']
    
    def __init__(self):
        self.preloaded_greeting = "Hey! I'm your AI PC builder. What's your budget for this build?"
    
    def format_history(self, chat_history):
        """Format chat history for Gemini prompt"""
        out = []
        for m in chat_history[-30:]:  # Last 30 messages
            role = m.get('role', 'assistant').capitalize()
            text = (m.get('text') or '').strip()
            if text:
                out.append(f"{role}: {text}")
        return "\n".join(out)
    
    def build_conversation_prompt(self, chat_history, answers):
        """Build the conversational prompt for Gemini"""
        history_text = self.format_history(chat_history)
        answers_text = "\n".join([f"- {k}: {answers.get(k)}" for k in self.REQUIRED_FIELDS if answers.get(k)])
        missing = [k for k in self.REQUIRED_FIELDS if not answers.get(k)]
        missing_text = ", ".join(missing) if missing else "none"
        
        return f"""
You are the onboarding wizard for an AI PC builder. Friendly, concise, conversational.
The UI already showed the first assistant message below — do NOT repeat it; continue naturally from it:
PRELOADED: {self.preloaded_greeting}

Conversation so far:
{history_text}

Collected answers so far (if any):
{answers_text or 'none'}

Fields to capture (ONLY these 7 fields - do NOT ask about components):
- budget (freeform; numbers or ranges like 800-1500 are fine)
- color (recommend black/white, but accept any choice; suggest RGB can provide exotic colors)
- rgb_level preference (number 0–10 OR words like "none", "subtle", "medium", "lots", "max")
- aesthetics preference (number 0–10 OR words like "low", "balanced", "high")
- use_case (freeform: games, streaming, editing, etc.)
- upgradeability (freeform: "won't upgrade", "might upgrade", "will upgrade")
- extra_notes (freeform: any special requirements, or "none")

Missing fields: {missing_text}

CRITICAL: Do NOT ask about AMD vs Intel, NVIDIA vs AMD, cooling types, or any specific components. Only ask about the 7 fields above.



PERFORMANCE TIERLIST (reference only):
Use this to judge relative GPU performance when selecting parts.
RTX 5090 32GB............... 100
RTX Pro 6000 Blackwell 96GB.  90
RX 7900 XTX 24GB............  75
RTX 5080 16GB...............  74
RX 9070 XT 16GB.............  67
RTX 5070 Ti 16GB............  66
RX 9070 16GB................  62
RTX 4070 Ti Super 16GB......  61
RTX 5070 12GB...............  55
RTX 4070 Super 12GB.........  53
RTX 4070 12GB...............  51
RX 7800 XT 16GB.............  50
RTX 5060 Ti 16GB............  48
RTX 5060 Ti 8GB.............  47
RX 9060 XT 16GB.............  46
RTX 4060 Ti 8GB.............  45
RTX 5060 8GB................  44
RX 9060 XT 8GB..............  44
Intel Arc B580 12GB.........  42
RTX 4060 8GB................  40
RX 7600 8GB.................  38
RTX 3060 12GB...............  35
RTX 5050 8GB................  34
RTX 3050 6GB................  28
(If a model is not listed, approximate using adjacent models and VRAM class.)

- RGB levels: 0-3 (minimal), 4-6 (moderate), 7-10 (lots)
- Aesthetics: 0-3 (performance first), 4-6 (balanced), 7-10 (looks matter)
- Colors: Recommend black or white for best component availability and value. If they want exotic colors (pink, purple, etc.), suggest RGB lighting can provide that color theme.

CONVERSATION FLOW RULES:
- If user gives a simple answer (like "fortnite", "nah", "just fort"), ACCEPT it and move to the next field
- Only ask for clarification if the answer is completely unclear or contradictory
- Don't ask "just to confirm" or "to be clear" - trust their answers
- Move through fields efficiently: budget → color → rgb_level → aesthetics → use_case → upgradeability → extra_notes

Instructions:
- Be conversational and helpful. You can ask follow-up questions, provide advice, or explain things.
- You MUST collect these specific fields: budget, color, rgb_level, aesthetics, use_case, upgradeability, extra_notes
- Ask ONLY ONE question at a time - keep it simple and focused.
- Keep responses SHORT - under 100 words for Discord. Be concise.
- Always end with a single question to keep the conversation flowing.
- ACCEPT simple answers and move on - don't ask endless clarifying questions.
- DO NOT ask "just to confirm" or "to be clear" - trust their answers and move forward.
- When users ask for recommendations (like "what's good for Fortnite"), give helpful suggestions and then ask for their preference.
- For colors: Recommend black or white for best value/availability, but if they want exotic colors, suggest RGB can provide that theme. Always accept their final choice.
- DO NOT ask questions about specific components (AMD vs Intel, NVIDIA vs AMD, cooling types, etc.) - only ask about the required fields.
- When you have enough information to build a PC, say something like "Great! I think I have everything I need. Ready to build your PC?"

IMPORTANT: You MUST end your message with <READY_TO_BUILD> when you have collected information for ALL 7 fields: budget, color, rgb_level, aesthetics, use_case, upgradeability, and extra_notes.
"""
    

class PCBuildGenerator:
    """Handles PC build generation and refinement using Gemini"""
    
    def __init__(self):
        genai.configure(api_key=API_KEY)
        self.model = genai.GenerativeModel("gemini-1.5-pro-latest")
    
    def load_parts_data(self) -> str:
        """Load the latest parts data"""
        try:
            if os.path.exists(PARTS_DATA_FILE):
                with open(PARTS_DATA_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        logger.warning(f"Parts data file is empty: {PARTS_DATA_FILE}")
                        return ""
                    return content
            else:
                logger.error(f"Parts data file not found: {PARTS_DATA_FILE}")
                logger.error("Please ensure the parts data file exists in the same directory as the bot")
                return ""
        except Exception as e:
            logger.error(f"Error loading parts data: {e}")
            return ""
    
    def load_image_cache(self) -> Dict[str, str]:
        """Load image cache"""
        try:
            if os.path.exists(IMAGE_CACHE_FILE):
                with open(IMAGE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('images', {})
            return {}
        except Exception as e:
            logger.error(f"Error loading image cache: {e}")
            return {}
    
    def build_prompt(self, session: PCBuilderSession, parts_data: str) -> str:
        """Build the Gemini prompt"""
        
        # Extract budget value for calculations - handle open-ended inputs
        budget_text = session.answers.get('budget', '$1000')
        budget_match = re.search(r'(\d+[\,\d]*)', budget_text.replace(',', ''))
        
        if budget_match:
            budget_val = int(budget_match.group(1).replace(',', ''))
            # Calculate adjusted budget (85% or -$200, whichever is less)
            reduced = int(budget_val * 0.85)
            adjusted_budget = min(reduced, budget_val - 200)
            if budget_val - adjusted_budget < 200:
                adjusted_budget = budget_val - 200
            price_range = f"MAXIMUM TOTAL BUDGET: ${adjusted_budget} (absolute maximum, do not exceed)"
        else:
            # Handle open-ended budget requests
            budget_lower = budget_text.lower()
            if any(word in budget_lower for word in ['fortnite', 'gaming', 'game']):
                # Default gaming budget if they asked about gaming
                adjusted_budget = 800
                price_range = f"RECOMMENDED GAMING BUDGET: ${adjusted_budget} (good for competitive gaming like Fortnite)"
            elif any(word in budget_lower for word in ['budget', 'cost', 'price', 'spend', 'afford']):
                # Default mid-range budget for general advice
                adjusted_budget = 1200
                price_range = f"RECOMMENDED BUDGET: ${adjusted_budget} (balanced performance and value)"
            else:
                # Default budget
                adjusted_budget = 1000
                price_range = f"RECOMMENDED BUDGET: ${adjusted_budget} (good starting point)"
        
        prompt = f"""
You are a friendly PC build expert. Using the compact catalog below and the user's brief, design a cohesive, great-looking build that balances performance, noise, thermals, and value. Be creative and lean into the user's style, but keep things practical and compatible.

CATALOG (compact, one line per item):
{parts_data}

How to read the catalog:
- Only lines that start with "I|" are items.
- Format is I|Category|Name $Price. The $Price belongs to that Name on the same line.
- Use these prices for your internal comparisons, but do not output any prices.
- Treat these catalog prices as the ONLY valid prices; do not estimate or infer prices from anywhere else.

COST RULES (hard constraints):
- Absolute budget cap: ${adjusted_budget if adjusted_budget else 'use max in context'}.
- Choose variants using the catalog prices to stay within budget; if needed, step down to cheaper options (including iGPU builds) while keeping compatibility and color.

BUDGET AND CONTEXT:
- Max total budget: {price_range}
- Use case: {session.answers.get('use_case', 'General use')}
- Color scheme: {session.answers.get('color', 'Black')}
- RGB preference (0-10): {session.answers.get('rgb_level', '5')}
- Aesthetics priority (0-10): {session.answers.get('aesthetics', '5')}
- Upgradeability: {session.answers.get('upgradeability', 'I might upgrade')}
- Extra notes: {session.answers.get('extra_notes', '')}

SPECIAL HANDLING FOR OPEN-ENDED INPUTS:
- If the user asked for budget advice (like "what's a good budget for gaming"), recommend a sensible budget range in your description
- If they mentioned specific games or use cases in their budget answer, incorporate that into the build recommendations
- Be conversational and helpful - explain why you're choosing certain budget ranges or components

Important output rules:
- Do not include any prices or currency symbols in your output EXCEPT in the final section titled DEBUG PRICE CHECK.
- Keep the structure below exactly so the app can parse it.
- Before you output, quickly sum the catalog prices of your chosen parts. If the total exceeds the cap, revise parts and re-check. Do not output until the total is under the cap.

Selection guidance:
- Value first. Spend where it matters (CPU/GPU/SSD), then refine cooling and looks.
- Keep parts physically/electrically compatible. Check sockets, size clearances, headers, and connectors.
- Storage: only use m.2 ssd for the primary drive. only use sata if it clearly helps the user.
- Cooling: prefer stock cooler unless clearly necessary; do not add extra fans unless necessary or included by the case.
- PSU: cheaper power supplies are acceptable when reputable; prefer lower-cost PSUs that meet wattage needs.
- If aesthetics priority is low, pick the cheapest acceptable variant of a given GPU model that matches the colour.
- If a dGPU strains the budget, consider a capable APU/iGPU path and call it out.
- CASE: You MUST select a case from the catalog. Choose one that matches the color preference and provides good airflow. Do not skip the case selection.

Parts to avoid:
- Older GPUs
- The rtx 3050 is not good value. avoid using unless the user says specifically they want dlss or a 3050 
- Corsair Liquid coolers (strongly avoid)
- Power supplies with mismatched coloured cables (mustard cables) *strongly avoid*

Parts to prefer:
- Ryzen CPUs
- AMD GPUs
- Intel arc b580
- Avoid core ultra
- Motherboards with built in wifi/bluetooth

PERFORMANCE TIERLIST (reference only):
RTX 5090 32GB............... 100
RTX Pro 6000 Blackwell 96GB.  90
RX 7900 XTX 24GB............  75
RTX 5080 16GB...............  74
RX 9070 XT 16GB.............  67
RTX 5070 Ti 16GB............  66
RX 9070 16GB................  62
RTX 4070 Ti Super 16GB......  61
RTX 5070 12GB...............  55
RTX 4070 Super 12GB.........  53
RTX 4070 12GB...............  51
RX 7800 XT 16GB.............  50
RTX 5060 Ti 16GB............  48
RTX 5060 Ti 8GB.............  47
RX 9060 XT 16GB.............  46
RTX 4060 Ti 8GB.............  45
RTX 5060 8GB................  44
RX 9060 XT 8GB..............  44
Intel Arc B580 12GB.........  42
RTX 4060 8GB................  40
RX 7600 8GB.................  38
RTX 3060 12GB...............  35
RTX 5050 8GB................  34
RTX 3050 6GB................  28

OUTPUT FORMAT (strict):
- Start with a single-line build name.
- Then write 2-3 short paragraphs describing:
  • Why this build fits {session.answers.get('use_case', 'General use')} and the aesthetic focus
  • Expected performance and thermals/noise
  • How the look matches {session.answers.get('color', 'Black')}/{session.answers.get('rgb_level', '5')} and the upgrade path
- Add the exact title: COMPONENT BREAKDOWN
  Then list components in this exact order, one line each:
  CPU, SSD, (optional) HDD, Case, Power Supply, CPU Cooler, Graphics Card, RAM, Motherboard, (optional) Fans
  After each line, add 1-3 sentences explaining the choice (fit/compatibility/benefit), then a line with just ---
- Add the exact title: EXTRA NOTES and briefly address any special considerations from the user notes.
- Add the exact title: DEBUG PRICE CHECK
  Then list each selected component and its price from the catalog on its own line in the form:
  CPU = $<price>
  SSD = $<price>
  (optional) HDD = $<price>
  Case = $<price>
  Power Supply = $<price>
  CPU Cooler = $<price>
  Graphics Card = $<price or $0 if using iGPU>
  RAM = $<price>
  Motherboard = $<price>
  TOTAL = $<sum of above using catalog prices>

MANDATORY COMPONENTS (exactly once): CPU, Graphics Card (or "None (using iGPU)"), SSD, Case (MUST be selected from catalog), Power Supply, RAM, Motherboard.

CRITICAL: You must include ALL mandatory components. The Case is NOT optional - you must pick a specific case from the catalog that matches the user's color preference.

FINAL CHECKS BEFORE YOU FINISH:
- You must output exactly ONE single complete build (one COMPONENT BREAKDOWN). Do not include alternates or multiple builds.
- Keep the total within the max budget.
- Ensure no prices are shown anywhere in your text except DEBUG PRICE CHECK.
- Keep the exact section titles so the UI can parse them.
- VERIFY: You have selected a Case from the catalog. The Case line must show a specific case model, not "None" or be missing.
"""
        return prompt
    
    async def generate_build(self, session: PCBuilderSession) -> str:
        """Generate a PC build based on session answers"""
        try:
            logger.info(f"Starting build generation for user {session.user_id}")
            
            parts_data = self.load_parts_data()
            if not parts_data:
                logger.error("Parts data is empty or missing")
                return "❌ Error: Could not load parts data. Please contact an administrator."
            
            logger.info(f"Loaded parts data: {len(parts_data)} characters")
            
            prompt = self.build_prompt(session, parts_data)
            logger.info(f"Generated prompt: {len(prompt)} characters")
            
            response = self.model.generate_content(prompt, request_options={'timeout': 30})
            logger.info("Received response from Gemini")
            
            result = getattr(response, 'text', '') or ''
            if not result:
                logger.error("Empty response from Gemini")
                return "❌ Error: Could not generate build recommendation. Please try again."
            
            logger.info(f"Generated build result: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error generating build: {e}")
            return f"❌ Error generating build: {str(e)}"
    
    async def handle_refinement_message(self, session: PCBuilderSession, user_message: str, build_result: str) -> str:
        """Handle refinement conversation after initial build"""
        try:
            parts_data = self.load_parts_data()
            if not parts_data:
                return "❌ Error: Could not load parts data for refinement."
            
            # Build refinement prompt similar to the web chatbot
            prompt = f"""
You are a friendly PC build assistant helping refine an existing build. The user has already received their initial build recommendation and wants to make changes or ask questions.

CURRENT BUILD:
{build_result}

USER'S REQUEST:
{user_message}

USER PREFERENCES:
- Budget: {session.answers.get('budget', 'N/A')}
- Use Case: {session.answers.get('use_case', 'N/A')}
- Color: {session.answers.get('color', 'N/A')}
- RGB Level: {session.answers.get('rgb_level', 'N/A')}/10
- Aesthetics: {session.answers.get('aesthetics', 'N/A')}/10
- Upgradeability: {session.answers.get('upgradeability', 'N/A')}
- Extra Notes: {session.answers.get('extra_notes', 'N/A')}

PARTS CATALOG (for reference):
{parts_data}

Instructions:
- Be conversational and helpful, like you're chatting with a friend
- If they want to change parts, suggest specific alternatives from the catalog
- If they're asking questions, give detailed but easy-to-understand answers
- If they want to upgrade/downgrade, explain the trade-offs
- When users ask for recommendations, provide helpful suggestions based on their needs
- Keep responses SHORT - under 100 words for Discord
- Always end with a single question to keep the conversation flowing
- Don't mention specific prices unless they ask
- Focus on value, performance, and compatibility
- DO NOT ask questions about specific components - only respond to their requests

Remember: You're helping them get the perfect PC, so be enthusiastic and knowledgeable!
"""
            
            response = self.model.generate_content(prompt, request_options={'timeout': 30})
            result = getattr(response, 'text', '') or ''
            
            if not result:
                return "I'm here to help! What would you like to know about your build or what changes are you thinking about?"
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling refinement: {e}")
            return f"Sorry, I ran into an issue there. What were you thinking about changing or asking about your build?"

# Initialize components
session_manager = SessionManager()
conversational_flow = ConversationalFlow()
build_generator = PCBuildGenerator()

def are_all_fields_collected(session):
    """Check if all required fields have been collected"""
    required_fields = conversational_flow.REQUIRED_FIELDS
    collected_fields = set()
    
    # Check session.answers
    for field in required_fields:
        if field in session.answers and session.answers[field]:
            collected_fields.add(field)
    
    # Also check chat history for any additional information
    chat_text = " ".join([msg.get('text', '') for msg in session.chat_history]).lower()
    
    # Look for budget mentions
    if 'budget' not in collected_fields:
        if any(word in chat_text for word in ['$', 'dollar', 'budget', 'price', 'cost', 'around', 'under', 'over']):
            if any(char.isdigit() for char in chat_text):
                collected_fields.add('budget')
    
    # Look for color mentions
    if 'color' not in collected_fields:
        colors = ['black', 'white', 'red', 'blue', 'green', 'pink', 'purple', 'rgb']
        if any(color in chat_text for color in colors):
            collected_fields.add('color')
    
    # Look for rgb mentions
    if 'rgb_level' not in collected_fields:
        if any(word in chat_text for word in ['rgb', 'light', 'led', 'none', 'lots', 'some']):
            collected_fields.add('rgb_level')
    
    # Look for aesthetics mentions
    if 'aesthetics' not in collected_fields:
        if any(word in chat_text for word in ['look', 'aesthetic', 'style', 'performance', 'balanced']):
            collected_fields.add('aesthetics')
    
    # Look for use case mentions
    if 'use_case' not in collected_fields:
        games = ['fortnite', 'league', 'minecraft', 'valorant', 'gaming', 'streaming', 'work']
        if any(game in chat_text for game in games):
            collected_fields.add('use_case')
    
    # Look for upgrade mentions
    if 'upgradeability' not in collected_fields:
        if any(word in chat_text for word in ['upgrade', 'wont', "won't", 'might', 'will', 'nah']):
            collected_fields.add('upgradeability')
    
    # Look for extra notes
    if 'extra_notes' not in collected_fields:
        if any(word in chat_text for word in ['special', 'request', 'requirement', 'need', 'want', 'none', 'no', 'nah']):
            collected_fields.add('extra_notes')
    
    # Check if we have all 7 fields
    essential_fields = ['budget', 'color', 'rgb_level', 'aesthetics', 'use_case', 'upgradeability', 'extra_notes']
    essential_collected = sum(1 for field in essential_fields if field in collected_fields)
    
    return essential_collected >= 7

def get_build_number():
    """Get the next build number"""
    collective_file = os.path.join(SCRIPT_DIR, 'collective_builds.txt')
    if os.path.exists(collective_file):
        try:
            with open(collective_file, 'r', encoding='utf-8') as f:
                content = f.read()
                build_count = content.count('=== BUILD #')
                return build_count + 1
        except:
            return 1
    return 1

async def save_build_to_collective_file(session):
    """Save completed build to collective file with AI-generated compressed responses"""
    try:
        # Use AI to generate compressed entry instead of raw data extraction
        conversation_text = " ".join([f"{msg['role']}: {msg['text']}" for msg in session.chat_history])
        build_text = session.build_result[:1000] if session.build_result else ""
        feedback_text = session.user_feedback if session.user_feedback else ""
        
        # Create AI prompt for compressed entry
        compression_prompt = f"""
Create a compressed PC build entry like this example format:

white
8/10
7/10
fortnite
mid-range
EN: user showed confusion about amd and nvidia, wanted a build around fortnite
RTX5060
2TB SSD
AMD CPU
RAM
Motherboard
PSU
Case
loved it

Based on this conversation and build:
CONVERSATION: {conversation_text}
BUILD: {build_text}
FEEDBACK: {feedback_text}

Respond with ONLY the compressed entry, one item per line, no labels or formatting.
"""
        
        try:
            response = build_generator.model.generate_content(compression_prompt, request_options={'timeout': 15})
            compressed_entry = getattr(response, 'text', '').strip()
            
            if not compressed_entry:
                # Fallback to old method if AI fails
                params = extract_simplified_params(session)
                ai_notes = extract_ai_notes(session)
                parts = extract_parts_from_build(session.build_result)
                user_feedback = session.user_feedback
                compressed_entry = format_collective_entry(params, ai_notes, parts, user_feedback)
        except:
            # Fallback to old method if AI fails
            params = extract_simplified_params(session)
            ai_notes = extract_ai_notes(session)
            parts = extract_parts_from_build(session.build_result)
            user_feedback = session.user_feedback
            compressed_entry = format_collective_entry(params, ai_notes, parts, user_feedback)
        
        # Add timestamp and build number
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        build_number = get_build_number()
        
        # Write to collective file with file locking
        collective_file = os.path.join(SCRIPT_DIR, 'collective_builds.txt')
        with FileLock(COLLECTIVE_LOCK_FILE):
            with open(collective_file, 'a', encoding='utf-8') as f:
                f.write(f"=== BUILD #{build_number} - {timestamp} ===\n")
                f.write(compressed_entry)
                f.write('\n\n')
            
        logger.info(f"Saved AI-compressed build #{build_number} to collective file")
        
    except Exception as e:
        logger.error(f"Error saving to collective file: {e}")

def extract_simplified_params(session):
    """Extract simplified user parameters from session"""
    params = {}
    
    # Extract key parameters from answers
    if 'budget' in session.answers:
        budget = session.answers['budget']
        # Simplify budget
        if 'around' in budget.lower() or 'about' in budget.lower():
            params['budget'] = budget
        else:
            params['budget'] = budget
    
    if 'color' in session.answers:
        params['color'] = session.answers['color']
    
    if 'rgb_level' in session.answers:
        params['rgb_level'] = session.answers['rgb_level']
    
    if 'aesthetics' in session.answers:
        params['aesthetics'] = session.answers['aesthetics']
    
    if 'use_case' in session.answers:
        params['use_case'] = session.answers['use_case']
    
    if 'upgradeability' in session.answers:
        params['upgradeability'] = session.answers['upgradeability']
    
    if 'extra_notes' in session.answers:
        params['extra_notes'] = session.answers['extra_notes']
    
    return params

def extract_ai_notes(session):
    """Extract AI notes about user confusion/needs from chat history"""
    notes = []
    
    # Look for patterns indicating confusion or specific needs
    chat_text = " ".join([msg.get('text', '') for msg in session.chat_history]).lower()
    
    # Check for AMD/NVIDIA confusion
    if 'amd' in chat_text and 'nvidia' in chat_text:
        notes.append("user showed confusion about amd and nvidia")
    
    # Check for specific game mentions
    games = ['fortnite', 'league', 'minecraft', 'valorant', 'csgo', 'cyberpunk', 'elden ring']
    for game in games:
        if game in chat_text:
            notes.append(f"wanted a build around {game}")
            break
    
    # Check for budget confusion
    if any(word in chat_text for word in ['idk', 'dont know', "don't know", 'not sure', 'maybe']):
        if any(word in chat_text for word in ['budget', 'price', 'cost']):
            notes.append("user was unsure about budget")
    
    # Check for color confusion
    if any(word in chat_text for word in ['idk', 'dont know', "don't know", 'not sure']):
        if any(word in chat_text for word in ['color', 'colour', 'theme']):
            notes.append("user was unsure about color preference")
    
    # Check for RGB confusion
    if any(word in chat_text for word in ['idk', 'dont know', "don't know", 'not sure']):
        if any(word in chat_text for word in ['rgb', 'light', 'led']):
            notes.append("user was unsure about rgb preference")
    
    # Check for resolution questions
    if any(word in chat_text for word in ['resolution', '1080p', '1440p', '4k']):
        notes.append("user asked about resolution preferences")
    
    # Check for upgrade confusion
    if any(word in chat_text for word in ['upgrade', 'upgrading']):
        if any(word in chat_text for word in ['idk', 'dont know', "don't know", 'not sure', 'maybe']):
            notes.append("user was unsure about upgrade plans")
    
    # If no specific notes, check for general confusion
    if not notes:
        if any(word in chat_text for word in ['idk', 'dont know', "don't know", 'not sure', 'maybe', 'confused']):
            notes.append("user showed general uncertainty")
    
    return notes

def extract_parts_from_build(build_result):
    """Extract parts list from build result"""
    parts = []
    lines = build_result.split('\n')
    
    for line in lines:
        if ':' in line and not line.startswith('http') and len(line) < 200:
            # Extract component type and name
            if line.strip():
                parts.append(line.strip())
    
    return parts

def format_collective_entry(params, ai_notes, parts, user_feedback):
    """Format the collective entry in compressed format like the image example"""
    entry = []
    
    # User parameters (simplified by AI)
    simplified_params = []
    
    # Color
    if 'color' in params:
        color = params['color'].lower()
        if 'black' in color:
            simplified_params.append('black')
        elif 'white' in color:
            simplified_params.append('white')
        else:
            simplified_params.append(color.split()[0])  # Take first word
    
    # RGB Level
    if 'rgb_level' in params:
        rgb = params['rgb_level']
        import re
        match = re.search(r'(\d+)', str(rgb))
        if match:
            simplified_params.append(f"{match.group(1)}/10")
        elif 'none' in str(rgb).lower():
            simplified_params.append('0/10')
        elif 'lots' in str(rgb).lower() or 'max' in str(rgb).lower():
            simplified_params.append('10/10')
        else:
            simplified_params.append('5/10')
    
    # Aesthetics
    if 'aesthetics' in params:
        aesthetics = params['aesthetics']
        import re
        match = re.search(r'(\d+)', str(aesthetics))
        if match:
            simplified_params.append(f"{match.group(1)}/10")
        elif 'performance' in str(aesthetics).lower():
            simplified_params.append('3/10')
        elif 'balanced' in str(aesthetics).lower():
            simplified_params.append('5/10')
        elif 'looks' in str(aesthetics).lower():
            simplified_params.append('8/10')
        else:
            simplified_params.append('5/10')
    
    # Use Case
    if 'use_case' in params:
        use_case = params['use_case'].lower()
        if 'fortnite' in use_case:
            simplified_params.append('fortnite')
        elif 'league' in use_case:
            simplified_params.append('league')
        elif 'gaming' in use_case:
            simplified_params.append('gaming')
        elif 'streaming' in use_case:
            simplified_params.append('streaming')
        else:
            simplified_params.append('general')
    
    # Budget (simplified)
    if 'budget' in params:
        budget = params['budget'].lower()
        import re
        match = re.search(r'(\d+)', budget)
        if match:
            amount = int(match.group(1))
            if amount < 600:
                simplified_params.append('budget')
            elif amount < 1000:
                simplified_params.append('mid-range')
            else:
                simplified_params.append('high-end')
        else:
            simplified_params.append('mid-range')
    
    # Add simplified params
    entry.extend(simplified_params)
    
    # AI Notes (compressed)
    if ai_notes:
        entry.append(f"EN: {ai_notes[0] if ai_notes else 'no special notes'}")
    
    # Parts (simplified)
    if parts:
        simplified_parts = []
        for part in parts[:8]:  # Limit to 8 most important parts
            if ':' in part:
                part_name = part.split(':', 1)[1].strip()
                # Extract key components
                if 'rtx' in part_name.lower():
                    simplified_parts.append('RTX5060')  # Generic RTX
                elif 'ssd' in part_name.lower() or 'nvme' in part_name.lower():
                    if '2tb' in part_name.lower():
                        simplified_parts.append('2TB SSD')
                    elif '1tb' in part_name.lower():
                        simplified_parts.append('1TB SSD')
                    else:
                        simplified_parts.append('SSD')
                elif 'ryzen' in part_name.lower():
                    simplified_parts.append('AMD CPU')
                elif 'intel' in part_name.lower():
                    simplified_parts.append('Intel CPU')
                elif 'ram' in part_name.lower() or 'memory' in part_name.lower():
                    simplified_parts.append('RAM')
                elif 'motherboard' in part_name.lower():
                    simplified_parts.append('Motherboard')
                elif 'power supply' in part_name.lower() or 'psu' in part_name.lower():
                    simplified_parts.append('PSU')
                elif 'case' in part_name.lower():
                    simplified_parts.append('Case')
        
        if simplified_parts:
            entry.extend(simplified_parts)
        else:
            entry.append('ETC')
    
    # User feedback (summarized)
    if user_feedback:
        feedback = user_feedback.lower()
        if 'love' in feedback or 'perfect' in feedback or 'great' in feedback:
            entry.append('loved it')
        elif 'expensive' in feedback or 'too much' in feedback:
            entry.append('too expensive')
        elif 'good' in feedback or 'nice' in feedback:
            entry.append('liked it')
        elif 'bad' in feedback or 'hate' in feedback:
            entry.append('didnt like')
        else:
            entry.append('mixed feelings')
    
    return '\n'.join(entry)

async def save_session_compressed(user_id, session):
    """Save session in compressed text format instead of JSON"""
    try:
        # Create compressed session data
        compressed_data = []
        
        # Add timestamp and user info with instance ID
        compressed_data.append(f"[{session.last_activity}] User:{user_id} Instance:{INSTANCE_ID}")
        
        # Add all user settings with values
        if session.answers:
            settings = []
            for key, value in session.answers.items():
                settings.append(f"{key}={value}")
            if settings:
                compressed_data.append(f"Settings: {','.join(settings)}")
        
        # Add concerns/issues from chat
        concerns = []
        chat_text = " ".join([msg.get('text', '') for msg in session.chat_history]).lower()
        
        if any(word in chat_text for word in ['confused', 'dont know', "don't know", 'not sure', 'idk', 'maybe']):
            concerns.append('user uncertainty')
        
        if any(word in chat_text for word in ['amd', 'nvidia']) and any(word in chat_text for word in ['confused', 'which', 'better']):
            concerns.append('gpu brand confusion')
        
        if any(word in chat_text for word in ['expensive', 'too much', 'budget']):
            concerns.append('budget concerns')
        
        if any(word in chat_text for word in ['fortnite', 'league', 'minecraft']):
            game = next((word for word in ['fortnite', 'league', 'minecraft'] if word in chat_text), None)
            if game:
                concerns.append(f'game-specific: {game}')
        
        if concerns:
            compressed_data.append(f"Concerns: {','.join(concerns)}")
        
        # Add AI-generated conversation summary
        if session.chat_history:
            conversation_text = " ".join([f"{msg['role']}: {msg['text']}" for msg in session.chat_history[-8:]])
            
            try:
                summary_prompt = f"""
Compress this Discord PC building conversation into 1-2 sentences maximum. Focus on key user needs and confusion:

{conversation_text}

Respond with just the compressed summary, no formatting.
"""
                response = build_generator.model.generate_content(summary_prompt, request_options={'timeout': 10})
                summary = getattr(response, 'text', '').strip()
                if summary:
                    compressed_data.append(f"Summary: {summary}")
            except:
                compressed_data.append("Summary: PC building conversation")
        
        # Add parts list (not in sentences)
        if session.build_result:
            parts = []
            lines = session.build_result.split('\n')
            for line in lines:
                if ':' in line and any(word in line.lower() for word in ['cpu', 'gpu', 'rtx', 'ssd', 'ram', 'case', 'motherboard', 'power supply']):
                    part = line.split(':', 1)[1].strip()
                    # Extract just the component name, not full description
                    if '(' in part:
                        part = part.split('(')[0].strip()
                    parts.append(part)
            
            if parts:
                compressed_data.append(f"Parts: {','.join(parts)}")
        
        # Add price if available
        if session.build_result:
            lines = session.build_result.split('\n')
            for line in lines:
                if 'TOTAL = $' in line:
                    price = line.split('TOTAL = $')[1].strip()
                    compressed_data.append(f"Price: ${price}")
                    break
        
        # Add user feedback if exists
        if session.user_feedback:
            compressed_data.append(f"Feedback: {session.user_feedback}")
        
        # Add build edits if any
        if session.build_edits:
            compressed_data.append(f"Edits: {','.join(session.build_edits)}")
        
        # Write to compressed sessions file with file locking
        sessions_file = os.path.join(SCRIPT_DIR, 'discord_sessions_compressed.txt')
        with FileLock(SESSIONS_LOCK_FILE):
            with open(sessions_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(compressed_data) + '\n\n')
            
    except Exception as e:
        logger.error(f"Error saving compressed session: {e}")

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Check if parts data file exists
    if not os.path.exists(PARTS_DATA_FILE):
        logger.error(f"CRITICAL: Parts data file not found: {PARTS_DATA_FILE}")
        logger.error("The bot will not function properly without this file!")
    else:
        logger.info(f"Parts data file found: {PARTS_DATA_FILE}")
    
    cleanup_task.start()

@tasks.loop(hours=6)
async def cleanup_task():
    """Clean up old sessions periodically"""
    session_manager.cleanup_old_sessions()

@bot.command(name='build', help='Start building a custom PC', case_insensitive=True)
async def start_build(ctx):
    """Start the PC building process in a private thread"""
    user_id = ctx.author.id
    
    # Check if user already has an active session
    if user_id in session_manager.sessions:
        await ctx.send("You already have an active PC build session! Use `!status` to check your progress.")
        return
    
    # Create a private thread for this build session
    thread_name = f"Start Building PC - {ctx.author.display_name}"
    
    # Check if thread already exists
    existing_thread = None
    for thread in ctx.channel.threads:
        if thread.name == thread_name and not thread.archived:
            existing_thread = thread
            break
    
    if existing_thread:
        await ctx.send(f"You already have an active build thread: {existing_thread.mention}")
        return
    
    # Create new private thread
    try:
        thread = await ctx.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            reason=f"PC build session for {ctx.author.display_name}"
        )
        
        # Add the user to the thread
        await thread.add_user(ctx.author)
        
        # Send confirmation to original channel
        await ctx.send(f"🖥️ Created your private build thread: {thread.mention}")
        
    except Exception as e:
        logger.error(f"Error creating thread: {e}")
        await ctx.send("❌ Could not create private thread. You may need administrator permissions.")
        return
    
    # Create new session
    session = session_manager.get_session(user_id)
    
    # Reset session to start fresh
    session.chat_history = []
    session.answers = {}
    session.conversation_mode = True
    session.refinement_mode = False
    session.build_result = ""
    await save_session_compressed(ctx.author.id, session)
    
    # Send the preloaded greeting in the thread
    embed = discord.Embed(
        title="🖥️ Hey! Let's build you an awesome PC!",
        description=conversational_flow.preloaded_greeting,
        color=0x00ff00
    )
    embed.add_field(
        name="📋 Available Commands",
        value="• `!restart` - Start over from beginning\n"
              "• `!parts` - Show current build parts\n"
              "• `!status` - Check build progress\n"
              "• `!cancel` - Cancel build session\n"
              "• `!health` - Check bot status\n"
              "• `!collective` - View all builds",
        inline=False
    )
    embed.set_footer(text="Type 'cancel' at any time to stop, or 'restart' to begin again")
    
    await thread.send(embed=embed)


async def generate_and_send_build(ctx, session: PCBuilderSession):
    """Generate and send the PC build"""
    
    # Show generating message
    thinking_embed = discord.Embed(
        title="🤔 Generating Your Custom PC Build...",
        description="This may take a moment while I analyze the latest parts and create your perfect build.",
        color=0xffaa00
    )
    thinking_msg = await ctx.send(embed=thinking_embed)
    
    # Generate the build
    build_result = await build_generator.generate_build(session)
    
    # Delete thinking message
    await thinking_msg.delete()
    
    # Store build result and enter refinement mode
    session.build_result = build_result
    session.refinement_mode = True
    await save_session_compressed(ctx.author.id, session)
    
    # Parse and send results
    await send_build_result(ctx, session, build_result)

async def send_build_result(ctx, session: PCBuilderSession, build_result: str):
    """Send the build result in a nice format"""
    
    if build_result.startswith("❌"):
        await ctx.send(build_result)
        return
    
    # Parse the build result
    lines = build_result.split('\n')
    build_name = lines[0] if lines else "Custom PC Build"
    
    # Extract description and components
    description_lines = []
    component_lines = []
    in_components = False
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        if "COMPONENT BREAKDOWN" in line.upper():
            in_components = True
            continue
        elif "DEBUG PRICE CHECK" in line.upper():
            break
        elif "EXTRA NOTES" in line.upper():
            break
        
        if in_components:
            if line and not line.startswith('---'):
                component_lines.append(line)
        else:
            if line and not line.startswith('#'):
                description_lines.append(line)
    
    # Create main embed
    main_embed = discord.Embed(
        title=f"🖥️ {build_name}",
        description='\n\n'.join(description_lines[:3]) if description_lines else "Your custom PC build is ready!",
        color=0x00ff00
    )
    
    
    await ctx.send(embed=main_embed)
    
    # Send components (without images for now)
    if component_lines:
        for line in component_lines:
            if ':' in line:
                # Extract component type and name
                component_type = line.split(':')[0].strip()
                component_name = line.split(':', 1)[1].strip()
                
                # Create component embed
                component_embed = discord.Embed(
                    title=f"🔧 {component_type}",
                    description=f"**{component_name}**",
                    color=0x0099ff
                )
                
                # Add next few lines as description if they're not component headers
                desc_lines = []
                try:
                    current_idx = component_lines.index(line)
                    for i in range(current_idx + 1, min(current_idx + 3, len(component_lines))):
                        next_line = component_lines[i]
                        if ':' in next_line and not next_line.startswith(' '):
                            break  # Next component
                        if next_line.strip() and not next_line.startswith('---'):
                            desc_lines.append(next_line.strip())
                except:
                    pass
                
                if desc_lines:
                    component_embed.add_field(
                        name="Why This Part",
                        value='\n'.join(desc_lines)[:1000],
                        inline=False
                    )
                
                await ctx.send(embed=component_embed)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
    
    # Send full build as file for easy copying
    import io
    build_file = discord.File(
        fp=io.StringIO(build_result),
        filename=f"pc_build_{session.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    
    file_embed = discord.Embed(
        title="📄 Complete Build Details",
        description="Here's your complete build specification as a text file for easy sharing!",
        color=0x9932cc
    )
    
    await ctx.send(embed=file_embed, file=build_file)
    
    # Ask for user feedback first
    feedback_embed = discord.Embed(
        title="📝 Quick Feedback",
        description="**Did you like this build?** Please let me know what you think!",
        color=0x0099ff
    )
    feedback_embed.add_field(
        name="Examples:",
        value="• \"Love it!\"\n• \"Too expensive\"\n• \"Perfect for Fortnite\"\n• \"Need more RGB\"",
        inline=False
    )
    feedback_embed.set_footer(text="Your feedback helps improve future builds")
    
    await ctx.send(embed=feedback_embed)
    
    # Set feedback mode
    session.feedback_mode = True

@bot.event
async def on_message(message):
    """Handle user messages"""
    if message.author == bot.user:
        return
    
    # Check if user has an active session
    user_id = message.author.id
    if user_id not in session_manager.sessions:
        await bot.process_commands(message)
        return
    
    session = session_manager.get_session(user_id)
    
    # Check for special commands
    if message.content.lower() == 'cancel':
        session_manager.clear_session(user_id)
        await message.channel.send("❌ PC build cancelled. Use `!build` to start again.")
        return
    
    if message.content.lower() == 'restart':
        # Clear the session completely
        session_manager.clear_session(user_id)
        
        # Start a new session
        new_session = session_manager.get_session(user_id)
        new_session.conversation_mode = True
        
        # Send restart message and start conversation
        restart_embed = discord.Embed(
            title="🔄 Restarting PC Build",
            description="Starting fresh! Let's build you an awesome PC from scratch.",
            color=0xffaa00
        )
        restart_embed.add_field(
            name="What's Next?",
            value="I'll ask you some questions to understand what you need, then generate your perfect build!",
            inline=False
        )
        restart_embed.add_field(
            name="📋 Available Commands",
            value="• `!restart` - Start over from beginning\n"
                  "• `!parts` - Show current build parts\n"
                  "• `!status` - Check build progress\n"
                  "• `!cancel` - Cancel build session\n"
                  "• `!health` - Check bot status\n"
                  "• `!collective` - View all builds",
            inline=False
        )
        restart_embed.set_footer(text="Type 'cancel' at any time to stop")
        
        await message.channel.send(embed=restart_embed)
        
        # Start the conversation
        await handle_conversation_mode(message, new_session)
        return
    
    # Handle feedback mode
    if session.feedback_mode:
        session.user_feedback = message.content
        session.feedback_mode = False
        
        # Save build to collective file
        await save_build_to_collective_file(session)
        
        # Send refinement invitation
        refinement_embed = discord.Embed(
            title="💬 Want to Refine Your Build?",
            description="Thanks for the feedback! I'm here if you want to make changes or ask questions! You can:\n\n"
                       "• Ask about specific parts or performance\n"
                       "• Request upgrades or downgrades\n"
                       "• Change colors, RGB, or aesthetics\n"
                       "• Get compatibility advice\n"
                       "• Or just chat about your build!\n\n"
                       "Just type your question or request, and I'll help you out! 🚀",
            color=0x9932cc
        )
        refinement_embed.set_footer(text="Type 'done' when you're happy with your build, or 'restart' to start over")
        
        await message.channel.send(embed=refinement_embed)
        session.refinement_mode = True
        return
    
    if message.content.lower() == 'done':
        session_manager.clear_session(user_id)
        await message.channel.send("🎉 Awesome! Enjoy your new PC build! Use `!build` anytime to create another build.")
        return
    
    # Handle refinement mode
    if session.refinement_mode:
        await handle_refinement_conversation(message, session)
        return
    
    # Handle conversation mode
    if session.conversation_mode:
        await handle_conversation_mode(message, session)
        return
    
    # If no active mode, ignore messages
    await bot.process_commands(message)

async def handle_conversation_mode(message, session: PCBuilderSession):
    """Handle the conversational PC building flow"""
    try:
        # Add user message to chat history
        session.chat_history.append({'role': 'user', 'text': message.content})
        
        # Show typing indicator
        async with message.channel.typing():
            # Build conversation prompt
            prompt = conversational_flow.build_conversation_prompt(session.chat_history, session.answers)
            
            # Get response from Gemini
            response = build_generator.model.generate_content(prompt, request_options={'timeout': 30})
            ai_text = getattr(response, 'text', '') or ''
            
            if not ai_text:
                ai_text = "I'm here to help! What would you like to know about building a PC?"
            
            # Check if ready to build
            if '<READY_TO_BUILD>' in ai_text:
                ai_text = ai_text.replace('<READY_TO_BUILD>', '').strip()
                await generate_build_from_conversation(message.channel, session)
                return
            
            # Also check if all required fields are collected (backup detection)
            if are_all_fields_collected(session):
                logger.info(f"All fields collected for user {session.user_id}, auto-triggering build generation")
                await generate_build_from_conversation(message.channel, session)
                return
            
            # Add AI response to chat history
            session.chat_history.append({'role': 'assistant', 'text': ai_text})
            
            # Send response
            embed = discord.Embed(
                title="💬 PC Builder Assistant",
                description=ai_text,
            color=0x00ff00
        )
            embed.set_footer(text="Type 'cancel' to stop, or 'restart' to begin again")
            
            await message.channel.send(embed=embed)
            
            # Update session activity
            session.update_activity()
            await save_session_compressed(message.author.id, session)
            
    except Exception as e:
        logger.error(f"Error in conversation mode: {e}")
        await message.channel.send("Sorry, I ran into an issue there. What would you like to know about building a PC?")

async def generate_build_from_conversation(channel, session: PCBuilderSession):
    """Generate build from conversational answers"""
    try:
        # Show generating message
        thinking_embed = discord.Embed(
            title="🤔 Generating Your Custom PC Build...",
            description="This may take a moment while I analyze the latest parts and create your perfect build.",
            color=0xffaa00
        )
        thinking_msg = await channel.send(embed=thinking_embed)
        
        # Generate the build using the answers from conversation
        build_result = await build_generator.generate_build(session)
        
        # Delete thinking message
        await thinking_msg.delete()
        
        # Store build result and enter refinement mode
        session.build_result = build_result
        session.refinement_mode = True
        session.conversation_mode = False
        await save_session_compressed(session.user_id, session)
        
        # Parse and send results
        await send_build_result(channel, session, build_result)
        
    except Exception as e:
        logger.error(f"Error generating build from conversation: {e}")
        error_embed = discord.Embed(
            title="❌ Build Generation Error",
            description=f"Sorry, I ran into an issue generating your build: `{str(e)[:100]}`\n\nPlease try again or contact support if the issue persists.",
            color=0xff0000
        )
        await channel.send(embed=error_embed)

async def handle_refinement_conversation(message, session: PCBuilderSession):
    """Handle refinement conversation after build is complete"""
    try:
        # Track what the user said for build edits
        if message.content.lower() not in ['done', 'restart', 'cancel']:
            session.build_edits.append(message.content)
        
        # Show typing indicator
        async with message.channel.typing():
            # Get refinement response
            refinement_response = await build_generator.handle_refinement_message(
                session, message.content, session.build_result
            )
            
            # Check if the response indicates changes were made (look for keywords)
            user_message = message.content.lower()
            made_changes = any(word in user_message for word in [
                'change', 'upgrade', 'downgrade', 'replace', 'swap', 'different', 
                'better', 'cheaper', 'more', 'less', 'instead', 'rather', 'prefer'
            ])
            
            # Send response
            embed = discord.Embed(
                title="💬 Build Assistant",
                description=refinement_response,
                color=0x00ff00
            )
            embed.set_footer(text="Type 'done' when finished, or 'restart' to start over")
            
            await message.channel.send(embed=embed)
            
            # If changes were requested, regenerate and show updated build
            if made_changes and 'change' in refinement_response.lower():
                await message.channel.send("🔄 **Regenerating your build with the requested changes...**")
                
                # Generate new build with updated parameters
                new_build_result = await build_generator.generate_build(session)
                
                # Update session with new build
                session.build_result = new_build_result
                
                # Send updated build result
                await send_build_result(message.channel, session, new_build_result)
            
            # Update session activity
            session.update_activity()
            await save_session_compressed(message.author.id, session)
            
    except Exception as e:
        logger.error(f"Error in refinement conversation: {e}")
        await message.channel.send("Sorry, I ran into an issue there. What were you thinking about changing or asking about your build?")

@bot.command(name='cancel', help='Cancel current PC build session', case_insensitive=True)
async def cancel_build(ctx):
    """Cancel current build session"""
    user_id = ctx.author.id
    if user_id in session_manager.sessions:
        session_manager.clear_session(user_id)
        await ctx.send("❌ PC build session cancelled.")
    else:
        await ctx.send("ℹ️ No active PC build session to cancel.")

@bot.command(name='restart', help='Restart PC build from the beginning', case_insensitive=True)
async def restart_build(ctx):
    """Restart the PC build from the beginning"""
    user_id = ctx.author.id
    
    if user_id not in session_manager.sessions:
        await ctx.send("❌ No active PC build session found. Use `!build` to start.")
        return
    
    # Clear the session completely
    session_manager.clear_session(user_id)
    
    # Start a new build session
    session = session_manager.get_session(user_id)
    session.conversation_mode = True
    
    # Send restart message
    restart_embed = discord.Embed(
        title="🔄 Restarting PC Build",
        description="Starting fresh! Let's build you an awesome PC from scratch.",
        color=0xffaa00
    )
    restart_embed.add_field(
        name="What's Next?",
        value="I'll ask you some questions to understand what you need, then generate your perfect build!",
        inline=False
    )
    restart_embed.add_field(
        name="📋 Available Commands",
        value="• `!restart` - Start over from beginning\n"
              "• `!parts` - Show current build parts\n"
              "• `!status` - Check build progress\n"
              "• `!cancel` - Cancel build session\n"
              "• `!health` - Check bot status\n"
              "• `!collective` - View all builds",
        inline=False
    )
    restart_embed.set_footer(text="Type 'cancel' at any time to stop")
    
    await ctx.send(embed=restart_embed)
    
    # Start the conversation
    await handle_conversation_mode(ctx, session)

@bot.command(name='parts', help='Show current build parts list', case_insensitive=True)
async def show_parts(ctx):
    """Show the current build parts list"""
    user_id = ctx.author.id
    
    if user_id not in session_manager.sessions:
        await ctx.send("❌ No active PC build session found. Use `!build` to start.")
        return
    
    session = session_manager.get_session(user_id)
    
    if not session.build_result:
        await ctx.send("❌ No build generated yet. Complete the conversation first.")
        return
    
    # Parse and show the current parts
    await send_build_result(ctx, session, session.build_result)

@bot.command(name='status', help='Check current build session status', case_insensitive=True)
async def build_status(ctx):
    """Check build session status"""
    user_id = ctx.author.id
    if user_id in session_manager.sessions:
        session = session_manager.sessions[user_id]
        
        embed = discord.Embed(
            title="📊 Build Session Status",
            color=0x0099ff
        )
        
        if session.refinement_mode:
            embed.add_field(
                name="Status",
                value="🎉 Build complete! In refinement mode - you can ask questions or request changes",
                inline=False
            )
        elif session.conversation_mode:
            collected_fields = len([k for k in conversational_flow.REQUIRED_FIELDS if session.answers.get(k)])
            embed.add_field(
                name="Status",
                value=f"💬 In conversation mode - {collected_fields}/{len(conversational_flow.REQUIRED_FIELDS)} fields collected",
                inline=False
            )
        else:
            embed.add_field(
                name="Status",
                value="ℹ️ No active session. Use `!build` to start!",
            inline=False
        )
        
        if session.answers:
            answers_text = ""
            for key, value in session.answers.items():
                answers_text += f"**{key.replace('_', ' ').title()}:** {value}\n"
            
            embed.add_field(
                name="Current Answers",
                value=answers_text[:1000] + ("..." if len(answers_text) > 1000 else ""),
                inline=False
            )
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("ℹ️ No active PC build session. Use `!build` to start!")

@bot.command(name='health', help='Check bot health and dependencies', case_insensitive=True)
async def health_check(ctx):
    """Check bot health and dependencies"""
    embed = discord.Embed(
        title="🏥 Bot Health Check",
        color=0x00ff00
    )
    
    # Check parts data file
    parts_status = "✅ Found" if os.path.exists(PARTS_DATA_FILE) else "❌ Missing"
    embed.add_field(name="Parts Data File", value=f"{parts_status}\n`{PARTS_DATA_FILE}`", inline=False)
    
    # Check image cache
    image_status = "✅ Found" if os.path.exists(IMAGE_CACHE_FILE) else "⚠️ Optional (not found)"
    embed.add_field(name="Image Cache", value=image_status, inline=True)
    
    # Check API connection (basic test)
    try:
        # Quick test of Gemini API
        test_response = build_generator.model.generate_content("Test", request_options={'timeout': 5})
        api_status = "✅ Connected"
    except Exception as e:
        api_status = f"❌ Error: {str(e)[:50]}..."
    embed.add_field(name="Gemini API", value=api_status, inline=True)
    
    # Active sessions
    active_sessions = len(session_manager.sessions)
    embed.add_field(name="Active Sessions", value=str(active_sessions), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='collective', case_insensitive=True)
async def show_collective(ctx):
    """Show the collective builds file"""
    try:
        collective_file = os.path.join(SCRIPT_DIR, "collective_builds.txt")
        
        if not os.path.exists(collective_file):
            await ctx.send("📁 No collective builds file found yet. Complete a build to create one!")
            return
        
        # Read the file
        with open(collective_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file is too large for Discord
        if len(content) > 1900:  # Leave room for embed formatting
            # Send as file if too large
            file = discord.File(collective_file, filename="collective_builds.txt")
            embed = discord.Embed(
                title="📁 Collective Builds File",
                description="The file is too large to display here, so I've attached it as a file.",
                color=0x0099ff
            )
            await ctx.send(embed=embed, file=file)
        else:
            # Send as embed
            embed = discord.Embed(
                title="📁 Collective Builds",
                description=f"```\n{content}\n```",
                color=0x0099ff
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        logger.error(f"Error showing collective file: {e}")
        await ctx.send("❌ Error reading collective builds file.")

if __name__ == "__main__":
    print("Starting Discord bot...")
    print(f"Bot token: {BOT_TOKEN[:10]}...")
    
    # Check for required files before starting
    print(f"Looking for parts data file: {PARTS_DATA_FILE}")
    if not os.path.exists(PARTS_DATA_FILE):
        print(f"❌ WARNING: Parts data file not found: {PARTS_DATA_FILE}")
        print("The bot will not function properly without this file!")
        print("Please ensure the parts data file exists in the same directory as the bot script.")
        print()
    else:
        print(f"✅ Parts data file found: {PARTS_DATA_FILE}")
        print()
    
    print("Available commands:")
    print("- !build (or !Build) - Start building a PC")
    print("- !restart - Restart PC build from beginning")
    print("- !parts - Show current build parts list")
    print("- !status - Check your current build session")
    print("- !cancel - Cancel current build session")
    print("- !health - Check bot health and dependencies")
    print("- !collective - View collective builds file")
    print()
    
    print(f"🚀 Bot Instance ID: {INSTANCE_ID}")
    print("⚠️  IMPORTANT: Discord bots cannot run multiple instances with the same token!")
    print("   Each bot instance needs its own unique Discord token.")
    print("   File locking is implemented to prevent conflicts if multiple instances somehow run.")
    print()
    
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"Error starting bot: {e}")
        print("Common fixes:")
        print("1. Make sure discord.py is installed: pip install discord.py")
        print("2. Make sure google-generativeai is installed: pip install google-generativeai")
        print("3. Check if bot token is correct")
        print("4. Make sure latest_parts_formatted file exists")
        print("5. Check your internet connection")
        print("Bot startup failed. Check logs for details.")
