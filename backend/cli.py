#!/usr/bin/env python3
"""
Open-Brain Backend — Command Line Interface (CLI)

Supports:
1. Persistent sessions (via .session.json)
2. JWT Auto-refresh
3. Complete Registration and MFA Login Flows (Option A)
4. Interactive REPL Chat Loop with SSE Streaming
5. Quick direct CLI commands via argparse
"""

import argparse
import sys
import os
import json
import time
import getpass
from typing import Optional, Dict, Any, Generator

try:
    import httpx
except ImportError:
    print("Error: The 'httpx' package is required. Please install it using 'pip install httpx'.")
    sys.exit(1)

# --- Configuration ---
DEFAULT_BASE_URL = "http://localhost:8000"
SESSION_FILE = ".session.json"

# --- ANSI Escape Codes for Rich UI ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"

def print_err(text: str):
    print(f"{CLR_RED}{CLR_BOLD}Error:{CLR_RESET} {CLR_RED}{text}{CLR_RESET}")

def print_ok(text: str):
    print(f"{CLR_GREEN}{CLR_BOLD}Success:{CLR_RESET} {CLR_GREEN}{text}{CLR_RESET}")

def print_info(text: str):
    print(f"{CLR_CYAN}{text}{CLR_RESET}")

def print_warning(text: str):
    print(f"{CLR_YELLOW}{CLR_BOLD}Warning:{CLR_RESET} {CLR_YELLOW}{text}{CLR_RESET}")


# --- Session Storage Manager ---
class SessionManager:
    """Manages reading and writing local session tokens."""
    
    @staticmethod
    def save_session(access_token: str, refresh_token: str, email: str, base_url: str = DEFAULT_BASE_URL) -> None:
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "email": email,
            "base_url": base_url
        }
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_session() -> Optional[Dict[str, str]]:
        if not os.path.exists(SESSION_FILE):
            return None
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def clear_session() -> None:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)


# --- HTTP API Client with Auto-Refresh ---
class OpenBrainClient:
    """Session-aware client for interacting with the backend API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = SessionManager.load_session()
        self.client = httpx.Client(timeout=30.0)

    @property
    def is_logged_in(self) -> bool:
        return self.session is not None and "access_token" in self.session

    @property
    def email(self) -> str:
        return self.session.get("email", "") if self.session else ""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.is_logged_in:
            headers["Authorization"] = f"Bearer {self.session['access_token']}"
        return headers

    def _refresh_tokens(self) -> bool:
        """Attempt to rotate tokens using the refresh token."""
        if not self.session or "refresh_token" not in self.session:
            return False

        refresh_token = self.session["refresh_token"]
        print_info("\n[Session expired. Attempting token rotation...]")
        
        try:
            resp = self.client.post(
                f"{self.base_url}/auth/refresh",
                headers={"Authorization": f"Bearer {refresh_token}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.session["access_token"] = data["access_token"]
                if "refresh_token" in data:
                    self.session["refresh_token"] = data["refresh_token"]
                
                SessionManager.save_session(
                    access_token=self.session["access_token"],
                    refresh_token=self.session["refresh_token"],
                    email=self.session["email"],
                    base_url=self.base_url
                )
                print_ok("Session renewed successfully.")
                return True
        except Exception as e:
            pass
            
        print_err("Session expired. Please log in again.")
        SessionManager.clear_session()
        self.session = None
        return False

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an HTTP request and auto-retry on 401 after token refresh."""
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers

        resp = self.client.request(method, url, **kwargs)
        
        # Auto-refresh on Unauthorized
        if resp.status_code == 401 and self.is_logged_in:
            if self._refresh_tokens():
                # Retry with new headers
                kwargs["headers"] = self._get_headers()
                resp = self.client.request(method, url, **kwargs)
            else:
                raise httpx.HTTPStatusError(
                    "Session invalidated.", request=resp.request, response=resp
                )
        return resp

    def stream_chat(self, payload: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Send chat prompt and yield parsed Server-Sent Events (SSE)."""
        url = f"{self.base_url}/ai/chat"
        headers = self._get_headers()
        
        # We use a client-side stream connection
        with self.client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code == 401:
                # Attempt token refresh & retry once
                if self._refresh_tokens():
                    headers = self._get_headers()
                    with self.client.stream("POST", url, json=payload, headers=headers) as retry_response:
                        if retry_response.status_code != 200:
                            retry_response.read()
                            yield {"event": "error", "data": retry_response.json().get("detail", "Error starting stream")}
                            return
                        yield from self._parse_sse(retry_response)
                else:
                    yield {"event": "error", "data": "Session expired."}
                return

            if response.status_code != 200:
                response.read()
                yield {"event": "error", "data": response.json().get("detail", "Error starting stream")}
                return

            yield from self._parse_sse(response)

    def _parse_sse(self, response: httpx.Response) -> Generator[Dict[str, Any], None, None]:
        """Simple line-by-line parser for SSE format."""
        current_event = None
        for line in response.iter_lines():
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = data_str
                
                yield {"event": current_event or "message", "data": data}
                current_event = None


# =============================================================================
# API Operations Implementations
# =============================================================================

def register_flow(client: OpenBrainClient, email: str) -> bool:
    """Triggers OTP delivery with email and password, prompts for OTP, and completes registration."""
    try:
        password = getpass.getpass(prompt=f"{CLR_BOLD}Enter desired password (min 8 chars, incl. UPPER, lower, digit):{CLR_RESET} ")
        print_info(f"\nRequesting OTP code for {email}...")
        resp = client.request("POST", "/auth/register/send-otp", json={"email": email, "password": password})
        if resp.status_code != 200:
            print_err(resp.json().get("detail", "Failed to initiate registration / send OTP."))
            return False
        
        init_data = resp.json()
        registration_token = init_data.get("registration_token")
        if not registration_token:
            print_err("No registration token received from server.")
            return False

        print_ok("OTP code successfully requested via email.")
        
        otp = input(f"{CLR_BOLD}Enter 6-digit OTP code:{CLR_RESET} ").strip()
        
        print_info("\nRegistering account...")
        reg_payload = {
            "registration_token": registration_token,
            "email": email,
            "otp": otp
        }
        resp = client.request("POST", "/auth/register", json=reg_payload)
        
        if resp.status_code != 201:
            print_err(resp.json().get("detail", "Registration failed."))
            return False
            
        data = resp.json()
        SessionManager.save_session(data["access_token"], data["refresh_token"], email, client.base_url)
        client.session = SessionManager.load_session()
        print_ok(f"Account registration verified and completed! Saved session.")
        return True
    except Exception as e:
        print_err(f"Communication error: {e}")
        return False


def login_flow(client: OpenBrainClient, email: str) -> bool:
    """Option A MFA Login: Submits credentials, gets MFA token, prompts OTP."""
    password = getpass.getpass(prompt=f"{CLR_BOLD}Enter password:{CLR_RESET} ")
    print_info("\nVerifying credentials...")
    try:
        resp = client.request("POST", "/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            print_err(resp.json().get("detail", "Login failed (invalid credentials or rate-limited)."))
            return False

        data = resp.json()
        mfa_token = data.get("mfa_token")
        
        if not mfa_token:
            print_err("MFA Challenge failed. No MFA token received.")
            return False

        print_ok("Password verified. Multi-Factor OTP challenge sent.")
        
        otp = input(f"{CLR_BOLD}Enter 6-digit OTP code:{CLR_RESET} ").strip()
        print_info("\nCompleting MFA verification...")
        
        verify_payload = {"mfa_token": mfa_token, "otp": otp}
        resp = client.request("POST", "/auth/login/verify", json=verify_payload)
        
        if resp.status_code != 200:
            print_err(resp.json().get("detail", "OTP verification failed. Please try again."))
            return False
            
        final_tokens = resp.json()
        SessionManager.save_session(
            final_tokens["access_token"], 
            final_tokens["refresh_token"], 
            email, 
            client.base_url
        )
        client.session = SessionManager.load_session()
        print_ok("MFA Verification Successful! Welcome back.")
        return True
    except Exception as e:
        print_err(f"Communication error: {e}")
        return False


def view_profile(client: OpenBrainClient) -> None:
    if not client.is_logged_in:
        print_err("Not logged in.")
        return
    try:
        resp = client.request("GET", "/users/me")
        if resp.status_code == 200:
            data = resp.json()
            print(f"\n{CLR_BOLD}=== User Profile ==={CLR_RESET}")
            print(f"ID:          {data['id']}")
            print(f"Email:       {data['email']}")
            print(f"Verified:    {data['is_verified']}")
            print(f"Plan:        {data['plan']}")
            print(f"Created At:  {data['created_at']}")
            print("====================")
        else:
            print_err("Failed to retrieve profile.")
    except Exception as e:
        print_err(f"Error: {e}")


def list_chats(client: OpenBrainClient) -> None:
    if not client.is_logged_in:
        print_err("Not logged in.")
        return
    try:
        resp = client.request("GET", "/chats")
        if resp.status_code == 200:
            data = resp.json()
            conversations = data.get("conversations", [])
            print(f"\n{CLR_BOLD}=== Past Conversations ({data.get('total', len(conversations))}) ==={CLR_RESET}")
            if not conversations:
                print("No past chats found.")
            for c in conversations:
                cid = c.get("chat_id") or c.get("id") or "unknown"
                title = c.get("title") or "No Title"
                date_str = c.get("updated_at") or c.get("created_at") or ""
                date_part = f" ({date_str[:10]})" if date_str else ""
                print(f"[{cid}] {title}{date_part}")
            print("=========================================")
        else:
            print_err("Failed to retrieve conversations.")
    except Exception as e:
        print_err(f"Error: {e}")


def show_chat_history(client: OpenBrainClient, chat_id: str) -> None:
    if not client.is_logged_in:
        print_err("Not logged in.")
        return
    try:
        resp = client.request("GET", f"/chats/{chat_id}/history")
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("messages", [])
            print(f"\n{CLR_BOLD}=== Conversation: {data.get('title')} ==={CLR_RESET}")
            if not messages:
                print("No messages in this chat.")
            for m in messages:
                role_lbl = f"{CLR_GREEN}{CLR_BOLD}User{CLR_RESET}" if m['role'] == "user" else f"{CLR_BLUE}{CLR_BOLD}Assistant ({m.get('provider_used') or 'AI'}){CLR_RESET}"
                print(f"\n{role_lbl}:")
                print(m['content'])
            print("\n=========================================")
        else:
            print_err(f"Failed to retrieve history for chat ID {chat_id}.")
    except Exception as e:
        print_err(f"Error: {e}")


def delete_chat(client: OpenBrainClient, chat_id: str) -> None:
    if not client.is_logged_in:
        print_err("Not logged in.")
        return
    try:
        resp = client.request("DELETE", f"/chats/{chat_id}")
        if resp.status_code == 200:
            print_ok(f"Chat {chat_id} deleted successfully.")
        else:
            print_err(resp.json().get("detail", "Failed to delete chat."))
    except Exception as e:
        print_err(f"Error: {e}")


def list_characters(client: OpenBrainClient) -> None:
    if not client.is_logged_in:
        print_err("Not logged in.")
        return
    try:
        resp = client.request("GET", "/ai/characters")
        if resp.status_code == 200:
            characters = resp.json()
            print(f"\n{CLR_BOLD}=== Available AI Characters ==={CLR_RESET}")
            for char in characters:
                print(f"{CLR_YELLOW}{char['name']}{CLR_RESET} [id: {CLR_BOLD}{char['id']}{CLR_RESET}]")
                print(f"  Description: {char['description']}")
            print("==================================")
        else:
            print_err("Failed to retrieve characters.")
    except Exception as e:
        print_err(f"Error: {e}")


# =============================================================================
# REPL / Interactive Chat Loop
# =============================================================================

def interactive_chat_repl(
    client: OpenBrainClient, 
    chat_id: Optional[str] = None, 
    provider: str = "claude", 
    model: Optional[str] = None,
    character_id: Optional[str] = None
) -> None:
    """Enter a terminal-based streaming chat room."""
    print_info(f"\nEntering chat session...")
    print_info(f"Using Provider: {provider} | Model: {model or 'default'} | Character: {character_id or 'none'}")
    print_warning("Type '/exit' to return to the main menu.\n")
    
    current_chat_id = chat_id
    
    while True:
        try:
            prompt = input(f"\n{CLR_BOLD}{CLR_GREEN}You:{CLR_RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            break

        if not prompt:
            continue
            
        if prompt.lower() == "/exit":
            break

        payload = {
            "prompt": prompt,
            "provider": provider
        }
        if current_chat_id:
            payload["chat_id"] = current_chat_id
        if model:
            payload["model"] = model
        if character_id:
            payload["character_id"] = character_id

        sys.stdout.write(f"\n{CLR_BOLD}{CLR_BLUE}Open-Brain:{CLR_RESET} ")
        sys.stdout.flush()

        # Stream response chunks
        try:
            for event in client.stream_chat(payload):
                evt_type = event["event"]
                evt_data = event["data"]
                
                if evt_type == "chat_start":
                    current_chat_id = evt_data.get("chat_id")
                elif evt_type == "chunk":
                    sys.stdout.write(evt_data.get("text", ""))
                    sys.stdout.flush()
                elif evt_type == "error":
                    sys.stdout.write(f"\n{CLR_RED}Error: {evt_data}{CLR_RESET}\n")
                    sys.stdout.flush()
                elif evt_type == "done":
                    pass
        except Exception as e:
            print(f"\n{CLR_RED}Connection error: {e}{CLR_RESET}")
        print() # Newline at completion


# =============================================================================
# Interactive Mode Loop (Main Menu GUI)
# =============================================================================

def run_interactive_mode(client: OpenBrainClient) -> None:
    """Runs a clean interactive terminal menu loop."""
    print(f"{CLR_BOLD}{CLR_MAGENTA}==================================================")
    print("      🧠 Welcome to Open-Brain Terminal Client 🧠")
    print(f"=================================================={CLR_RESET}")
    
    while True:
        if not client.is_logged_in:
            print(f"\n{CLR_BOLD}--- Auth Menu ---{CLR_RESET}")
            print("1. Log In")
            print("2. Register New Account")
            print("3. Exit")
            
            choice = input(f"{CLR_BOLD}Select an option [1-3]:{CLR_RESET} ").strip()
            
            if choice == "1":
                email = input(f"{CLR_BOLD}Enter email:{CLR_RESET} ").strip()
                if email:
                    login_flow(client, email)
            elif choice == "2":
                email = input(f"{CLR_BOLD}Enter email:{CLR_RESET} ").strip()
                if email:
                    register_flow(client, email)
            elif choice == "3":
                print_info("Goodbye!")
                break
            else:
                print_err("Invalid selection.")
        else:
            print(f"\n{CLR_BOLD}--- Main Menu (Logged in as: {client.email}) ---{CLR_RESET}")
            print("1. Start a New Chat")
            print("2. List Past Conversations")
            print("3. View Conversation History")
            print("4. Delete a Conversation")
            print("5. View AI Characters")
            print("6. View Profile")
            print("7. Log Out")
            print("8. Exit")
            
            choice = input(f"{CLR_BOLD}Select an option [1-8]:{CLR_RESET} ").strip()
            
            if choice == "1":
                # Prompt optional chat ID to continue
                list_chats(client)
                chat_id_input = input(f"\n{CLR_BOLD}Enter Chat ID to continue (optional, press Enter for a new chat):{CLR_RESET} ").strip()
                chat_id = chat_id_input if chat_id_input else None

                # Prompt provider
                print_info("\nAvailable Providers: [1] claude (Default) | [2] openai | [3] ollama")
                p_choice = input(f"{CLR_BOLD}Choose Provider [1-3] or hit Enter for default:{CLR_RESET} ").strip()
                provider = "claude"
                if p_choice == "2":
                    provider = "openai"
                elif p_choice == "3":
                    provider = "ollama"
                
                # Fetch characters to offer selection
                character_id = None
                if not chat_id:
                    try:
                        resp = client.request("GET", "/ai/characters")
                        if resp.status_code == 200:
                            chars = resp.json()
                            if chars:
                                print_info("\nAvailable Personas:")
                                print("0. None (Default Assistant)")
                                for idx, c in enumerate(chars, 1):
                                    print(f"{idx}. {c['name']} - {c['description']}")
                                c_choice = input(f"{CLR_BOLD}Select Persona [0-{len(chars)}]:{CLR_RESET} ").strip()
                                if c_choice.isdigit() and 0 < int(c_choice) <= len(chars):
                                    character_id = chars[int(c_choice) - 1]["id"]
                    except Exception:
                        pass
                
                model = input(f"{CLR_BOLD}Enter custom model name (optional, press Enter to default):{CLR_RESET} ").strip()
                interactive_chat_repl(
                    client, 
                    chat_id=chat_id, 
                    provider=provider, 
                    model=model if model else None, 
                    character_id=character_id
                )
                
            elif choice == "2":
                list_chats(client)
            elif choice == "3":
                list_chats(client)
                chat_id = input(f"\n{CLR_BOLD}Enter Chat ID to read:{CLR_RESET} ").strip()
                if chat_id:
                    show_chat_history(client, chat_id)
                    continue_convo = input(f"\n{CLR_BOLD}Do you want to continue this conversation? [y/N]:{CLR_RESET} ").strip().lower()
                    if continue_convo == "y":
                        print_info("\nAvailable Providers: [1] claude (Default) | [2] openai | [3] ollama")
                        p_choice = input(f"{CLR_BOLD}Choose Provider [1-3] or hit Enter for default:{CLR_RESET} ").strip()
                        provider = "claude"
                        if p_choice == "2":
                            provider = "openai"
                        elif p_choice == "3":
                            provider = "ollama"
                        
                        model = input(f"{CLR_BOLD}Enter custom model name (optional, press Enter to default):{CLR_RESET} ").strip()
                        interactive_chat_repl(
                            client,
                            chat_id=chat_id,
                            provider=provider,
                            model=model if model else None
                        )
            elif choice == "4":
                list_chats(client)
                chat_id = input(f"\n{CLR_BOLD}Enter Chat ID to delete:{CLR_RESET} ").strip()
                if chat_id:
                    confirm = input(f"Are you sure you want to delete {chat_id}? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        delete_chat(client, chat_id)
            elif choice == "5":
                list_characters(client)
            elif choice == "6":
                view_profile(client)
            elif choice == "7":
                try:
                    client.request("POST", "/auth/logout")
                except Exception:
                    pass
                SessionManager.clear_session()
                client.session = None
                print_ok("Logged out successfully.")
            elif choice == "8":
                print_info("Goodbye!")
                break
            else:
                print_err("Invalid selection.")


# =============================================================================
# CLI Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="🧠 Open-Brain API Command Line Interface (CLI) client.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Backend Base URL")
    
    subparsers = parser.add_subparsers(dest="command", help="CLI commands")

    # Command: register
    subparsers.add_parser("register", help="Trigger registration flow").add_argument("--email", required=True)

    # Command: login
    subparsers.add_parser("login", help="Log in with MFA (Option A)").add_argument("--email", required=True)

    # Command: profile
    subparsers.add_parser("profile", help="View current logged in profile")

    # Command: list-chats
    subparsers.add_parser("chats", help="List all past conversations")

    # Command: show-chat
    subparsers.add_parser("history", help="Retrieve conversation history").add_argument("chat_id")

    # Command: delete-chat
    subparsers.add_parser("delete-chat", help="Delete a conversation").add_argument("chat_id")

    # Command: characters
    subparsers.add_parser("characters", help="List available AI personas")

    # Command: chat (one-off or enter loop)
    chat_parser = subparsers.add_parser("chat", help="Start a chat room or send a single prompt")
    chat_parser.add_argument("--provider", default="claude", choices=["claude", "openai", "ollama"], help="AI provider")
    chat_parser.add_argument("--model", help="Model override")
    chat_parser.add_argument("--character", help="Character ID")
    chat_parser.add_argument("--chat-id", help="Continue existing chat ID")
    chat_parser.add_argument("prompt", nargs="?", help="If specified, sends a single message and exits. If omitted, starts REPL loop.")

    args = parser.parse_args()

    client = OpenBrainClient(base_url=args.url)

    if not args.command:
        # Run interactive REPL shell
        run_interactive_mode(client)
        return

    # Direct Commands Execution
    if args.command == "register":
        register_flow(client, args.email)
    elif args.command == "login":
        login_flow(client, args.email)
    elif args.command == "profile":
        view_profile(client)
    elif args.command == "chats":
        list_chats(client)
    elif args.command == "history":
        show_chat_history(client, args.chat_id)
    elif args.command == "delete-chat":
        delete_chat(client, args.chat_id)
    elif args.command == "characters":
        list_characters(client)
    elif args.command == "chat":
        if args.prompt:
            # Single prompt streaming execution
            if not client.is_logged_in:
                print_err("You must log in first to use the chat.")
                sys.exit(1)
                
            payload = {
                "prompt": args.prompt,
                "provider": args.provider
            }
            if args.chat_id:
                payload["chat_id"] = args.chat_id
            if args.model:
                payload["model"] = args.model
            if args.character:
                payload["character_id"] = args.character
                
            try:
                for event in client.stream_chat(payload):
                    if event["event"] == "chunk":
                        sys.stdout.write(event["data"].get("text", ""))
                        sys.stdout.flush()
                    elif event["event"] == "chat_start":
                        print_info(f"[Chat Session Started. ID: {event['data']['chat_id']}]")
                    elif event["event"] == "error":
                        print_err(event["data"])
            except Exception as e:
                print_err(f"Stream error: {e}")
            print()
        else:
            if not client.is_logged_in:
                print_err("You must log in first to use the chat.")
                sys.exit(1)
            interactive_chat_repl(
                client, 
                chat_id=args.chat_id, 
                provider=args.provider, 
                model=args.model, 
                character_id=args.character
            )

if __name__ == "__main__":
    main()
