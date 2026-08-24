# System Design

## 1. System Overview

The Healthcare Appointment Manager is designed to provide a reliable way for patients to view doctor availability and book appointments. The system manages doctors, patients, appointments, leave schedules, and notifications. The design focuses on preventing conflicting appointments and maintaining consistent booking information.

The main appointment flow is:

**Patient → Select Doctor → Select Date/Time → Check Availability → Confirm Appointment → Store Appointment → Send Notification**

The system validates availability before an appointment is confirmed. This ensures that appointment-related operations are controlled by the application's business rules rather than relying only on the user interface.

---

## 2. Double-Booking Prevention

Double-booking occurs when two patients attempt to reserve the same doctor at the same date and time. The system prevents this by checking the appointment records before creating a new booking.

When a patient selects a doctor, date, and time slot, the system checks whether an active appointment already exists for the same doctor and time. If the slot is already occupied, the booking request is rejected and the patient is asked to select another available slot.

The appointment can be identified using the combination:

**Doctor + Appointment Date + Time Slot + Appointment Status**

Cancelled appointments should not block a slot, while confirmed or active appointments should make the slot unavailable.

The availability check should also be performed immediately before the final appointment is created. This is important because another user may have booked the same slot while the first patient was completing the booking process.

Where supported by the database, the final availability check and appointment creation should be performed as an atomic transaction. This reduces the risk of race conditions where two requests attempt to book the same slot simultaneously.

---

## 3. Doctor Leave Conflict Handling

Doctor leave is treated as part of the doctor's availability schedule. Before an appointment is created, the system checks whether the selected doctor is available on the requested date.

If the doctor is marked as being on leave, the system prevents new appointments from being created for that date or affected period.

The system should also consider appointments that already exist when a doctor adds leave. If existing appointments conflict with newly recorded leave, these appointments should be identified for administrative action. Depending on the application's workflow, they can be cancelled, rescheduled, or communicated to the affected patients.

This approach prevents patients from booking appointments when the doctor is unavailable and helps maintain consistency between the doctor's schedule and the appointment database.

---

## 4. Slot Hold Mechanism

A slot-hold mechanism can be used to temporarily reserve a selected appointment slot while a patient is completing the booking process.

The slot follows a simple state transition:

**Available → Held → Confirmed**

When the patient begins the booking process, the selected slot can be marked as **Held** for a limited period. During this period, other patients should not be allowed to reserve the same slot.

If the patient successfully completes the booking, the held slot becomes **Confirmed**.

If the patient abandons the booking or the hold period expires, the slot is released and returns to the **Available** state.

The system should check the current hold status again when the patient confirms the appointment. This prevents an expired hold from being used to create an invalid appointment.

A time limit on holds is important because otherwise users could reserve slots indefinitely without completing their appointments.

---

## 5. Notification Failure Handling

Notifications are used to inform patients about appointment confirmations, cancellations, reminders, or other appointment-related events.

The notification process should be separated from the core appointment transaction. First, the appointment should be successfully created or updated in the database. The system can then attempt to send the notification.

The process can be represented as:

**Appointment Saved → Notification Attempt → Success / Failure**

If the notification is successfully delivered, the system can record the notification status.

If notification delivery fails because of a temporary email, network, or external-service problem, the appointment should not be deleted or marked as unsuccessful. Instead, the failure should be recorded so that the notification can be retried or reviewed by an administrator.

This separation ensures that a notification-service failure does not cause a valid appointment booking to be lost.

---

## 6. Overall Appointment Booking Flow

The complete design can be summarized as:

```text
Patient selects Doctor
        ↓
Select Date and Time
        ↓
Check Doctor Availability
        ↓
Check Doctor Leave
        ↓
Check Slot Availability
        ↓
Create Temporary Hold
        ↓
Final Availability Check
        ↓
Confirm Appointment
        ↓
Store Appointment
        ↓
Update Slot Status
        ↓
Send Notification
        ↓
Success / Retry on Failure
```

## 7. Design Goals

The system is designed around four main goals:

1. **Consistency** – prevent conflicting or duplicate appointments.
2. **Availability Management** – ensure doctor leave is respected.
3. **Reliable Booking** – temporarily protect slots during the booking process.
4. **Fault Tolerance** – ensure notification failures do not invalidate successful appointments.

Overall, the design provides a controlled appointment-booking workflow in which availability, doctor schedules, slot status, appointment confirmation, and notifications are handled as separate but connected components. This helps make the Healthcare Appointment Manager more reliable, maintainable, and suitable for real-world appointment-management scenarios.
