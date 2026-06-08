# AisleWise
Smart Retail Assistant

## Quick Start

1. Create and activate your virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```
Or use Uvicorn directly:
```powershell
uvicorn app:app --port 5000 --reload
```

4. Open the app in your browser:

- http://127.0.0.1:5000/
- Admin: http://127.0.0.1:5000/admin
- Worker: http://127.0.0.1:5000/worker/login
- Customer Chat: http://127.0.0.1:5000/customer/chat

## Gemini LLM Setup

To enable the AI assistant, set your Gemini API key in the environment:

```powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Then restart the application.

## Default Admin Credentials

- Store ID: `admin`
- Password: `password123`

## Sample Worker Accounts

- `john.doe@gmail.com` (Active)
- `jane.smith@gmail.com` (Active)
- `bob.brown@gmail.com` (Inactive)
