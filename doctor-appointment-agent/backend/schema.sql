-- Doctor Availability and Appointment Management System
-- PostgreSQL Database Schema

-- Drop tables if they exist (for fresh setup)
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS doctor_availability CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS specializations CASCADE;

-- Create Specializations table
CREATE TABLE specializations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Doctors table
CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    specialization_id INTEGER REFERENCES specializations(id),
    license_number VARCHAR(50) UNIQUE,
    experience_years INTEGER,
    consultation_fee DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Patients table
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(10),
    address TEXT,
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Doctor Availability table
CREATE TABLE doctor_availability (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Sunday, 6=Saturday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration INTEGER DEFAULT 30, -- Duration in minutes
    max_patients_per_slot INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_time_range CHECK (start_time < end_time)
);

-- Create Appointments table
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration INTEGER DEFAULT 30, -- Duration in minutes
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
    reason_for_visit TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doctor_id, appointment_date, appointment_time)
);

-- Create indexes for better performance
CREATE INDEX idx_doctors_specialization ON doctors(specialization_id);
CREATE INDEX idx_doctor_availability_doctor ON doctor_availability(doctor_id);
CREATE INDEX idx_doctor_availability_day ON doctor_availability(day_of_week);
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, appointment_date);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_status ON appointments(status);

-- Insert sample data

-- Specializations
INSERT INTO specializations (name, description) VALUES
('Cardiology', 'Heart and cardiovascular system specialist'),
('Dermatology', 'Skin, hair, and nail specialist'),
('Pediatrics', 'Child healthcare specialist'),
('Orthopedics', 'Bone and joint specialist'),
('Neurology', 'Brain and nervous system specialist'),
('General Medicine', 'Primary care and general health'),
('Psychiatry', 'Mental health specialist'),
('ENT', 'Ear, Nose, and Throat specialist');

-- Doctors (Fixed: Removed duplicate license numbers and ensured unique emails)
INSERT INTO doctors (first_name, last_name, email, phone, specialization_id, license_number, experience_years, consultation_fee) VALUES
('John', 'Smith', 'john.smith@hospital.com', '+1-555-0101', 1, 'MD001', 15, 200.00),
('Sarah', 'Johnson', 'sarah.johnson@hospital.com', '+1-555-0102', 2, 'MD002', 8, 180.00),
('Michael', 'Brown', 'michael.brown@hospital.com', '+1-555-0103', 3, 'MD003', 12, 150.00),
('Emily', 'Davis', 'emily.davis@hospital.com', '+1-555-0104', 4, 'MD004', 10, 220.00),
('David', 'Wilson', 'david.wilson@hospital.com', '+1-555-0105', 5, 'MD005', 18, 250.00),
('Lisa', 'Anderson', 'lisa.anderson@hospital.com', '+1-555-0106', 6, 'MD006', 6, 120.00),
('Anthony', 'Miller', 'anthony.miller@hospital.com', '+1-555-0110', 1, 'MD007', 7, 190.00),
('Natalie', 'Moore', 'natalie.moore@hospital.com', '+1-555-0111', 2, 'MD008', 9, 185.00),
('Kevin', 'Taylor', 'kevin.taylor@hospital.com', '+1-555-0112', 3, 'MD009', 5, 140.00),
('Laura', 'Clark', 'laura.clark@hospital.com', '+1-555-0113', 4, 'MD010', 11, 210.00),
('Brian', 'Lewis', 'brian.lewis@hospital.com', '+1-555-0114', 5, 'MD011', 13, 240.00),
('Rachel', 'Hall', 'rachel.hall@hospital.com', '+1-555-0115', 6, 'MD012', 4, 115.00),
('George', 'Allen', 'george.allen@hospital.com', '+1-555-0116', 1, 'MD013', 16, 205.00),
('Megan', 'Scott', 'megan.scott@hospital.com', '+1-555-0117', 2, 'MD014', 8, 170.00),
('Samuel', 'King', 'samuel.king@hospital.com', '+1-555-0118', 3, 'MD015', 6, 135.00),
('Laura', 'Scott', 'laura.scott@hospital.com', '+1-555-0107', 7, 'MD016', 11, 210.00),  
('Brian', 'Hall', 'brian.hall@hospital.com', '+1-555-0108', 3, 'MD017', 7, 160.00),     
('Natalie', 'King', 'natalie.king@hospital.com', '+1-555-0109', 8, 'MD018', 9, 190.00), 
('George', 'Baker', 'george.baker@hospital.com', '+1-555-0120', 4, 'MD019', 13, 230.00);

-- Patients
INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone) VALUES
('Alice', 'Cooper', 'alice.cooper@email.com', '+1-555-1001', '1985-03-15', 'Female', '123 Main St, City, State 12345', 'Bob Cooper', '+1-555-1002'),
('Robert', 'Taylor', 'robert.taylor@email.com', '+1-555-1003', '1978-07-22', 'Male', '456 Oak Ave, City, State 12345', 'Mary Taylor', '+1-555-1004'),
('Jennifer', 'White', 'jennifer.white@email.com', '+1-555-1005', '1990-11-08', 'Female', '789 Pine Rd, City, State 12345', 'James White', '+1-555-1006'),
('William', 'Harris', 'william.harris@email.com', '+1-555-1007', '1972-05-30', 'Male', '321 Elm St, City, State 12345', 'Susan Harris', '+1-555-1008'),
('Maria', 'Garcia', 'maria.garcia@email.com', '+1-555-1009', '1988-09-12', 'Female', '654 Maple Dr, City, State 12345', 'Carlos Garcia', '+1-555-1010'),
('James', 'Martinez', 'james.martinez@email.com', '+1-555-1011', '1995-01-25', 'Male', '987 Cedar Ln, City, State 12345', 'Rosa Martinez', '+1-555-1012'),
('Olivia', 'Turner', 'olivia.turner@email.com', '+1-555-1013', '1992-04-18', 'Female', '111 Birch St, City, State 12345', 'Ethan Turner', '+1-555-1014'),
('Benjamin', 'Lee', 'benjamin.lee@email.com', '+1-555-1015', '1980-06-05', 'Male', '222 Spruce Ave, City, State 12345', 'Nina Lee', '+1-555-1016'),
('Sophia', 'Wright', 'sophia.wright@email.com', '+1-555-1017', '1975-10-30', 'Female', '333 Cypress Blvd, City, State 12345', 'Daniel Wright', '+1-555-1018'),
('Ethan', 'Clark', 'ethan.clark@email.com', '+1-555-1019', '2000-02-14', 'Male', '444 Redwood Dr, City, State 12345', 'Mia Clark', '+1-555-1020'),
('Chloe', 'Walker', 'chloe.walker@email.com', '+1-555-1021', '1998-08-12', 'Female', '555 Aspen Ln, City, State 12345', 'Noah Walker', '+1-555-1022'),
('Daniel', 'Young', 'daniel.young@email.com', '+1-555-1023', '1983-12-09', 'Male', '666 Sequoia Ct, City, State 12345', 'Lily Young', '+1-555-1024');

-- Doctor Availability (Fixed: Corrected doctor IDs and removed duplicates)
INSERT INTO doctor_availability (
    doctor_id,
    day_of_week,
    start_time,
    end_time,
    slot_duration,
    max_patients_per_slot
) VALUES

-- Dr. John Smith (Cardiology) - ID: 1
(1, 1, '09:00:00', '17:00:00', 30, 1),
(1, 2, '09:00:00', '17:00:00', 30, 1),
(1, 3, '09:00:00', '17:00:00', 30, 1),
(1, 4, '09:00:00', '17:00:00', 30, 1),
(1, 5, '09:00:00', '13:00:00', 30, 1),
(1, 0, '10:00:00', '14:00:00', 30, 1),

-- Dr. Sarah Johnson (Dermatology) - ID: 2
(2, 1, '10:00:00', '18:00:00', 45, 1),
(2, 3, '10:00:00', '18:00:00', 45, 1),
(2, 5, '10:00:00', '18:00:00', 45, 1),
(2, 6, '09:00:00', '13:00:00', 45, 1),

-- Dr. Michael Brown (Pediatrics) - ID: 3
(3, 1, '08:00:00', '16:00:00', 20, 1),
(3, 2, '08:00:00', '16:00:00', 20, 1),
(3, 3, '08:00:00', '16:00:00', 20, 1),
(3, 4, '08:00:00', '16:00:00', 20, 1),
(3, 5, '08:00:00', '16:00:00', 20, 1),
(3, 6, '09:00:00', '13:00:00', 20, 1),

-- Dr. Emily Davis (Orthopedics) - ID: 4
(4, 2, '11:00:00', '19:00:00', 60, 1),
(4, 4, '11:00:00', '19:00:00', 60, 1),
(4, 6, '08:00:00', '14:00:00', 60, 1),

-- Dr. David Wilson (Neurology) - ID: 5
(5, 1, '14:00:00', '20:00:00', 45, 1),
(5, 3, '14:00:00', '20:00:00', 45, 1),
(5, 5, '14:00:00', '20:00:00', 45, 1),

-- Dr. Lisa Anderson (General Medicine) - ID: 6
(6, 1, '08:00:00', '16:00:00', 30, 1),
(6, 2, '08:00:00', '16:00:00', 30, 1),
(6, 3, '08:00:00', '16:00:00', 30, 1),
(6, 4, '08:00:00', '16:00:00', 30, 1),
(6, 5, '08:00:00', '16:00:00', 30, 1),
(6, 6, '08:00:00', '12:00:00', 30, 1),

-- Dr. Anthony Miller (Cardiology) - ID: 7
(7, 1, '08:00:00', '12:00:00', 30, 1),
(7, 2, '08:00:00', '12:00:00', 30, 1),
(7, 3, '08:00:00', '12:00:00', 30, 1),

-- Dr. Natalie Moore (Dermatology) - ID: 8
(8, 2, '10:00:00', '14:00:00', 45, 1),
(8, 4, '10:00:00', '14:00:00', 45, 1),

-- Dr. Kevin Taylor (Pediatrics) - ID: 9
(9, 1, '09:00:00', '17:00:00', 20, 1),
(9, 2, '09:00:00', '17:00:00', 20, 1),
(9, 3, '09:00:00', '17:00:00', 20, 1),
(9, 4, '09:00:00', '17:00:00', 20, 1),
(9, 5, '09:00:00', '17:00:00', 20, 1),

-- Dr. Laura Clark (Orthopedics) - ID: 10
(10, 3, '13:00:00', '17:00:00', 60, 1),
(10, 6, '09:00:00', '13:00:00', 60, 1),

-- Dr. Brian Lewis (Neurology) - ID: 11
(11, 5, '10:00:00', '18:00:00', 45, 1),

-- Dr. Laura Scott (Psychiatry) - ID: 16
(16, 2, '13:00:00', '18:00:00', 60, 1),
(16, 3, '13:00:00', '18:00:00', 60, 1),
(16, 4, '13:00:00', '18:00:00', 60, 1),
(16, 5, '13:00:00', '17:00:00', 60, 1),

-- Dr. Brian Hall (Pediatrics) - ID: 17
(17, 1, '08:00:00', '12:00:00', 20, 1),
(17, 2, '08:00:00', '12:00:00', 20, 1),
(17, 3, '08:00:00', '12:00:00', 20, 1),
(17, 4, '08:00:00', '12:00:00', 20, 1),
(17, 5, '08:00:00', '12:00:00', 20, 1),
(17, 6, '09:00:00', '11:00:00', 20, 1),

-- Dr. Natalie King (ENT) - ID: 18
(18, 3, '10:00:00', '14:00:00', 30, 1),
(18, 5, '10:00:00', '14:00:00', 30, 1),
(18, 6, '10:00:00', '13:00:00', 30, 1),

-- Dr. George Baker (Orthopedics) - ID: 19
(19, 2, '12:00:00', '18:00:00', 60, 1),
(19, 4, '12:00:00', '18:00:00', 60, 1),
(19, 6, '09:00:00', '14:00:00', 60, 1);

-- Sample Appointments
INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes) VALUES
(1, 1, '2025-07-21', '09:30:00', 30, 'scheduled', 'Chest pain evaluation', 'Patient reports intermittent chest pain'),
(2, 2, '2025-07-21', '10:45:00', 45, 'confirmed', 'Skin rash consultation', 'Rash on arms and legs'),
(3, 3, '2025-07-22', '08:20:00', 20, 'scheduled', 'Child wellness check', 'Annual checkup for 5-year-old'),
(4, 4, '2025-07-22', '12:00:00', 60, 'scheduled', 'Knee pain assessment', 'Chronic knee pain, possible arthritis'),
(5, 5, '2025-07-23', '14:45:00', 45, 'confirmed', 'Headache consultation', 'Frequent migraines'),
(6, 6, '2025-07-23', '09:00:00', 30, 'scheduled', 'General health checkup', 'Annual physical examination'),
(1, 6, '2025-07-24', '10:30:00', 30, 'completed', 'Follow-up consultation', 'Blood pressure check'),
(2, 1, '2025-07-25', '11:00:00', 30, 'cancelled', 'Cardiac screening', 'Patient cancelled due to schedule conflict'),
(7, 2, '2025-08-01', '10:00:00', 45, 'scheduled', 'Acne breakout', 'Patient experiencing severe acne'),
(8, 1, '2025-08-02', '09:00:00', 30, 'confirmed', 'Heart palpitations', 'Recommended ECG'),
(9, 6, '2025-08-03', '08:30:00', 30, 'scheduled', 'Routine physical exam', 'No major concerns'),
(10, 3, '2025-08-01', '08:00:00', 20, 'scheduled', 'Pediatric vaccination', 'Second dose of vaccine'),
(11, 4, '2025-08-02', '12:00:00', 60, 'scheduled', 'Back pain assessment', 'Suspected lumbar strain'),
(12, 5, '2025-08-02', '15:30:00', 45, 'scheduled', 'Frequent dizziness', 'Needs MRI referral'),
(7, 3, '2025-08-05', '09:00:00', 20, 'confirmed', 'Child cough and fever', 'Check lungs and temperature'),
(8, 6, '2025-08-05', '10:30:00', 30, 'scheduled', 'Follow-up diabetes check', 'Review latest lab results'),
(9, 5, '2025-08-06', '14:45:00', 45, 'scheduled', 'Memory issues', 'Family history of Alzheimer');
