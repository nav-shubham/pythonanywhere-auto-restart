import os
import re
import sys
import logging
import http.cookiejar
import requests

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("cookies", exist_ok=True)

# Set up logging to both console and a file
log_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(os.path.join("logs", "automation.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PythonAnywhereAutomation")

def load_env(filepath=".env"):
    """Parse a simple .env file manually without external dependencies."""
    config = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().strip('"').strip("'")
                    config[key] = val
    return config

def get_session_csrf_token(session):
    """Retrieve the CSRF token from the session cookies."""
    for cookie in session.cookies:
        if cookie.name == "csrftoken":
            return cookie.value
    return None

def is_logged_in(session, username):
    """Check if the session is authenticated for the given username."""
    url = f"https://www.pythonanywhere.com/user/{username}/webapps/"
    try:
        resp = session.get(url, allow_redirects=False)
        # A successful logged-in response should be 200 OK
        if resp.status_code == 200 and f"user/{username}/" in resp.text.lower():
            return True
    except Exception as e:
        logger.error(f"Error checking login status for {username}: {e}")
    return False

def login(session, username, password):
    """Attempt to log in to PythonAnywhere using credentials."""
    login_url = "https://www.pythonanywhere.com/login/"
    try:
        logger.info(f"Attempting to log in as '{username}' using password...")
        
        # 1. GET login page to populate initial cookies and obtain CSRF token
        resp = session.get(login_url)
        csrf_token = get_session_csrf_token(session)
        if not csrf_token:
            # Fallback to search in HTML if not in cookies
            match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', resp.text)
            if match:
                csrf_token = match.group(1)
        
        if not csrf_token:
            logger.error(f"Could not find CSRF token on login page for '{username}'")
            return False
            
        # 2. POST login form data
        data = {
            "csrfmiddlewaretoken": csrf_token,
            "login_view-current_step": "auth",
            "auth-username": username,
            "auth-password": password
        }
        headers = {
            "Referer": login_url,
            "X-CSRFToken": csrf_token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        post_resp = session.post(login_url, data=data, headers=headers)
        
        # 3. Verify login status
        if is_logged_in(session, username):
            logger.info(f"Successfully logged in as '{username}'!")
            return True
        else:
            logger.error(f"Login failed for '{username}'. Response code: {post_resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"Exception occurred during login for '{username}': {e}")
        return False

def get_expiry_date(session, username):
    """Extract the 'disabled on' expiry date from the webapps configuration page."""
    url = f"https://www.pythonanywhere.com/user/{username}/webapps/"
    try:
        resp = session.get(url)
        match = re.search(r'This site will be disabled on\s*<strong>([^<]+)</strong>', resp.text)
        if match:
            return match.group(1).strip()
        match_alt = re.search(r'disabled on[^<]*<strong>([^<]+)</strong>', resp.text)
        if match_alt:
            return match_alt.group(1).strip()
    except Exception as e:
        logger.error(f"Error fetching expiry date for '{username}': {e}")
    return "Unknown"

def extend_webapp(session, username, domain):
    """Send a POST request to extend the web app (click the 'Run for 1 month' button)."""
    url = f"https://www.pythonanywhere.com/user/{username}/webapps/{domain}/extend"
    csrf_token = get_session_csrf_token(session)
    if not csrf_token:
        logger.error(f"No CSRF token found in session cookies for extending '{domain}'")
        return False
        
    headers = {
        "Referer": f"https://www.pythonanywhere.com/user/{username}/webapps/",
        "X-CSRFToken": csrf_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {
        "csrfmiddlewaretoken": csrf_token
    }
    try:
        logger.info(f"Sending extension request for '{domain}'...")
        resp = session.post(url, headers=headers, data=data)
        if resp.status_code == 200:
            logger.info(f"Successfully sent extend request for '{domain}'.")
            return True
        else:
            logger.error(f"Failed to extend '{domain}'. HTTP status: {resp.status_code}")
    except Exception as e:
        logger.error(f"Exception during web app extension for '{domain}': {e}")
    return False

def reload_webapp(session, username, domain):
    """Send a POST request to reload the web app (restart the server)."""
    url = f"https://www.pythonanywhere.com/user/{username}/webapps/{domain}/reload"
    csrf_token = get_session_csrf_token(session)
    if not csrf_token:
        logger.error(f"No CSRF token found in session cookies for reloading '{domain}'")
        return False
        
    headers = {
        "Referer": f"https://www.pythonanywhere.com/user/{username}/webapps/",
        "X-CSRFToken": csrf_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {
        "csrfmiddlewaretoken": csrf_token
    }
    try:
        logger.info(f"Sending reload request for '{domain}'...")
        resp = session.post(url, headers=headers, data=data)
        if resp.status_code == 200 and resp.text.strip() == "OK":
            logger.info(f"Successfully reloaded web app '{domain}'!")
            return True
        else:
            logger.error(f"Failed to reload '{domain}'. HTTP status: {resp.status_code}, Response: {resp.text}")
    except Exception as e:
        logger.error(f"Exception during reload for '{domain}': {e}")
    return False

def send_telegram_notification(bot_token, chat_id, message):
    """Send a consolidated notification message to Telegram."""
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        logger.info("Sending Telegram notification...")
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram notification sent successfully.")
        else:
            logger.error(f"Failed to send Telegram notification. Status: {resp.status_code}, Response: {resp.text}")
    except Exception as e:
        logger.error(f"Exception occurred while sending Telegram notification: {e}")

def main():
    logger.info("=" * 60)
    logger.info("Starting PythonAnywhere Automation Task...")
    logger.info("=" * 60)
    
    # Load configuration
    env_config = load_env()
    
    # Configure the two accounts
    accounts = [
        {
            "username": "navshubham",
            "domain": "navshubham.pythonanywhere.com",
            "cookie_file": os.path.join("cookies", "www.navshubham.pythonanywhere.com_cookies.txt"),
            "password_key": "PASSWORD_NAVSHUBHAM"
        },
        {
            "username": "navsshubham",
            "domain": "navsshubham.pythonanywhere.com",
            "cookie_file": os.path.join("cookies", "www.navsshubham.pythonanywhere.com_cookies.txt"),
            "password_key": "PASSWORD_NAVSSHUBHAM"
        }
    ]
    
    results = []
    
    for account in accounts:
        username = account["username"]
        domain = account["domain"]
        cookie_file = account["cookie_file"]
        password_key = account["password_key"]
        
        logger.info("-" * 40)
        logger.info(f"Processing account: '{username}' ({domain})")
        logger.info("-" * 40)
        
        session = requests.Session()
        cj = http.cookiejar.MozillaCookieJar(cookie_file)
        
        # 1. Try loading cookies from file
        cookies_loaded = False
        if os.path.exists(cookie_file):
            try:
                cj.load(ignore_discard=True, ignore_expires=True)
                session.cookies = cj
                logger.info(f"Loaded existing cookies from '{cookie_file}'.")
                cookies_loaded = True
            except Exception as e:
                logger.warning(f"Could not load cookies from '{cookie_file}': {e}")
        else:
            logger.info(f"No existing cookies file found at '{cookie_file}'.")
            
        # 2. Check if cookies are valid
        logged_in = False
        if cookies_loaded:
            logger.info("Verifying session validity...")
            logged_in = is_logged_in(session, username)
            if logged_in:
                logger.info("Session cookies are valid and logged in successfully.")
            else:
                logger.info("Session cookies are expired or invalid.")
                
        # 3. Fallback to username/password login if needed
        if not logged_in:
            password = env_config.get(password_key) or os.getenv(password_key)
            if not password:
                err_msg = f"Password not found in .env or system environment under key '{password_key}'."
                logger.error(f"Cannot log in for '{username}': {err_msg} Skipping account.")
                results.append(f"<b>Account:</b> <code>{username}</code>\n<b>Domain:</b> {domain}\n<b>Status:</b> ❌ Failed (Credentials missing)")
                continue
                
            # Perform login
            logged_in = login(session, username, password)
            if logged_in:
                # Save the new cookies to disk
                try:
                    for cookie in session.cookies:
                        cj.set_cookie(cookie)
                    cj.save(cookie_file, ignore_discard=True, ignore_expires=True)
                    logger.info(f"Saved new authenticated cookies to '{cookie_file}'.")
                except Exception as e:
                    logger.error(f"Failed to save cookies to '{cookie_file}': {e}")
            else:
                logger.error(f"Failed to log in for '{username}'. Skipping account.")
                results.append(f"<b>Account:</b> <code>{username}</code>\n<b>Domain:</b> {domain}\n<b>Status:</b> ❌ Failed (Login failed)")
                continue
                
        # 4. Perform actions (Extend & Reload)
        # Fetch current expiry date
        initial_expiry = get_expiry_date(session, username)
        logger.info(f"Current web app expiry date: {initial_expiry}")
        
        # Extend web app
        extend_success = extend_webapp(session, username, domain)
        
        # Reload web app
        reload_success = reload_webapp(session, username, domain)
        
        # Fetch and verify new expiry date
        new_expiry = get_expiry_date(session, username)
        logger.info(f"New web app expiry date: {new_expiry}")
        
        # Save cookies again in case tokens changed or were updated during POST requests
        try:
            for cookie in session.cookies:
                cj.set_cookie(cookie)
            cj.save(cookie_file, ignore_discard=True, ignore_expires=True)
        except Exception as e:
            logger.error(f"Failed to update cookies file: {e}")
            
        if extend_success and reload_success:
            logger.info(f"Successfully processed all automation actions for '{username}'!")
            results.append(f"<b>Account:</b> <code>{username}</code>\n<b>Domain:</b> {domain}\n<b>Status:</b> ✅ Success\n<b>Expiry:</b> {new_expiry}")
        else:
            logger.warning(f"Finished processing '{username}' with warnings/errors (Extend success: {extend_success}, Reload success: {reload_success})")
            results.append(f"<b>Account:</b> <code>{username}</code>\n<b>Domain:</b> {domain}\n<b>Status:</b> ⚠️ Partial (Extend: {extend_success}, Reload: {reload_success})\n<b>Expiry:</b> {new_expiry}")
            
    logger.info("=" * 60)
    logger.info("PythonAnywhere Automation Task Completed.")
    logger.info("=" * 60)
    
    # 5. Send Telegram notification if configured
    if results:
        status_text = "\n\n".join(results)
        message = f"<b>🤖 PythonAnywhere Auto-Renewal Report</b>\n\n{status_text}"
        bot_token = env_config.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = env_config.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            send_telegram_notification(bot_token, chat_id, message)
        else:
            logger.info("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")

if __name__ == "__main__":
    main()
