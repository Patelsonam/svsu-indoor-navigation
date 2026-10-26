# SVSU E1 Block Indoor Navigation System

A web-based indoor navigation system designed to help students, faculty members, parents, and visitors navigate inside the E1 Block of Shri Vishwakarma Skill University (SVSU).

The project aims to provide indoor navigation without relying on GPS, which is often unreliable inside buildings.

## Features

- Indoor navigation for the SVSU E1 Block
- Interactive building maps and navigation interface
- Floor and room information management
- QR-code-based location access
- Django-powered backend and REST API
- Map editor for managing indoor map data
- Responsive web interface
- Browser-based access

## Technology Stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** SQLite (development)
- **Frontend:** HTML, CSS, JavaScript
- **QR Code:** HTML5 QR Code and QR Code JavaScript libraries
- **Fonts:** Inter

## Project Structure

```text
backend/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── navigation/
│   ├── management/
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Patelsonam/svsu-indoor-navigation.git
cd svsu-indoor-navigation
```

### 2. Create a virtual environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. Load initial SVSU navigation data (optional)

If you want to use the project's seed data, run:

```bash
python manage.py seed_svsu
```

### 6. Start the development server

```bash
python manage.py runserver
```

Open the local development URL:

http://127.0.0.1:8000/

## Configuration

Before deploying this project publicly, configure Django for production, including:

- A secure secret key stored in environment variables
- `DEBUG = False`
- Appropriate allowed hosts
- Production database configuration
- Static file handling
- HTTPS and security settings

Do not commit passwords, API keys, or other secrets to the repository.

## Current Status

The project source code is available on GitHub. Production deployment and database configuration may require additional setup.

## Future Improvements

- Deploy the application to a public hosting platform
- Improve route calculation and floor-to-floor navigation
- Add more building maps and points of interest
- Improve accessibility and voice-guided navigation
- Enhance mobile experience and testing

## Author

**Sonam Patel**

GitHub: [@Patelsonam](https://github.com/Patelsonam)

## License

No license has been specified yet. All rights remain with the copyright holder unless a license is added.
