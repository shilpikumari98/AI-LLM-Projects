from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from datetime import datetime
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def convert_row_to_dict(row):
    result = {}
    for key, value in row._mapping.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result

# --- Specializations ---
def get_specializations():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM specializations ORDER BY name ASC"))
        return [convert_row_to_dict(row) for row in result]

def add_specialization(name, description=None):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                INSERT INTO specializations (name, description)
                VALUES (:name, :description)
                RETURNING id
            """), {
                "name": name,
                "description": description
            })
            conn.commit()
            return result.fetchone()[0]
        except IntegrityError as e:
            return {"error": "A specialization with this name already exists."}

def get_specialization_by_id(specialization_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM specializations WHERE id = :id"), {"id": specialization_id})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

def update_specialization(specialization_id, **kwargs):
    allowed_fields = ["name", "description"]
    update_fields = []
    params = {"id": specialization_id}
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = kwargs[field]
    if not update_fields:
        return False
    query = f"UPDATE specializations SET {', '.join(update_fields)} WHERE id = :id"
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query), params)
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            if "name" in str(e):
                return {"error": "A specialization with this name already exists."}
            else:
                return {"error": "Failed to update specialization due to database constraint."}

def delete_specialization(specialization_id):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("DELETE FROM specializations WHERE id = :id"), {"id": specialization_id})
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            return {"error": "Cannot delete specialization as it is referenced by doctors."}

# --- Doctors ---
def get_doctors():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM doctors ORDER BY last_name, first_name ASC"))
        return [convert_row_to_dict(row) for row in result]

def get_doctor_by_id(doctor_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM doctors WHERE id = :id"), {"id": doctor_id})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

def add_doctor(first_name, last_name, email, phone=None, specialization_id=None, license_number=None, experience_years=None, consultation_fee=None):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                INSERT INTO doctors
                (first_name, last_name, email, phone, specialization_id, license_number, experience_years, consultation_fee)
                VALUES (:first_name, :last_name, :email, :phone, :specialization_id, :license_number, :experience_years, :consultation_fee)
                RETURNING id
            """), {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "specialization_id": specialization_id,
                "license_number": license_number,
                "experience_years": experience_years,
                "consultation_fee": consultation_fee
            })
            conn.commit()
            return result.fetchone()[0]
        except IntegrityError as e:
            if "email" in str(e):
                return {"error": "A doctor with this email already exists."}
            elif "license_number" in str(e):
                return {"error": "A doctor with this license number already exists."}
            else:
                return {"error": "Failed to register doctor due to database constraint."}

def update_doctor(doctor_id, **kwargs):
    allowed_fields = ["first_name", "last_name", "email", "phone", "specialization_id", "license_number", "experience_years", "consultation_fee", "is_active"]
    update_fields = []
    params = {"id": doctor_id}
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = kwargs[field]
    if not update_fields:
        return False
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE doctors SET {', '.join(update_fields)} WHERE id = :id"
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query), params)
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            if "email" in str(e):
                return {"error": "A doctor with this email already exists."}
            elif "license_number" in str(e):
                return {"error": "A doctor with this license number already exists."}
            else:
                return {"error": "Failed to update doctor due to database constraint."}

def delete_doctor(doctor_id):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("DELETE FROM doctors WHERE id = :id"), {"id": doctor_id})
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            return {"error": "Cannot delete doctor as they have appointments or availability records."}

def get_specialization_by_name(name):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM specializations WHERE LOWER(name) = LOWER(:name)"), {"name": name})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

# --- Patients ---
def get_patients():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM patients ORDER BY last_name, first_name ASC"))
        return [convert_row_to_dict(row) for row in result]

def get_patient_by_id(patient_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM patients WHERE id = :id"), {"id": patient_id})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

def add_patient(first_name, last_name, email, phone=None, date_of_birth=None, gender=None, address=None, emergency_contact_name=None, emergency_contact_phone=None):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                INSERT INTO patients
                (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone)
                VALUES (:first_name, :last_name, :email, :phone, :date_of_birth, :gender, :address, :emergency_contact_name, :emergency_contact_phone)
                RETURNING id
            """), {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "date_of_birth": date_of_birth,
                "gender": gender,
                "address": address,
                "emergency_contact_name": emergency_contact_name,
                "emergency_contact_phone": emergency_contact_phone
            })
            conn.commit()
            return result.fetchone()[0]
        except IntegrityError as e:
            if "email" in str(e):
                return {"error": "A patient with this email already exists."}
            else:
                return {"error": "Failed to register patient due to database constraint."}

def update_patient(patient_id, **kwargs):
    allowed_fields = ["first_name", "last_name", "email", "phone", "date_of_birth", "gender", "address", "emergency_contact_name", "emergency_contact_phone", "is_active"]
    update_fields = []
    params = {"id": patient_id}
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = kwargs[field]
    if not update_fields:
        return False
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE patients SET {', '.join(update_fields)} WHERE id = :id"
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query), params)
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            if "email" in str(e):
                return {"error": "A patient with this email already exists."}
            else:
                return {"error": "Failed to update patient due to database constraint."}

def delete_patient(patient_id):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("DELETE FROM patients WHERE id = :id"), {"id": patient_id})
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            return {"error": "Cannot delete patient as they have appointments."}

# --- Doctor Availability ---
def get_doctor_availability(doctor_id=None, day_of_week=None):
    query = "SELECT * FROM doctor_availability WHERE is_active = TRUE"
    params = {}
    if doctor_id:
        query += " AND doctor_id = :doctor_id"
        params["doctor_id"] = doctor_id
    if day_of_week is not None:
        query += " AND day_of_week = :day_of_week"
        params["day_of_week"] = day_of_week
    query += " ORDER BY start_time ASC"
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [convert_row_to_dict(row) for row in result]

def add_doctor_availability(doctor_id, day_of_week, start_time, end_time, slot_duration=30, max_patients_per_slot=1):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                INSERT INTO doctor_availability
                (doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot)
                VALUES (:doctor_id, :day_of_week, :start_time, :end_time, :slot_duration, :max_patients_per_slot)
                RETURNING id
            """), {
                "doctor_id": doctor_id,
                "day_of_week": day_of_week,
                "start_time": start_time,
                "end_time": end_time,
                "slot_duration": slot_duration,
                "max_patients_per_slot": max_patients_per_slot
            })
            conn.commit()
            return result.fetchone()[0]
        except IntegrityError as e:
            return {"error": "Failed to add doctor availability due to database constraint."}

def get_doctor_availability_by_id(availability_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM doctor_availability WHERE id = :id"), {"id": availability_id})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

def update_doctor_availability(availability_id, **kwargs):
    allowed_fields = ["day_of_week", "start_time", "end_time", "slot_duration", "max_patients_per_slot", "is_active"]
    update_fields = []
    params = {"id": availability_id}
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = kwargs[field]
    if not update_fields:
        return False
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE doctor_availability SET {', '.join(update_fields)} WHERE id = :id"
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query), params)
            conn.commit()
            return result.rowcount > 0
        except IntegrityError as e:
            return {"error": "Failed to update doctor availability due to database constraint."}

def delete_doctor_availability(availability_id):
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM doctor_availability WHERE id = :id"), {"id": availability_id})
        conn.commit()
        return result.rowcount > 0

# --- Appointments ---
def get_appointments(doctor_id=None, patient_id=None, date=None, status=None):
    query = "SELECT * FROM appointments WHERE 1=1"
    params = {}
    if doctor_id:
        query += " AND doctor_id = :doctor_id"
        params["doctor_id"] = doctor_id
    if patient_id:
        query += " AND patient_id = :patient_id"
        params["patient_id"] = patient_id
    if date:
        query += " AND appointment_date = :date"
        params["date"] = date
    if status:
        query += " AND status = :status"
        params["status"] = status
    query += " ORDER BY appointment_date, appointment_time ASC"
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [convert_row_to_dict(row) for row in result]

def get_appointment_by_id(appointment_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM appointments WHERE id = :id"), {"id": appointment_id})
        row = result.fetchone()
        return convert_row_to_dict(row) if row else None

def add_appointment(patient_id, doctor_id, appointment_date, appointment_time, duration=30, status='scheduled', reason_for_visit=None, notes=None):
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                INSERT INTO appointments
                (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes)
                VALUES (:patient_id, :doctor_id, :appointment_date, :appointment_time, :duration, :status, :reason_for_visit, :notes)
                RETURNING id
            """), {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "duration": duration,
                "status": status,
                "reason_for_visit": reason_for_visit,
                "notes": notes
            })
            conn.commit()
            return result.fetchone()[0]
        except IntegrityError as e:
            return {"error": "This slot is already booked for this doctor. Please choose another time."}

def update_appointment(appointment_id, **kwargs):
    allowed_fields = ["appointment_date", "appointment_time", "duration", "status", "reason_for_visit", "notes"]
    update_fields = []
    params = {"id": appointment_id}
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = kwargs[field]
    if not update_fields:
        return False
    query = f"UPDATE appointments SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        conn.commit()
        return result.rowcount > 0

def cancel_appointment(appointment_id):
    return update_appointment(appointment_id, status='cancelled')

def delete_appointment(appointment_id):
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM appointments WHERE id = :id"), {"id": appointment_id})
        conn.commit()
        return result.rowcount > 0

# --- Search and Utility Functions ---
def search_doctors(query=None, specialization_id=None, is_active=True):
    base_query = "SELECT d.*, s.name as specialization_name FROM doctors d LEFT JOIN specializations s ON d.specialization_id = s.id WHERE d.is_active = :is_active"
    params = {"is_active": is_active}
    
    if query:
        base_query += " AND (LOWER(d.first_name) LIKE LOWER(:query) OR LOWER(d.last_name) LIKE LOWER(:query) OR LOWER(d.email) LIKE LOWER(:query))"
        params["query"] = f"%{query}%"
    
    if specialization_id:
        base_query += " AND d.specialization_id = :specialization_id"
        params["specialization_id"] = specialization_id
    
    base_query += " ORDER BY d.last_name, d.first_name ASC"
    
    with engine.connect() as conn:
        result = conn.execute(text(base_query), params)
        return [convert_row_to_dict(row) for row in result]

def search_patients(query=None, is_active=True):
    base_query = "SELECT * FROM patients WHERE is_active = :is_active"
    params = {"is_active": is_active}
    
    if query:
        base_query += " AND (LOWER(first_name) LIKE LOWER(:query) OR LOWER(last_name) LIKE LOWER(:query) OR LOWER(email) LIKE LOWER(:query))"
        params["query"] = f"%{query}%"
    
    base_query += " ORDER BY last_name, first_name ASC"
    
    with engine.connect() as conn:
        result = conn.execute(text(base_query), params)
        return [convert_row_to_dict(row) for row in result]

def get_doctor_schedule(doctor_id, date):
    """Get doctor's schedule for a specific date including appointments and availability"""
    with engine.connect() as conn:
        # Get availability for the day of week
        day_of_week = date.weekday()  # Monday=0, Sunday=6
        if day_of_week == 6:  # Sunday
            day_of_week = 0
        else:
            day_of_week += 1  # Convert to our schema (Sunday=0, Monday=1, etc.)
        
        # Get availability
        availability_query = """
            SELECT * FROM doctor_availability 
            WHERE doctor_id = :doctor_id AND day_of_week = :day_of_week AND is_active = TRUE
        """
        availability_result = conn.execute(text(availability_query), {
            "doctor_id": doctor_id, 
            "day_of_week": day_of_week
        })
        availability = [convert_row_to_dict(row) for row in availability_result]
        
        # Get appointments
        appointments_query = """
            SELECT * FROM appointments 
            WHERE doctor_id = :doctor_id AND appointment_date = :date
            ORDER BY appointment_time ASC
        """
        appointments_result = conn.execute(text(appointments_query), {
            "doctor_id": doctor_id, 
            "date": date
        })
        appointments = [convert_row_to_dict(row) for row in appointments_result]
        
        return {
            "availability": availability,
            "appointments": appointments,
            "date": date,
            "day_of_week": day_of_week
        }
