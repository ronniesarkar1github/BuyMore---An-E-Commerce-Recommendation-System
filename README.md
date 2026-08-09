# BuyMore---An-E-Commerce-Recommendation-System
BuyMore is an intelligent e-commerce platform combining secure shopping with AI and machine learning. It offers product search, Wishlist, Cart, reviews, recommendations, and an AI chatbot, while administrators manage products, orders, payments, and inventory through a dedicated dashboard.

Project Set Up : 

MongoDB Installation (Windows) [OR , Watch this : https://youtu.be/tC49Nzm6SyM?si=ROkrXJpFtBrBi05W ]

1. Download MongoDB Community Server  
   Go to the MongoDB Community Server download page and choose the Windows MSI installer.

2. Run the installer
   - Choose Complete setup
   - Keep defaults

3. Install MongoDB as a service (recommended)  
   This makes it start automatically.

4. Start MongoDB
   If installed as a service, it starts automatically.  
   Otherwise, open Services and start MongoDB Server.

5. Verify MongoDB
   MongoDB runs on:
   ```
   mongodb://127.0.0.1:27017/
   ```

---

Project Setup Steps (Windows)

1. Install Python (3.11 recommended)  
   From python.org, and ensure “Add Python to PATH” is checked.

2. Copy the full project folder  
   Include:
   - `app.py`
   - `requirements.txt`
   - ChatBot - Project
   - `templates/`, `static/`
   - `bert_sentiment_model/`

3. Open Terminal in project folder

4. Create virtual environment
   ```powershell
   python -m venv .venv
   ```

5. Activate venv
   ```powershell
   & ".\.venv\Scripts\Activate.ps1"
   ```

6. Install dependencies
   ```powershell
   python -m pip install -r requirements.txt
   ```

7. Run Flask app
   ```powershell
   python app.py
   ```

8. Open in browser
   ```
   http://127.0.0.1:5000
   ```

---

If venv activation is blocked
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

If they get long‑path errors installing
Enable long paths or create the venv in a shorter path like `D:\venv\shop`.


