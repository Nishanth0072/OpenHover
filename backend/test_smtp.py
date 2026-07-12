import smtplib

def load_env(filepath):
    env_vars = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip()
    return env_vars

def test_smtp():
    env = load_env('.env')
    host = env.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(env.get('SMTP_PORT', '587'))
    username = env.get('SMTP_USERNAME', '')
    password = env.get('SMTP_PASSWORD', '')

    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Username: {username}")
    print(f"Password length: {len(password)}")

    # Test 1: Port 465 with SMTP_SSL
    print("\n--- Test 1: SMTP_SSL (port 465) ---")
    try:
        server = smtplib.SMTP_SSL(host, 465)
        server.login(username, password)
        print("SUCCESS with SMTP_SSL on port 465!")
        server.quit()
    except Exception as e:
        print(f"FAILED: {e}")

    # Test 2: Port 587 with STARTTLS
    print("\n--- Test 2: STARTTLS (port 587) ---")
    try:
        server = smtplib.SMTP(host, 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(username, password)
        print("SUCCESS with STARTTLS on port 587!")
        server.quit()
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_smtp()
