
# Doctor Agent 🏥

An AI-powered healthcare appointment management system that uses natural language processing to handle doctor and patient registrations, appointment scheduling, and fetching doctors/patients informations through an intuitive chat interface.

## 🌟 Features

### 🤖 AI-Powered Natural Language Interface
- **Conversational AI**: Interact with the system using natural language commands
- **Intelligent Parsing**: LLM-based extraction of structured data from conversational input
- **Context Awareness**: Understands relationships between doctors, patients, and appointments
- **Flexible Commands**: Multiple ways to express the same intent

### 👨‍⚕️ Doctor Management
- **Registration**: Register new doctors with comprehensive details
- **Specializations**: Manage medical specializations and specialties
- **Availability**: Set and manage doctor schedules and availability
- **Profiles**: Store doctor credentials, experience, and consultation fees

### 👥 Patient Management
- **Registration**: Register new patients with demographic information
- **Profiles**: Store patient details, emergency contacts, and medical history
- **Demographics**: Get details of age, gender, address, and contact information

### 📅 Appointment Management
- **Booking**: Schedule appointments using natural language
- **Rescheduling**: Change appointment dates and times
- **Cancellation**: Cancel appointments with confirmation

### 🗄️ Database Features
- **PostgreSQL**: Robust relational database backend
- **SQLAlchemy ORM**: Modern database abstraction layer
- **Data Integrity**: Comprehensive validation and constraints
- **Performance**: Optimized indexes and queries

## 🏗️ Architecture

### Backend Stack
- **FastAPI**: Modern Python web framework for high-performance APIs
- **SQLAlchemy**: Database ORM and connection management
- **PostgreSQL**: Production-ready relational database
- **LLM Integration**: OpenAI-compatible API for natural language processing
- **MCP (Model Context Protocol)**: Tool integration for AI agents

### Frontend Stack
- **HTML5/CSS3**: Modern, responsive web interface
- **JavaScript**: Lightweight, fast client-side interactions
- **Real-time Chat**: Interactive conversation interface
- **Medical UI**: Professional healthcare-themed design

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/doctor_agent.git
   cd doctor_agent
   ```

2. **Set up Python environment**
   ```bash
   # Create virtual environment
   python -m venv myenv
   
   # Activate virtual environment
   # On Windows:
   myenv\Scripts\activate
   # On macOS/Linux:
   source myenv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configure database**
   ```bash
   # Edit backend/config.py with your database credentials
   # Or use the existing remote database configuration
   ```

5. **Initialize database**
   ```bash
   # Run the schema.sql file in your PostgreSQL database
   psql -h your_host -U your_user -d your_database -f backend/schema.sql
   ```

6. **Start the server**
   ```bash
   cd backend
   uvicorn doctor_server:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Access the application**
   - Open your browser and navigate to `http://localhost:8000`
   - Start chatting with the AI agent!

## 🤖 MCP (Model Context Protocol) Integration

This project implements **MCP (Model Context Protocol)** functionality to enable AI agents to interact with the healthcare management system through standardized tool interfaces.

### MCP Features
- **Tool Registration**: AI agents can discover available tools through the `/list_tools` endpoint
- **Tool Execution**: Agents can execute tools via the `/call_tool` endpoint
- **Structured Communication**: Standardized request/response formats for tool interactions
- **Async Support**: Full asynchronous support for high-performance tool execution

### Available MCP Tools
- **`ask_agent`**: Primary tool for natural language queries and commands
  - **Purpose**: Handle all user queries including registration, booking, and data retrieval
  - **Parameters**: `question` (string) - Natural language query
  - **Returns**: Structured response with success status, messages, and data

### MCP Integration Example
```python
# Example MCP tool call
import requests

# List available tools
tools_response = requests.get("http://localhost:8000/list_tools")
tools = tools_response.json()["tools"]

# Execute a tool
tool_request = {
    "name": "ask_agent",
    "arguments": {
        "question": "Register a new doctor named Dr. John Smith with email john.smith@hospital.com"
    }
}
response = requests.post("http://localhost:8000/call_tool", json=tool_request)
result = response.json()
```

## 💬 Usage Examples

### Doctor Registration
```
"Register a new doctor named Dr. Alex Johnson with email alex.johnson@test.com, specialization Cardiology"
"Add doctor Sarah Wilson, email sarah.wilson@hospital.com, phone 555-1234, specialization Dermatology"
```

### Patient Registration
```
"Register a new patient named John Smith with email john.smith@email.com, gender Male"
"Add patient Maria Garcia, email maria.garcia@email.com, date of birth 1985-08-20"
```

### Specialization Management
```
"Register a new specialization called Oncology with description Cancer treatment specialist"
"Add specialization Dermatology, description Skin and hair specialist"
```

### Availability Management
```
"Add availability for Dr. John Smith on Monday from 9:00 AM to 5:00 PM"
"Set availability for Sarah Johnson on Wednesday 10:00 AM to 6:00 PM, 45-minute slots"
```

### Appointment Management
```
"Book an appointment for John Smith with Dr. Alex Johnson on 2024-01-15 at 10:00 AM"
"Cancel appointment ID 123"
"Reschedule appointment ID 123 to 2024-01-16 at 2:00 PM"
```

### Data Queries
```
"Show all cardiologists"
"List appointments for Dr. Smith on Monday"
"Find patients with email containing 'john'"
"Get all available slots for Dr. Johnson on Tuesday"
```

## 🗄️ Database Schema

### Core Tables
1. **`specializations`** - Medical specializations and specialties
2. **`doctors`** - Doctor information and credentials
3. **`patients`** - Patient information and demographics
4. **`doctor_availability`** - Doctor schedules and availability
5. **`appointments`** - Appointment bookings and status

### Key Relationships
- Doctors → Specializations (many-to-one)
- Appointments → Doctors (many-to-one)
- Appointments → Patients (many-to-one)
- Doctor Availability → Doctors (many-to-one)

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the `backend` directory:

```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5555
POSTGRES_DB=doctor_agent
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password

# AI Model Configuration
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4
```

### Database Configuration
Edit `backend/config.py` to match your database setup:

```python
# Database URL format
DATABASE_URL = "postgresql+psycopg2://user:password@host:port/database"

# AI Model settings
OPENAI_API_KEY = "your_api_key"
OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_MODEL_NAME = "gpt-4"
```

## 📁 Project Structure

```
doctor_agent/
├── backend/
│   ├── config.py              # Configuration settings
│   ├── doctor_ai_agent.py     # AI agent and NLP logic
│   ├── doctor_db.py           # Database operations
│   ├── doctor_server.py       # FastAPI server with MCP
│   ├── requirements.txt       # Python dependencies
│   └── schema.sql            # Database schema
├── frontend/
│   ├── index.html            # Main web interface
│   ├── app.js               # Frontend JavaScript
│   └── style.css            # Styling
├── myenv/                   # Python virtual environment
├── FEATURES_SUMMARY.md      # Detailed feature documentation
├        
└── README.md               # This file
```

## 🙏 Acknowledgments

- **FastAPI** - Modern web framework for building APIs
- **SQLAlchemy** - Database toolkit and ORM
- **OpenAI** - AI model integration
- **PostgreSQL** - Robust relational database
- **MCP** - Model Context Protocol for AI agent integration

**Made with ❤️ for the healthcare community**
