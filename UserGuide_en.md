# Clinic Operations Assistant - User Guide

Welcome to the Clinic Operations Assistant! This AI-powered assistant is designed to handle time-consuming, day-to-day clinic tasks—such as finding available time slots, rescheduling appointments, and checking therapist calendars—simply by chatting with it in natural language.

This guide will show you how to start the application for the first time and provide real-world examples of how smart the assistant is at handling requests and catching human errors.

---

## 1. Initial Setup (First Time Only)

For the assistant to process your requests, it needs a "brain" (an AI model like Google Gemini or OpenAI).

**Step 1: Configure your API Key**

1. In the main project folder, find the file named `.env.example`. Make a copy of it and rename the copy to exactly `.env`.
2. Open the `.env` file in any text editor.
3. Paste your Google or OpenAI API key inside (for example, right after `GOOGLE_API_KEY=`).

**Step 2: Run the Application**
Open your terminal (or command prompt) in the project folder and type the following command to start chatting with the assistant:

```bash
uv run python -m app.cli

```

You will see a welcome message, the current clinic date and time, and a `Manager >` prompt waiting for your instructions.

---

## 2. Real-World Examples

Below are a few real scenarios showing how the assistant can help you in different situations.

### Scenario 1: Smart Rescheduling (No Manual Lookup Needed)

You don't need to memorize appointment IDs. Just mention the patient's name, the therapist, and your desired time. The assistant will search the database, find the correct ID, check for open slots, and reschedule it automatically.

> **Manager >** Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest available slot after 2 PM.
> **Assistant >** Sara Ahmadi's appointment with Dr. Rezaei tomorrow (October 13, 2026) has been successfully rescheduled from 09:00 to the earliest available slot after 2:00 PM:
> * **New Appointment Time:** 2026-10-13 at 14:00 (until 14:45)
> * **Therapist:** Dr. Rezaei
> * **Patient:** Sara Ahmadi
> 
> 

### Scenario 2: Preventing Mistakes Due to Name Ambiguity

If you provide an incomplete name (like just a surname), the assistant won't blindly guess. It stops and asks for clarification to prevent moving the wrong patient's appointment.

> **Manager >** Move Ahmadi's appointment tomorrow to 2 PM.
> **Assistant >** I found multiple appointments matching the surname "Ahmadi" for tomorrow (October 13, 2026):
> 1. **Ali Ahmadi** with Dr. Rezaei (10:00 – 11:00)
> 2. **Ali Ahmadi** with Dr. Moradi (11:00 – 12:00)
> 3. **Sara Ahmadi** with Dr. Moradi (12:00 – 13:00)
> ...
> Could you please specify which patient and which appointment you would like to move to 2:00 PM?
> 
> 

### Scenario 3: Handling Fully Booked Days & Correcting Mistakes

If a therapist is fully booked, the assistant won't invent fake slots. Also, if you make a mistake in your prompt (like misremembering the name of the therapist for your 10 AM session), it politely corrects you based on the actual database.

> **Manager >** Find open slots for Dr. Moradi tomorrow and move my 10 AM session to one of them.
> **Assistant >** I checked Dr. Moradi's schedule for tomorrow (October 13, 2026), but there are currently **no available open slots** (all slots are fully booked).
> Additionally, looking at Dr. Moradi's schedule, there is no 10:00 AM session listed for you with Dr. Moradi; however, you do have a 10:00 AM session scheduled tomorrow with **Dr. Rezaei** (Ali Ahmadi).
> Would you like me to check available slots for Dr. Rezaei or another therapist instead?

### Scenario 4: Conversational Memory (Context Awareness)

The assistant remembers the context of your conversation. If you ask about a therapist's calendar, you don't need to repeat the therapist's name in your very next question.

> **Manager >** Show me Dr. Rezaei's availability tomorrow.
> **Assistant >** Here are the available time slots for Dr. Rezaei tomorrow (October 13, 2026):
> * **09:00 – 09:45**
> * **09:15 – 10:00**
> ...
> 
> 
> **Manager >** What about Thursday?
> **Assistant >** Here are the available time slots for Dr. Rezaei on Thursday (October 15, 2026):
> * **09:00 – 09:45**
> * **09:15 – 10:00**
> ...
> Would you like to move Ali Ahmadi's session to any of these slots on Thursday?
> 
> 

### Scenario 5: Protection Against Human Errors (Past Dates or Invalid IDs)

The system strictly prevents moving appointments to the past or using invalid IDs. The assistant translates these system rules into simple, polite explanations.

> **Manager >** Reschedule appointment apt_1001 to yesterday at 10 AM.
> **Assistant >** I cannot fulfill this request for two reasons:
> 1. **Invalid Appointment ID:** `apt_1001` does not exist in our system. (To find the correct ID, you can search for appointments by patient or therapist name using `search_appointments`).
> 2. **Past Date:** You requested to reschedule an appointment to yesterday (October 11, 2026), which is in the past. Appointments can only be scheduled for present or future dates.
> 
> 

---

## 3. Exiting the Application

To end the session and close the assistant, simply type `exit` or `quit` in the prompt, or press `Ctrl + C` on your keyboard.
