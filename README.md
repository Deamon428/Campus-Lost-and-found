# Campus Lost & Found 🔍

A lightweight, zero-friction campus registry built to replace chaotic batch WhatsApp group spam with a structured, searchable feed for lost smart cards, hostel keys, calculators, and audio gear.

**Live Application:** [campus-lost-and-found-hl4v.onrender.com](https://campus-lost-and-found-hl4v.onrender.com/)

---

## The Problem

When students lose a campus smart card, hostel room key, or calculator in lecture halls or the library, notices are typically dropped into 500-member batch WhatsApp groups where they get buried under messages within 15 minutes. 

Existing portal solutions require full email/password registration, which kills campus adoption for simple utility tasks. **Campus Lost & Found** eliminates all account creation friction while maintaining security and instant communication.

---

## Key Features

* **Zero-Friction Device Ownership:** No usernames, passwords, or emails. When an item is posted, the backend generates an ephemeral cryptographic `manage_token` stored in the poster's browser `localStorage`. Only the original device can mark an item as resolved or delete the listing.
* **Direct WhatsApp Deep-Linking:** Claimants tap a single button to open a pre-filled WhatsApp conversation with the founder/owner to verify item details and arrange hostel gate handoffs.
* **Campus-Specific Filtering:** Instant client-side and server-side filtering tailored to university transit and study hubs:
  * **Categories:** Smart Card / ID, Keys, Electronics / Audio, Stationery / Drafter, Cycle / Other.
  * **Locations:** Central Library, LT / LP Complex, Hostel Area, COS / Sports Complex, Other.
* **Image Upload Pipeline:** Secure multipart upload storing photo previews locally with unique UUID references.
* **Clean Light UI:** Built using a mobile-first Tailwind design with responsive status chips and reactive search.

---

## Tech Stack

* **Backend:** FastAPI (Python 3.11+)
* **Database:** SQLite3 with composite indexing on `(type, status, category, location)`
* **File Handling:** `python-multipart` with UUID-based image deduplication
* **Frontend:** Tailwind CSS, Vanilla JavaScript (Fetch API, DOM manipulation, `localStorage` state)
* **Server & Deployment:** Uvicorn, Render (Web Service)

---

## API Overview

| Method | Endpoint | Description | Auth / Headers |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/items` | Fetch filtered items feed (`type`, `category`, `location`, `status`, `search`) | Public |
| `POST` | `/api/items` | Submit a new Lost or Found report (supports multipart image upload) | Public |
| `PATCH` | `/api/items/{id}/resolve` | Mark an item listing as resolved/claimed | `X-Manage-Token` |
| `DELETE` | `/api/items/{id}` | Remove a listing and delete its uploaded media | `X-Manage-Token` |

---

## Local Development

### 1. Clone the repository
```bash
git clone [https://github.com/Deamon428/campus-lost-and-found.git](https://github.com/Deamon428/campus-lost-and-found.git)
cd campus-lost-and-found
```

### 2. Set up virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize database
```bash
python models.py
```

### 4. Run the development server
```bash
uvicorn main:app --reload --port 8002
```

Open [http://localhost:8002](http://localhost:8002) in your browser.

---

## Project Structure

```text
campus-lost-and-found/
├── main.py              # FastAPI application, CORS, static routes, and API endpoints
├── models.py            # SQLite schema initialization, table constraints, and DB dependencies
├── requirements.txt     # Python dependencies (fastapi, uvicorn, python-multipart)
├── static/
│   ├── index.html       # Stitch-designed frontend UI and client-side logic
│   └── uploads/         # Uploaded item media (ignored by Git)
├── .gitignore
└── README.md
```

---
