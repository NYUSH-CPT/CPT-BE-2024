# CPT Mental Health Platform

> A full-stack web application supporting a longitudinal mental health intervention research study for the LGBTQ+ community, featuring automated task scheduling, role-based access control, interactive cognitive behavioral therapy (CBT) game, and secure multi-channel participant communication.

[![Next.js](https://img.shields.io/badge/Next.js-14.2-black)](https://nextjs.org/)
[![Django](https://img.shields.io/badge/Django-4.1.6-green)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org/)

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Design Highlights](#-design-highlights)
- [Project Structure](#-project-structure)
- [Author](#-author)

---

## 🎯 Project Overview

The **CPT (Cognitive Processing Therapy) Mental Health Platform** is a production-grade research application designed to support a multi-day longitudinal intervention study. The platform manages participant enrollment, daily task assignments, progress tracking, automated quality control, and secure communication across multiple channels (web, SMS, in-app messaging).

The system consists of two tightly integrated repositories:

- **Backend (CPT-BE-2024)**: Django REST API with automated scheduling, encryption, and multi-role administration
- **Frontend (CPT-FE-2024)**: Next.js application with dynamic task progression, interactive CBT game, and responsive UI

### Research Context

This platform supports a real-world mental health research study targeting the LGBTQ+ community. Participants progress through structured daily tasks over multiple weeks, including:

- Daily writing exercises with quality control
- Interactive CBT-based counseling simulation game
- Periodic survey assessments (Qualtrics integration)
- Automated feedback delivery and progress monitoring

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Task         │  │ Interactive  │  │ Survey       │      │
│  │ Stepper      │  │ CBT Game     │  │ Integration  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                    │            │
│         └─────────────────┼────────────────────┘            │
│                           │                                  │
│              Context API (Global State)                      │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │ REST API (JWT Auth)
┌───────────────────────────┼──────────────────────────────────┐
│                   Backend (Django REST)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Task         │  │ Game State   │  │ Automated    │      │
│  │ Management   │  │ Persistence  │  │ Scheduling   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                    │            │
│  ┌──────┴──────┐  ┌──────┴──────┐   ┌────────┴────────┐    │
│  │   Models    │  │  Services   │   │   Cron Jobs     │    │
│  │   & ORM     │  │  (SMS/Blued)│   │   (django-cron) │    │
│  └──────┬──────┘  └──────┬──────┘   └────────┬────────┘    │
│         │                 │                    │            │
└─────────┼─────────────────┼────────────────────┼────────────┘
          │                 │                    │
    ┌─────┴─────┐    ┌──────┴──────┐     ┌──────┴──────┐
    │  MySQL    │    │  Alibaba    │     │   Blued     │
    │ Database  │    │  Cloud SMS  │     │  Messaging  │
    └───────────┘    └─────────────┘     └─────────────┘
```

### Data Flow

1. **Authentication**: SMS-based OTP authentication with encrypted phone numbers
2. **Task Progression**: Server-side state management with time-window validation
3. **Quality Control**: Multi-stage review workflow (RA + CS) with automated validation rules
4. **Automated Communication**: Cron-based scheduled messages via Blued API and SMS
5. **Game State**: Pickle-serialized game objects stored in binary fields with state persistence

---

## ✨ Key Features

### 🎮 Interactive CBT Game Engine

- **State Machine Architecture**: Complex node-based game flow with recursive state management
- **Persistent Game State**: Binary serialization (pickle) for mid-game break/resume functionality
- **Dynamic Scenario Generation**: Excel-based content parsing with randomized presentation order
- **Real-time Scoring**: Immediate feedback with point accumulation (+1000/-300) and performance tracking
- **Multi-patient Scenarios**: 16+ interactive counseling scenarios with cognitive restructuring exercises

### 📅 Automated Task Scheduling

- **Cron-based Automation**: Daily scheduled task execution (8:00 AM and 8:00 PM)
- **Multi-criteria Task Matching**: Group-based, day-based, and condition-based task filtering
- **Dynamic Notification System**: Automated participant messaging via Blued API and SMS
- **Time-window Enforcement**: Server-side validation of task availability windows
- **Survey Reminder System**: Automated reminders for overdue assessments with 6-day windows

### 🔐 Security & Privacy

- **AES Encryption**: Client-side PII encryption (phone numbers, WeChat IDs) before database storage
- **JWT Authentication**: Token-based authentication with refresh token support
- **Role-based Access Control**: Multi-level permission system (Superuser, INFO, RA, CS, LS) with customized Django admin views
- **Secure Data Export**: Encrypted field decryption only for authorized admin users
- **Environment-based Secrets**: All sensitive credentials stored in environment variables

### 📊 Quality Control System

- **Multi-stage Review Process**: Research Assistant (RA) + Clinical Supervisor (CS) dual-review workflow
- **Automated Quality Checks**: Rule-based validation with automatic ban flag management
- **Writing Quality Assessment**: Real-time quality flag updates based on reviewer consensus
- **Ban Reason Tracking**: JSON-based structured logging of ban reasons with timestamps
- **Progress Validation**: Automated checks for survey validity, task completion, and game performance

### 🔄 Progress Management

- **Flexible Day Tracking**: Float-based currentDay system supporting fractional progress (e.g., 2.1 for video completion, 23 for survey milestones)
- **Dynamic Task Availability**: Time-window calculations based on participant start date
- **Ban State Management**: Automatic progression to survey-only mode upon quality violations
- **Survey Integration**: Qualtrics webhook integration for automated survey validation
- **Feedback Delivery**: Markdown-based feedback system with view-tracking

### 📱 Multi-channel Communication

- **Blued API Integration**: In-app messaging for Chinese LGBTQ+ social platform users
- **Alibaba Cloud SMS**: Programmatic SMS notifications via Alibaba Cloud SMS API
- **WeChat Support**: Encrypted WeChat ID storage for alternative communication
- **Template-based Messaging**: JSON-configured message templates with dynamic parameter injection

---

## 💻 Tech Stack

### Backend

| Category                  | Technology                                 |
| ------------------------- | ------------------------------------------ |
| **Framework**       | Django 4.1.6, Django REST Framework 3.14.0 |
| **Database**        | MySQL (mysqlclient 2.2.4)                  |
| **Authentication**  | JWT (djangorestframework-simplejwt 5.2.2)  |
| **Task Scheduling** | django-crontab 0.7.1                       |
| **Encryption**      | PyCryptodome 3.20.0 (AES-ECB)              |
| **API Client**      | aiohttp 3.8.3, requests 2.28.2             |
| **SMS Service**     | Alibaba Cloud SMS SDK                      |
| **Serialization**   | pickle (for game state), JSON              |
| **Web Server**      | Uvicorn (ASGI)                             |

### Frontend

| Category                   | Technology                         |
| -------------------------- | ---------------------------------- |
| **Framework**        | Next.js 14.2.4 (React 18)          |
| **UI Library**       | Material-UI (MUI) 5.15.17          |
| **State Management** | React Context API                  |
| **Styling**          | SCSS Modules, Tailwind CSS 3.4.1   |
| **HTTP Client**      | Axios 1.7.0                        |
| **Form Management**  | React Hook Form 7.56.2, Yup 1.6.1  |
| **Media**            | react-player 2.16.0                |
| **Utilities**        | moment.js 2.30.1, jose 5.3.0 (JWT) |

### DevOps & Infrastructure

| Category                   | Technology                                   |
| -------------------------- | -------------------------------------------- |
| **Containerization** | Docker (multi-stage builds)                  |
| **Environment**      | python-dotenv 1.0.1                          |
| **Static Files**     | WhiteNoise (Django)                          |
| **CORS**             | django-cors-headers 3.13.0                   |
| **Logging**          | Django logging with TimedRotatingFileHandler |

---

## 🎨 Design Highlights

### 1. **Modular Service Architecture**

Backend services are organized into dedicated modules (`core/services/`) for:

- **SMS Service**: Alibaba Cloud SMS integration with template support
- **Blued Messaging**: In-app message delivery API wrapper
- **Game Engine**: State machine implementation with node-based flow control
- **Content Parser**: Excel-to-game-scenario converter with dynamic generation

### 2. **Context-based State Management**

Frontend uses React Context API for global user state:

- Centralized `InfoContext` provider managing user progress, permissions, and task data
- Automatic token refresh and API request interception
- Optimistic UI updates with server sync

### 3. **Dynamic Serializer Configuration**

Django REST Framework serializers use context-based field filtering:

```python
# Example: Different field sets for info endpoint vs admin panel
serializer = WebUserSerializer(webUser, context={"info": True})
```

### 4. **Comprehensive Error Handling**

- Decorator-based exception catching (`@catch_exceptions`)
- Centralized error logging with traceback capture
- User-friendly error messages in Chinese
- Automatic error page redirection (400, 401, 403, 419)

### 5. **Automated Validity Checking**

Rule-based participant validation system:

- **Pre-survey validation**: Survey 1 validity check
- **Post-survey validation**: At least one valid survey among 23, 39, 99
- **Writing quality checks**: Automatic aggregation of RA/CS reviews
- **Task completion tracking**: Overdue detection with 2-day + 4-hour windows
- **Game performance**: Minimum score threshold (61,200 = 60% of 102,000)

### 6. **Advanced Django Admin Customization**

- Role-based fieldset visibility (Superuser, INFO, RA, CS, LS)
- Dynamic readonly fields based on user group
- åCustom admin actions (reset game, export CSV, generate password reset links)
- Encrypted field display with on-the-fly decryption
- Bulk operations with permission checks

---

## 📁 Project Structure

### Backend Structure

```
CPT-BE-2024/
├── core/                    # Main Django app
│   ├── models.py           # Database models (WebUser, Whitelist, etc.)
│   ├── views.py            # API endpoints
│   ├── serializers.py      # DRF serializers
│   ├── tasks.py            # Scheduled task logic
│   ├── admin.py            # Django admin customization
│   ├── utility.py          # Encryption/decryption utilities
│   ├── services/           # External service integrations
│   │   ├── SMS.py         # Alibaba Cloud SMS service
│   │   ├── blued_msg.py   # Blued messaging API
│   │   ├── gameInit.py    # Game initialization
│   │   ├── gameModel.py   # Game state machine
│   │   └── parser.py      # Excel content parser
│   ├── csv_export/         # CSV export field definitions
│   └── migrations/         # Database migrations
├── CPTBackend/             # Django project settings
│   ├── settings.py        # Django configuration
│   └── urls.py            # Root URL configuration
├── staticfiles/            # Collected static files
├── Dockerfile              # Production Docker image
├── requirements.txt        # Python dependencies
└── crontab                 # Cron job definitions
```

### Frontend Structure

```
CPT-FE-2024/
├── pages/                  # Next.js pages (file-based routing)
│   ├── _app.js            # App wrapper with providers
│   ├── index.js           # Homepage with task stepper
│   ├── login/             # Authentication pages
│   ├── game/              # Interactive CBT game
│   ├── challenge_writing/ # Writing exercise pages
│   └── error/             # Error pages (400, 401, 403, 419)
├── components/            # Reusable React components
│   ├── Tasks.js          # Task progression stepper
│   ├── ChatBox.js        # Game chat interface
│   └── Header.js         # Navigation header
├── context/               # React Context providers
│   └── InfoContext.js    # Global user state
├── styles/                # SCSS modules
├── public/                # Static assets
├── utils.js               # Utility functions (API client, JWT)
├── Dockerfile             # Production Docker image
└── package.json           # Node dependencies
```

---

## 👨‍💻 Author

**Developed by Yongyu Liu, MCS @ UIUC**
