# CloudCampusIQ — Cloud-Based Online Learning Platform

[![Azure](https://img.shields.io/badge/Microsoft_Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)

## Live Application
🌐 [https://cloudcampusiq-anafeuh5dvbjd7fp.centralus-01.azurewebsites.net](https://cloudcampusiq-anafeuh5dvbjd7fp.centralus-01.azurewebsites.net)

---

## Project Overview

CloudCampusIQ is a fully deployed cloud-based online learning platform built on Microsoft Azure. The platform is designed to support up to 10,000 concurrent users and delivers course content securely through a professional web application. This project demonstrates real-world cloud engineering, DevOps practices, and web application development skills.

---

## Architecture
```
Students (Internet)
        ↓
   GitHub Actions (CI/CD)
        ↓
  Azure App Service (PaaS)
  ├── Flask Web Application
  ├── Azure Blob Storage (Course Materials)
  ├── Azure Active Directory (IAM)
  ├── Azure Monitor (Performance Alerts)
  └── Azure Cost Management (Spending Dashboard)
```

---

## Technologies Used

| Category | Technology |
|---|---|
| Cloud Provider | Microsoft Azure |
| Hosting | Azure App Service (PaaS) |
| Backend | Python 3.12 + Flask |
| Frontend | HTML5, CSS3, JavaScript |
| Storage | Azure Blob Storage |
| Security | Azure Active Directory + RBAC |
| Monitoring | Azure Monitor |
| Cost Management | Azure Cost Management |
| CI/CD | GitHub Actions |
| Version Control | Git + GitHub |

---

## Features

- Professional multi-page web application
- Course catalog with LinkedIn Learning integration
- Student login page
- Responsive design for all devices
- HTTPS enforced with TLS 1.2
- Automatic deployment via GitHub Actions CI/CD pipeline

---

## Security Implementation

- Azure Active Directory with Role-Based Access Control (RBAC)
- HTTPS Only enforced on Azure App Service
- TLS 1.2 minimum inbound version
- Private blob access — no anonymous access permitted
- Storage Blob Data Reader role assigned to authenticated users

---

## DevOps Pipeline

Every push to the `main` branch automatically:

1. Checks out the latest code
2. Sets up Python 3.12 environment
3. Installs all dependencies
4. Packages the application
5. Deploys to Azure App Service
```yaml
on:
  push:
    branches:
      - main
```

---

## Project Structure
```
cloudcampusiq/
├── app.py                        # Flask application routes
├── requirements.txt              # Python dependencies
├── .github/
│   └── workflows/
│       └── deploy.yml            # GitHub Actions CI/CD pipeline
├── static/
│   ├── css/
│   │   └── style.css             # Stylesheet
│   └── js/
│       └── main.js               # JavaScript
└── templates/
    ├── base.html                 # Base template
    ├── index.html                # Homepage
    ├── courses.html              # Course catalog
    └── login.html                # Student login
```

---

## Local Development

**Clone the repository:**
```bash
git clone https://github.com/Sittichai-nu/cloudcampusiq.git
cd cloudcampusiq
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run locally:**
```bash
python app.py
```

**Open browser:**
```
http://localhost:5000
```

---

## Monitoring and Cost Management

- **Azure Monitor** — HTTP server error alerts (Http5xx > 5 in 5 minutes)
- **Azure Cost Management** — Real-time spending dashboard
- **Current cost** — Less than $0.01/month (Azure for Students)

---

## Author

**Nu Chai**
WGU — D782 Network Architecture and Cloud Computing
April 2026

---

## License

This project is for educational purposes as part of WGU coursework.
