import requests
from config import OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL_NAME, DATABASE_URL
from doctor_db import (
    get_doctors, get_doctor_by_id, get_patients, get_patient_by_id, get_specializations,
    get_doctor_availability, get_appointments, add_appointment, update_appointment, cancel_appointment, delete_appointment, get_appointment_by_id,
    add_doctor, add_patient, get_specialization_by_name, add_specialization, get_specialization_by_id,
    add_doctor_availability, get_doctor_availability_by_id, update_doctor, update_patient, update_specialization,
    update_doctor_availability, delete_doctor, delete_patient, delete_specialization, delete_doctor_availability,
    search_doctors, search_patients, get_doctor_schedule
)
from sqlalchemy import create_engine, text
import time
import re

engine = create_engine(DATABASE_URL)

def get_sql_from_llm(question):
    system_prompt = (
        "You are a helpful assistant for a doctor appointment management database. "
        "Given a user's question, generate a valid SQL query for a PostgreSQL database. "
        "Available tables:\n"
        "1. 'doctors' (id, first_name, last_name, email, phone, specialization_id, license_number, experience_years, consultation_fee, is_active, created_at, updated_at)\n"
        "2. 'patients' (id, first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone, is_active, created_at, updated_at)\n"
        "3. 'appointments' (id, patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes, created_at, updated_at)\n"
        "4. 'specializations' (id, name, description, created_at)\n"
        "5. 'doctor_availability' (id, doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot, is_active, created_at, updated_at)\n"
        "Only return the SQL query, nothing else."
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{system_prompt}\n\n{question}"}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    sql = result["choices"][0]["message"]["content"].strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()

def query_database(query):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = [dict(row._mapping) for row in result]
        return rows
    except Exception as e:
        return {"error": str(e)}

def parse_operation(question):
    q = question.lower().strip()
    # Check for registration operations first
    register_doctor_keywords = ["register doctor", "add doctor", "create doctor", "new doctor", "sign up doctor", "register new doctor", "add new doctor"]
    register_patient_keywords = ["register patient", "add patient", "create patient", "new patient", "sign up patient", "register new patient", "add new patient"]
    register_specialization_keywords = ["register specialization", "add specialization", "create specialization", "new specialization", "add new specialization"]
    register_availability_keywords = ["add availability", "set availability", "create availability", "add doctor availability", "set doctor availability", "add schedule", "set schedule"]
    
    # Check for update operations
    update_doctor_keywords = ["update doctor", "modify doctor", "change doctor", "edit doctor", "update doctor details", "modify doctor details"]
    update_patient_keywords = ["update patient", "modify patient", "change patient", "edit patient", "update patient details", "modify patient details"]
    update_specialization_keywords = [
        "update specialization", "modify specialization", "change specialization", "edit specialization",
        "update specialization details", "change the specialization", "change specialization description",
        "update details of specialization", "change specialization descriptions"
    ]
    update_availability_keywords = ["update availability", "modify availability", "change availability", "edit availability", "update schedule", "modify schedule"]
    
    # Check for delete operations
    delete_doctor_keywords = ["delete doctor", "remove doctor", "deactivate doctor", "fire doctor"]
    delete_patient_keywords = ["delete patient", "remove patient", "deactivate patient", "discharge patient"]
    delete_specialization_keywords = ["delete specialization", "remove specialization", "deactivate specialization"]
    delete_availability_keywords = ["delete availability", "remove availability", "deactivate availability", "remove schedule"]
    
    # Check for appointment operations
    reschedule_keywords = ["reschedule", "change time", "move appointment", "shift", "postpone", "change date", "change appointment", "update time", "update appointment"]
    cancel_keywords = ["cancel", "delete", "remove appointment", "drop appointment"]
    book_keywords = ["book", "schedule", "make appointment", "create appointment", "add appointment"]
    
    # Check for help and general queries
    help_keywords = ["help", "what can you do", "how to", "guide", "tutorial", "instructions", "support", "assistance"]
    search_keywords = ["find", "search", "look for", "show", "list", "get", "display", "what is", "who is", "when is"]
    
    if any(k in q for k in register_doctor_keywords):
        print("[DEBUG] Detected operation: register_doctor")
        return "register_doctor"
    if any(k in q for k in register_patient_keywords):
        print("[DEBUG] Detected operation: register_patient")
        return "register_patient"
    if any(k in q for k in register_specialization_keywords):
        print("[DEBUG] Detected operation: register_specialization")
        return "register_specialization"
    if any(k in q for k in register_availability_keywords):
        print("[DEBUG] Detected operation: register_availability")
        return "register_availability"
    if any(k in q for k in update_doctor_keywords):
        print("[DEBUG] Detected operation: update_doctor")
        return "update_doctor"
    if any(k in q for k in update_patient_keywords):
        print("[DEBUG] Detected operation: update_patient")
        return "update_patient"
    if any(k in q for k in update_specialization_keywords):
        print("[DEBUG] Detected operation: update_specialization")
        return "update_specialization"
    if any(k in q for k in update_availability_keywords):
        print("[DEBUG] Detected operation: update_availability")
        return "update_availability"
    if any(k in q for k in delete_doctor_keywords):
        print("[DEBUG] Detected operation: delete_doctor")
        return "delete_doctor"
    if any(k in q for k in delete_patient_keywords):
        print("[DEBUG] Detected operation: delete_patient")
        return "delete_patient"
    if any(k in q for k in delete_specialization_keywords):
        print("[DEBUG] Detected operation: delete_specialization")
        return "delete_specialization"
    if any(k in q for k in delete_availability_keywords):
        print("[DEBUG] Detected operation: delete_availability")
        return "delete_availability"
    if any(k in q for k in reschedule_keywords):
        print("[DEBUG] Detected operation: reschedule")
        return "reschedule"
    if any(k in q for k in cancel_keywords):
        print("[DEBUG] Detected operation: cancel")
        return "cancel"
    if any(k in q for k in book_keywords):
        print("[DEBUG] Detected operation: book")
        return "book"
    if any(k in q for k in help_keywords):
        print("[DEBUG] Detected operation: help")
        return "help"
    if any(k in q for k in search_keywords):
        print("[DEBUG] Detected operation: search")
        return "search"
    print("[DEBUG] Detected operation: None")
    return None

def extract_appointment_id(details, question):
    # Accept both 'appointment_id' and 'id' as possible keys
    appt_id = details.get("appointment_id") or details.get("id")
    if appt_id is not None:
        try:
            return int(appt_id)
        except Exception:
            pass
    # Fallback: regex extraction from question
    match = re.search(r"appointment\s*id\s*(\d+)", question, re.IGNORECASE)
    if not match:
        match = re.search(r"id\s*(\d+)", question, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            pass
    return None

def extract_appointment_details(question, operation):
    """
    Use LLM to extract structured details for booking/canceling/rescheduling.
    Returns a dict with relevant fields.
    """
    prompt = (
        f"Extract the following details from the user's request for an appointment {operation}:\n"
        "- doctor_name (first and last, if available)\n"
        "- patient_name (first and last, if available)\n"
        "- appointment_date (YYYY-MM-DD)\n"
        "- appointment_time (HH:MM, 24h)\n"
        "- new_appointment_date (for reschedule, if present)\n"
        "- new_appointment_time (for reschedule, if present)\n"
        "- reason_for_visit (if present)\n"
        "- appointment_id (if present)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_doctor_registration_details(question):
    """
    Use LLM to extract structured details for doctor registration.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for doctor registration:\n"
        "- first_name (string)\n"
        "- last_name (string)\n"
        "- email (string)\n"
        "- phone (string, optional)\n"
        "- specialization (string, e.g., 'Cardiology', 'Dermatology', etc.)\n"
        "- license_number (string, optional)\n"
        "- experience_years (integer, optional)\n"
        "- consultation_fee (number, optional)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_patient_registration_details(question):
    """
    Use LLM to extract structured details for patient registration.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for patient registration:\n"
        "- first_name (string)\n"
        "- last_name (string)\n"
        "- email (string)\n"
        "- phone (string, optional)\n"
        "- date_of_birth (YYYY-MM-DD format, optional)\n"
        "- gender (string: 'Male', 'Female', or 'Other', optional)\n"
        "- address (string, optional)\n"
        "- emergency_contact_name (string, optional)\n"
        "- emergency_contact_phone (string, optional)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_specialization_registration_details(question):
    """
    Use LLM to extract structured details for specialization registration.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for specialization registration:\n"
        "- name (string, required) - the name of the specialization\n"
        "- description (string, optional) - description of the specialization\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_availability_registration_details(question):
    """
    Use LLM to extract structured details for doctor availability registration.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for doctor availability registration:\n"
        "- doctor_name (string, first and last name of the doctor)\n"
        "- day_of_week (integer: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday)\n"
        "- start_time (string, HH:MM format, 24-hour)\n"
        "- end_time (string, HH:MM format, 24-hour)\n"
        "- slot_duration (integer, minutes, optional, default 30)\n"
        "- max_patients_per_slot (integer, optional, default 1)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_doctor_update_details(question):
    """
    Use LLM to extract structured details for doctor updates.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for updating a doctor:\n"
        "- doctor_id (integer, if mentioned)\n"
        "- doctor_name (string, first and last name of the doctor, if no ID)\n"
        "- first_name (string, new first name if mentioned)\n"
        "- last_name (string, new last name if mentioned)\n"
        "- email (string, new email if mentioned)\n"
        "- phone (string, new phone if mentioned)\n"
        "- specialization (string, new specialization if mentioned)\n"
        "- license_number (string, new license number if mentioned)\n"
        "- experience_years (integer, new experience years if mentioned)\n"
        "- consultation_fee (number, new consultation fee if mentioned)\n"
        "- is_active (boolean, true/false if mentioned)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_patient_update_details(question):
    """
    Use LLM to extract structured details for patient updates.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for updating a patient:\n"
        "- patient_id (integer, if mentioned)\n"
        "- patient_name (string, first and last name of the patient, if no ID)\n"
        "- first_name (string, new first name if mentioned)\n"
        "- last_name (string, new last name if mentioned)\n"
        "- email (string, new email if mentioned)\n"
        "- phone (string, new phone if mentioned)\n"
        "- date_of_birth (YYYY-MM-DD format, new date if mentioned)\n"
        "- gender (string: 'Male', 'Female', or 'Other', new gender if mentioned)\n"
        "- address (string, new address if mentioned)\n"
        "- emergency_contact_name (string, new emergency contact name if mentioned)\n"
        "- emergency_contact_phone (string, new emergency contact phone if mentioned)\n"
        "- is_active (boolean, true/false if mentioned)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_specialization_update_details(question):
    """
    Use LLM to extract structured details for specialization updates.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for updating a specialization:\n"
        "- specialization_id (integer, if mentioned)\n"
        "- specialization_name (string, name of the specialization to update, if no ID)\n"
        "- new_name (string, new name if mentioned)\n"
        "- new_description (string, new description if mentioned, including if user says 'details as ...' or 'description as ...')\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def extract_availability_update_details(question):
    """
    Use LLM to extract structured details for availability updates.
    Returns a dict with relevant fields.
    """
    prompt = (
        "Extract the following details from the user's request for updating doctor availability:\n"
        "- availability_id (integer, if mentioned)\n"
        "- doctor_name (string, first and last name of the doctor, if no ID)\n"
        "- day_of_week (integer: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday, new day if mentioned)\n"
        "- start_time (string, HH:MM format, 24-hour, new start time if mentioned)\n"
        "- end_time (string, HH:MM format, 24-hour, new end time if mentioned)\n"
        "- slot_duration (integer, minutes, new slot duration if mentioned)\n"
        "- max_patients_per_slot (integer, new max patients per slot if mentioned)\n"
        "- is_active (boolean, true/false if mentioned)\n"
        "Return a JSON object with these fields. If a field is not mentioned, use null. Do not include any explanation, just the JSON.\n"
        f"User request: {question}"
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    json_text = result["choices"][0]["message"]["content"].strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    import json as pyjson
    try:
        return pyjson.loads(json_text)
    except Exception:
        return {}

def get_help_message():
    """
    Returns a user-friendly help message as HTML.
    """
    help_html = """
    <div style="font-family: Arial, sans-serif; max-width: 700px;">
      <h2>Doctor Agent - Healthcare Management System</h2>
      <p>
        I'm your <b>AI-powered healthcare assistant</b> that can help you manage doctors, patients, appointments, and more.<br>
        <b>Here's what I can do:</b>
      </p>
      <h3>Registration &amp; Management</h3>
      <ul>
        <li>
          <b>Doctors:</b>
          <ul>
            <li>Register new doctors: <i>Register a new doctor named Dr. John Smith with email john@hospital.com, specialization Cardiology</i></li>
            <li>Update doctor details: <i>Update Dr. John Smith's phone number to 555-1234</i></li>
            <li>Deactivate doctors: <i>Deactivate Dr. John Smith</i></li>
            <li>Search doctors: <i>Find all cardiologists</i> or <i>Search for Dr. Smith</i></li>
          </ul>
        </li>
        <li>
          <b>Patients:</b>
          <ul>
            <li>Register new patients: <i>Register a new patient named John Doe with email john@email.com</i></li>
            <li>Update patient details: <i>Update John Doe's phone number to 555-5678</i></li>
            <li>Deactivate patients: <i>Deactivate patient John Doe</i></li>
          </ul>
        </li>
        <li>
          <b>Specializations:</b>
          <ul>
            <li>Add new specializations: <i>Add specialization Oncology with description Cancer treatment</i></li>
            <li>Update specializations: <i>Update Cardiology description to Heart and cardiovascular specialist</i></li>
            <li>Remove specializations: <i>Delete specialization Dermatology</i></li>
          </ul>
        </li>
        <li>
          <b>Appointments &amp; Availability:</b>
          <ul>
            <li>Book appointments: <i>Book appointment for John Doe with Dr. Smith on 2024-01-15 at 10:00 AM</i></li>
            <li>Reschedule: <i>Reschedule appointment ID 123 to 2024-01-16 at 2:00 PM</i></li>
            <li>Cancel appointments: <i>Cancel appointment ID 123</i></li>
            <li>Set doctor availability: <i>Add availability for Dr. Smith on Monday from 9:00 AM to 5:00 PM</i></li>
            <li>Update availability: <i>Update Dr. Smith's Monday schedule to 10:00 AM to 6:00 PM</i></li>
          </ul>
        </li>
      </ul>
      <h3>Information Queries</h3>
      <ul>
        <li>Show all cardiologists</li>
        <li>List appointments for Dr. Smith on Monday</li>
        <li>Find patients with email containing 'john'</li>
        <li>Get all available slots for Dr. Johnson on Tuesday</li>
        <li>What is Dr. Smith's schedule for tomorrow?</li>
        <li>Show patient John Doe's appointments</li>
      </ul>
      <h3>Tips</h3>
      <ul>
        <li>You can use natural language - I'll understand what you mean!</li>
        <li>For updates, mention what you want to change</li>
        <li>I can find records by name or ID</li>
        <li>All operations are validated and safe</li>
      </ul>
      <p><b>Need help with something specific? Just ask!</b></p>
    </div>
    """
    return help_html

def find_doctor_id_by_name(doctor_name):
    if not doctor_name:
        return None
    name_parts = doctor_name.strip().split()
    docs = get_doctors()
    for doc in docs:
        full_name = f"{doc['first_name']} {doc['last_name']}".lower()
        if all(part.lower() in full_name for part in name_parts):
            return doc['id']
    return None

def find_patient_id_by_name(patient_name):
    if not patient_name:
        return None
    name_parts = patient_name.strip().split()
    pats = get_patients()
    for pat in pats:
        full_name = f"{pat['first_name']} {pat['last_name']}".lower()
        if all(part.lower() in full_name for part in name_parts):
            return pat['id']
    return None

def get_appointment_details_with_names(appt_id):
    appt = get_appointment_by_id(appt_id)
    if not appt:
        return None
    doc = get_doctor_by_id(appt["doctor_id"])
    pat = get_patient_by_id(appt["patient_id"])
    details = dict(appt)
    if doc:
        details["doctor_name"] = f"{doc['first_name']} {doc['last_name']}"
    if pat:
        details["patient_name"] = f"{pat['first_name']} {pat['last_name']}"
    return details

def handle_user_query(question):
    op = parse_operation(question)
    
    # Handle help queries first
    if op == "help":
        return {"success": True, "message": get_help_message()}

    if op in ("book", "cancel", "reschedule", "register_doctor", "register_patient", "register_specialization", "register_availability", 
               "update_doctor", "update_patient", "update_specialization", "update_availability",
               "delete_doctor", "delete_patient", "delete_specialization", "delete_availability", "search"):
        
        # Handle registration operations
        if op == "register_doctor":
            details = extract_doctor_registration_details(question)
            print(f"[DEBUG] Extracted doctor details: {details}")
            
            # Validate required fields
            if not all([details.get("first_name"), details.get("last_name"), details.get("email")]):
                return {"success": False, "message": "Missing required details for doctor registration (first name, last name, email)."}
            
            # Get specialization ID if provided
            specialization_id = None
            if details.get("specialization"):
                spec = get_specialization_by_name(details["specialization"])
                if spec:
                    specialization_id = spec["id"]
                else:
                    return {"success": False, "message": f"Specialization '{details['specialization']}' not found. Available specializations: Cardiology, Dermatology, Pediatrics, Orthopedics, Neurology, General Medicine, Psychiatry, ENT."}
            
            # Register the doctor
            doctor_id = add_doctor(
                first_name=details["first_name"],
                last_name=details["last_name"],
                email=details["email"],
                phone=details.get("phone"),
                specialization_id=specialization_id,
                license_number=details.get("license_number"),
                experience_years=details.get("experience_years"),
                consultation_fee=details.get("consultation_fee")
            )
            
            if isinstance(doctor_id, dict) and doctor_id.get("error"):
                return {"success": False, "message": doctor_id["error"]}
            
            doctor_details = get_doctor_by_id(doctor_id)
            return {"success": True, "message": "Doctor registered successfully!", "doctor_id": doctor_id, "details": doctor_details}
        
        elif op == "register_patient":
            details = extract_patient_registration_details(question)
            print(f"[DEBUG] Extracted patient details: {details}")
            
            # Validate required fields
            if not all([details.get("first_name"), details.get("last_name"), details.get("email")]):
                return {"success": False, "message": "Missing required details for patient registration (first name, last name, email)."}
            
            # Register the patient
            patient_id = add_patient(
                first_name=details["first_name"],
                last_name=details["last_name"],
                email=details["email"],
                phone=details.get("phone"),
                date_of_birth=details.get("date_of_birth"),
                gender=details.get("gender"),
                address=details.get("address"),
                emergency_contact_name=details.get("emergency_contact_name"),
                emergency_contact_phone=details.get("emergency_contact_phone")
            )
            
            if isinstance(patient_id, dict) and patient_id.get("error"):
                return {"success": False, "message": patient_id["error"]}
            
            patient_details = get_patient_by_id(patient_id)
            return {"success": True, "message": "Patient registered successfully!", "patient_id": patient_id, "details": patient_details}
        
        elif op == "register_specialization":
            details = extract_specialization_registration_details(question)
            print(f"[DEBUG] Extracted specialization details: {details}")
            
            # Validate required fields
            if not details.get("name"):
                return {"success": False, "message": "Missing required details for specialization registration (name)."}
            
            # Register the specialization
            specialization_id = add_specialization(
                name=details["name"],
                description=details.get("description")
            )
            
            if isinstance(specialization_id, dict) and specialization_id.get("error"):
                return {"success": False, "message": specialization_id["error"]}
            
            specialization_details = get_specialization_by_id(specialization_id)
            return {"success": True, "message": "Specialization registered successfully!", "specialization_id": specialization_id, "details": specialization_details}
        
        elif op == "register_availability":
            details = extract_availability_registration_details(question)
            print(f"[DEBUG] Extracted availability details: {details}")
            
            # Validate required fields
            if not all([details.get("doctor_name"), details.get("day_of_week") is not None, details.get("start_time"), details.get("end_time")]):
                return {"success": False, "message": "Missing required details for availability registration (doctor name, day of week, start time, end time)."}
            
            # Find doctor by name
            doctor_id = find_doctor_id_by_name(details["doctor_name"])
            if not doctor_id:
                return {"success": False, "message": f"Doctor '{details['doctor_name']}' not found."}
            
            # Validate day of week
            day_of_week = details["day_of_week"]
            if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return {"success": False, "message": "Day of week must be an integer between 0 (Sunday) and 6 (Saturday)."}
            
            # Register the availability
            availability_id = add_doctor_availability(
                doctor_id=doctor_id,
                day_of_week=day_of_week,
                start_time=details["start_time"],
                end_time=details["end_time"],
                slot_duration=details.get("slot_duration", 30),
                max_patients_per_slot=details.get("max_patients_per_slot", 1)
            )
            
            if isinstance(availability_id, dict) and availability_id.get("error"):
                return {"success": False, "message": availability_id["error"]}
            
            availability_details = get_doctor_availability_by_id(availability_id)
            doctor_details = get_doctor_by_id(doctor_id)
            if availability_details and doctor_details:
                availability_details["doctor_name"] = f"{doctor_details['first_name']} {doctor_details['last_name']}"
            
            return {"success": True, "message": "Doctor availability registered successfully!", "availability_id": availability_id, "details": availability_details}
        
        # Handle update operations
        elif op == "update_doctor":
            details = extract_doctor_update_details(question)
            print(f"[DEBUG] Extracted doctor update details: {details}")
            
            # Find doctor by ID or name
            doctor_id = details.get("doctor_id")
            if not doctor_id:
                doctor_id = find_doctor_id_by_name(details.get("doctor_name"))
                if not doctor_id:
                    return {"success": False, "message": f"Doctor '{details.get('doctor_name')}' not found."}
            
            # Get specialization ID if provided
            if details.get("specialization"):
                spec = get_specialization_by_name(details["specialization"])
                if spec:
                    details["specialization_id"] = spec["id"]
                else:
                    return {"success": False, "message": f"Specialization '{details['specialization']}' not found."}
            
            # Remove non-update fields
            update_data = {k: v for k, v in details.items() if k not in ["doctor_id", "doctor_name", "specialization"] and v is not None}
            
            if not update_data:
                return {"success": False, "message": "No valid fields to update."}
            
            # Update the doctor
            result = update_doctor(doctor_id, **update_data)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                doctor_details = get_doctor_by_id(doctor_id)
                return {"success": True, "message": "Doctor updated successfully!", "doctor_id": doctor_id, "details": doctor_details}
            else:
                return {"success": False, "message": "Failed to update doctor."}
        
        elif op == "update_patient":
            details = extract_patient_update_details(question)
            print(f"[DEBUG] Extracted patient update details: {details}")
            
            # Find patient by ID or name
            patient_id = details.get("patient_id")
            if not patient_id:
                patient_id = find_patient_id_by_name(details.get("patient_name"))
                if not patient_id:
                    return {"success": False, "message": f"Patient '{details.get('patient_name')}' not found."}
            
            # Remove non-update fields
            update_data = {k: v for k, v in details.items() if k not in ["patient_id", "patient_name"] and v is not None}
            
            if not update_data:
                return {"success": False, "message": "No valid fields to update."}
            
            # Update the patient
            result = update_patient(patient_id, **update_data)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                patient_details = get_patient_by_id(patient_id)
                return {"success": True, "message": "Patient updated successfully!", "patient_id": patient_id, "details": patient_details}
            else:
                return {"success": False, "message": "Failed to update patient."}
        
        elif op == "update_specialization":
            details = extract_specialization_update_details(question)
            print(f"[DEBUG] Extracted specialization update details: {details}")
            
            # Find specialization by ID or name
            specialization_id = details.get("specialization_id")
            if not specialization_id:
                spec = get_specialization_by_name(details.get("specialization_name"))
                if spec:
                    specialization_id = spec["id"]
                else:
                    return {"success": False, "message": f"Specialization '{details.get('specialization_name')}' not found."}
            
            # Prepare update data
            update_data = {}
            if details.get("new_name"):
                update_data["name"] = details["new_name"]
            if details.get("new_description") is not None:
                update_data["description"] = details["new_description"]
            
            if not update_data:
                return {"success": False, "message": "No valid fields to update."}
            
            # Update the specialization
            result = update_specialization(specialization_id, **update_data)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                specialization_details = get_specialization_by_id(specialization_id)
                return {"success": True, "message": "Specialization updated successfully!", "specialization_id": specialization_id, "details": specialization_details}
            else:
                return {"success": False, "message": "Failed to update specialization."}
        
        elif op == "update_availability":
            details = extract_availability_update_details(question)
            print(f"[DEBUG] Extracted availability update details: {details}")
            
            # Find availability by ID or doctor name + day
            availability_id = details.get("availability_id")
            if not availability_id:
                doctor_id = find_doctor_id_by_name(details.get("doctor_name"))
                if not doctor_id:
                    return {"success": False, "message": f"Doctor '{details.get('doctor_name')}' not found."}
                
                # Find availability record
                availabilities = get_doctor_availability(doctor_id=doctor_id, day_of_week=details.get("day_of_week"))
                if availabilities:
                    availability_id = availabilities[0]["id"]
                else:
                    return {"success": False, "message": f"No availability record found for this doctor on the specified day."}
            
            # Remove non-update fields
            update_data = {k: v for k, v in details.items() if k not in ["availability_id", "doctor_name"] and v is not None}
            
            if not update_data:
                return {"success": False, "message": "No valid fields to update."}
            
            # Update the availability
            result = update_doctor_availability(availability_id, **update_data)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                availability_details = get_doctor_availability_by_id(availability_id)
                return {"success": True, "message": "Doctor availability updated successfully!", "availability_id": availability_id, "details": availability_details}
            else:
                return {"success": False, "message": "Failed to update doctor availability."}
        
        # Handle delete operations
        elif op == "delete_doctor":
            details = extract_doctor_update_details(question)  # Reuse the same extraction
            doctor_id = details.get("doctor_id")
            if not doctor_id:
                doctor_id = find_doctor_id_by_name(details.get("doctor_name"))
                if not doctor_id:
                    return {"success": False, "message": f"Doctor '{details.get('doctor_name')}' not found."}
            
            result = delete_doctor(doctor_id)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                return {"success": True, "message": f"Doctor with ID {doctor_id} deleted successfully!"}
            else:
                return {"success": False, "message": "Failed to delete doctor."}
        
        elif op == "delete_patient":
            details = extract_patient_update_details(question)  # Reuse the same extraction
            patient_id = details.get("patient_id")
            if not patient_id:
                patient_id = find_patient_id_by_name(details.get("patient_name"))
                if not patient_id:
                    return {"success": False, "message": f"Patient '{details.get('patient_name')}' not found."}
            
            result = delete_patient(patient_id)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                return {"success": True, "message": f"Patient with ID {patient_id} deleted successfully!"}
            else:
                return {"success": False, "message": "Failed to delete patient."}
        
        elif op == "delete_specialization":
            details = extract_specialization_update_details(question)  # Reuse the same extraction
            specialization_id = details.get("specialization_id")
            if not specialization_id:
                spec = get_specialization_by_name(details.get("specialization_name"))
                if spec:
                    specialization_id = spec["id"]
                else:
                    return {"success": False, "message": f"Specialization '{details.get('specialization_name')}' not found."}
            
            result = delete_specialization(specialization_id)
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "message": result["error"]}
            
            if result:
                return {"success": True, "message": f"Specialization with ID {specialization_id} deleted successfully!"}
            else:
                return {"success": False, "message": "Failed to delete specialization."}
        
        elif op == "delete_availability":
            details = extract_availability_update_details(question)  # Reuse the same extraction
            availability_id = details.get("availability_id")
            if not availability_id:
                doctor_id = find_doctor_id_by_name(details.get("doctor_name"))
                if not doctor_id:
                    return {"success": False, "message": f"Doctor '{details.get('doctor_name')}' not found."}
                
                # Find availability record
                availabilities = get_doctor_availability(doctor_id=doctor_id, day_of_week=details.get("day_of_week"))
                if availabilities:
                    availability_id = availabilities[0]["id"]
                else:
                    return {"success": False, "message": f"No availability record found for this doctor on the specified day."}
            
            result = delete_doctor_availability(availability_id)
            if result:
                return {"success": True, "message": f"Availability with ID {availability_id} deleted successfully!"}
            else:
                return {"success": False, "message": "Failed to delete availability."}
        
        # Handle search operations
        elif op == "search":
            # For search operations, fall through to SQL generation
            pass
        
        # Handle appointment operations
        details = extract_appointment_details(question, op)
        print(f"[DEBUG] Extracted details: {details}")
        # Map names to IDs
        doctor_id = find_doctor_id_by_name(details.get("doctor_name"))
        patient_id = find_patient_id_by_name(details.get("patient_name"))
        # Book
        if op == "book":
            if not all([doctor_id, patient_id, details.get("appointment_date"), details.get("appointment_time")]):
                return {"success": False, "message": "Missing required details for booking (doctor, patient, date, time)."}
            # Check slot availability (do NOT check doctor_availability table)
            appts = get_appointments(doctor_id=doctor_id, date=details["appointment_date"])
            slot_taken = any(a["appointment_time"] == details["appointment_time"] and a["status"] not in ("cancelled",) for a in appts)
            if slot_taken:
                return {"success": False, "message": "Selected slot is already booked for this doctor."}
            # Allow booking even if doctor has no availability record
            appt_id = add_appointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                appointment_date=details["appointment_date"],
                appointment_time=details["appointment_time"],
                duration=30,
                status="scheduled",
                reason_for_visit=details.get("reason_for_visit"),
                notes=None
            )
            if isinstance(appt_id, dict) and appt_id.get("error"):
                return {"success": False, "message": appt_id["error"]}
            appt_details = get_appointment_details_with_names(appt_id)
            return {"success": True, "message": f"Appointment booked!", "appointment_id": appt_id, "details": appt_details}

        elif op == "cancel":
            appt_id = extract_appointment_id(details, question)
            if appt_id:
                ok = cancel_appointment(appt_id)
                appt_details = get_appointment_details_with_names(appt_id)
                if ok:
                    return {"success": True, "message": f"Appointment {appt_id} cancelled.", "appointment_id": appt_id, "details": appt_details}
                else:
                    return {"success": False, "message": f"Failed to cancel appointment {appt_id}."}
            # Try to find by doctor, patient, date, time
            appts = get_appointments(doctor_id=doctor_id, patient_id=patient_id, date=details.get("appointment_date"))
            for a in appts:
                if (details.get("appointment_time") is None or a["appointment_time"] == details.get("appointment_time")):
                    appt_id = a["id"]
                    break
            if not appt_id:
                return {"success": False, "message": "Could not identify the appointment to cancel."}
            ok = cancel_appointment(appt_id)
            appt_details = get_appointment_details_with_names(appt_id)
            if ok:
                return {"success": True, "message": f"Appointment {appt_id} cancelled.", "appointment_id": appt_id, "details": appt_details}
            else:
                return {"success": False, "message": f"Failed to cancel appointment {appt_id}."}
        # Reschedule
        elif op == "reschedule":
            appt_id = extract_appointment_id(details, question)
            new_date = details.get("new_appointment_date") or details.get("appointment_date")
            new_time = details.get("new_appointment_time") or details.get("appointment_time")
            if appt_id:
                if not all([new_date, new_time]):
                    return {"success": False, "message": "Missing new date/time for rescheduling."}
                # Check slot availability
                appt = get_appointment_by_id(appt_id)
                if not appt:
                    return {"success": False, "message": f"Appointment {appt_id} not found."}
                doctor_id = appt["doctor_id"]
                appts = get_appointments(doctor_id=doctor_id, date=new_date)
                slot_taken = any(a["appointment_time"] == new_time and a["status"] not in ("cancelled",) for a in appts)
                if slot_taken:
                    return {"success": False, "message": "Selected new slot is already booked for this doctor."}
                ok = update_appointment(appt_id, appointment_date=new_date, appointment_time=new_time)
                appt_details = get_appointment_details_with_names(appt_id)
                if ok:
                    return {"success": True, "message": f"Appointment {appt_id} rescheduled to {new_date} at {new_time}.", "appointment_id": appt_id, "details": appt_details}
                else:
                    return {"success": False, "message": f"Failed to reschedule appointment {appt_id}."}
            # Try to find by doctor, patient, date, time
            appts = get_appointments(doctor_id=doctor_id, patient_id=patient_id, date=details.get("appointment_date"))
            for a in appts:
                if (details.get("appointment_time") is None or a["appointment_time"] == details.get("appointment_time")):
                    appt_id = a["id"]
                    break
            if not appt_id:
                return {"success": False, "message": "Could not identify the appointment to reschedule."}
            if not all([new_date, new_time]):
                return {"success": False, "message": "Missing new date/time for rescheduling."}
            # Check slot availability
            appt = get_appointment_by_id(appt_id)
            if not appt:
                return {"success": False, "message": f"Appointment {appt_id} not found."}
            doctor_id = appt["doctor_id"]
            appts = get_appointments(doctor_id=doctor_id, date=new_date)
            slot_taken = any(a["appointment_time"] == new_time and a["status"] not in ("cancelled",) for a in appts)
            if slot_taken:
                return {"success": False, "message": "Selected new slot is already booked for this doctor."}
            ok = update_appointment(appt_id, appointment_date=new_date, appointment_time=new_time)
            appt_details = get_appointment_details_with_names(appt_id)
            if ok:
                return {"success": True, "message": f"Appointment {appt_id} rescheduled to {new_date} at {new_time}.", "appointment_id": appt_id, "details": appt_details}
            else:
                return {"success": False, "message": f"Failed to reschedule appointment {appt_id}."}
    
    # Fallback: try to generate SQL and run it
    sql = get_sql_from_llm(question)
    sql_lower = sql.strip().lower()
    try:
        if sql_lower.startswith("select"):
            rows = query_database(sql)
            return {"sql": sql, "results": rows}
        elif sql_lower.startswith(("update", "delete", "insert")):
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                conn.commit()
            return {"sql": sql, "success": True, "message": "Operation completed successfully."}
        else:
            # For other SQL types, just run and return generic message
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                conn.commit()
            return {"sql": sql, "success": True, "message": "SQL executed."}
    except Exception as e:
        return {"sql": sql, "error": str(e)}
