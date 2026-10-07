# Clinic Operations Assistant - User Guide

Welcome to the Clinic Operations Assistant! This AI-powered assistant is designed to handle time-consuming, day-to-day clinic tasks—such as finding available time slots, rescheduling appointments, and checking therapist calendars—simply by chatting with it in natural language.

This guide will show you how to start the application for the first time, configure your settings (including model choices and optional proxy routing), and walk through real-world examples demonstrating how the assistant handles requests, catches human errors, and enforces clinic rules.

---

## 1. Initial Setup (First Time Only)

For the assistant to process your requests, it needs an AI model provider (such as Google Gemini or OpenAI).

### Step 1: Configure your API Key & Settings

1. In the main project folder, find the file named `.env.example`. Make a copy of it and rename the copy to `.env`.
2. Open the `.env` file in any text editor.
3. Configure your API key:
   * **Google Gemini (Recommended / Free Tier):** Paste your key after `GOOGLE_API_KEY=`.
   * **OpenAI:** Paste your key after `OPENAI_API_KEY=`.
4. *(Optional)* Select a specific model using `LLM_MODEL`:
   * `google_genai:gemini-3.5-flash-lite` (Default in `.env.example`, verified on Google AI Studio Free Tier)
   * `google_genai:gemini-3.8-flash` (High-reasoning Free Tier workhorse)
   * `openai:gpt-4o-mini`
   * *If `LLM_MODEL` is omitted, the application automatically detects the correct provider based on your configured API key.*
5. *(Optional)* Configure a Network Proxy:
   * If you are behind a firewall or in a region requiring outbound proxy routing, uncomment the proxy variables in `.env`:
     ```bash
     # HTTP/HTTPS Proxy
     HTTPS_PROXY="http://127.0.0.1:8080"
     HTTP_PROXY="http://127.0.0.1:8080"

     # Or SOCKS5 Proxy
     SOCKS_PROXY="socks5://127.0.0.1:2080"
     ALL_PROXY="socks5://127.0.0.1:2080"
     ```
   * The assistant automatically synchronizes these settings into global network clients (`httpx` and Google GenAI SDKs).

### Step 2: Run the Application

Open your terminal in the project folder and start the assistant:

```bash
uv run python -m app.cli
```

You will see the startup banner displaying the fixed clinic demo clock, session thread ID, and the interactive prompt:

```text
==================================================
   Clinic Operations Assistant - Vertical Slice   
==================================================
Clinic Clock: 2026-10-12 Monday 09:00 (Asia/Tehran)
Session Thread: 4a2b9e6f1c7d4289b88931a72d4e5f10
Available tools: search_appointments, find_available_slots, reschedule_appointment
Type 'exit' or 'quit' to terminate.

Manager > 
```

---

## 2. Real-World Examples

Below are real scenarios showing how the assistant handles operational tasks and safeguards the clinic against mistakes.

### Scenario 1: Smart Rescheduling (No Manual Lookup Needed)

You do not need to look up appointment IDs manually. Just state the patient's name, the therapist, and your desired time window. The assistant searches the database, finds the appointment ID, checks open slots, and reschedules automatically.

> **Manager >** Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest available slot after 2 PM.  
> **Assistant >** Sara Ahmadi's appointment with Dr. Rezaei tomorrow (October 13, 2026) has been successfully rescheduled from 09:00 to the earliest available slot after 2:00 PM:  
> * **Appointment ID:** `apt_rezaei_01`  
> * **New Appointment Time:** 2026-10-13 at 14:00 (until 14:45)  
> * **Therapist:** Dr. Rezaei  
> * **Patient:** Sara Ahmadi  

### Scenario 2: Preventing Mistakes Due to Name Ambiguity

If you provide an incomplete name (such as only a surname), the assistant will not guess. It halts write operations and requests clarification so that another patient's booking is never moved by mistake.

> **Manager >** Move Ahmadi's appointment tomorrow to 2 PM.  
> **Assistant >** I found multiple appointments matching the surname "Ahmadi" for tomorrow (October 13, 2026):  
> 1. **Ali Ahmadi** with Dr. Rezaei (10:00 – 11:00)  
> 2. **Ali Ahmadi** with Dr. Moradi (11:00 – 12:00)  
> 3. **Sara Ahmadi** with Dr. Moradi (12:00 – 13:00)  
> Could you please specify which patient and which appointment you would like to move to 2:00 PM?  

### Scenario 3: Handling Fully Booked Days & Correcting Mistakes

If a therapist is fully booked, the assistant reports no availability and will never invent fake slots. Furthermore, if you misremember which therapist you or a patient have a session with, the assistant politely corrects the details based on the database.

> **Manager >** Find open slots for Dr. Moradi tomorrow and move my 10 AM session to one of them.  
> **Assistant >** I checked Dr. Moradi's schedule for tomorrow (October 13, 2026), but there are currently **no available open slots** (all slots are fully booked from 09:00 to 17:00).  
> Additionally, looking at Dr. Moradi's schedule, there is no 10:00 AM session listed for you with Dr. Moradi; however, there is a 10:00 AM session scheduled tomorrow with **Dr. Rezaei** (Ali Ahmadi).  
> Would you like me to check available slots for Dr. Rezaei instead?  

### Scenario 4: Conversational Memory (Context Awareness)

The assistant remembers context across conversation turns. If you ask about a therapist's schedule, you can ask follow-up questions without repeating the therapist's name.

> **Manager >** Show me Dr. Rezaei's availability tomorrow.  
> **Assistant >** Here are the available time slots for Dr. Rezaei tomorrow (October 13, 2026):  
> * 09:00 – 09:45  
> * 09:15 – 10:00  
> * 11:45 – 12:30  
> * 14:00 – 14:45  
> ...  
>   
> **Manager >** What about Thursday?  
> **Assistant >** Here are the available time slots for Dr. Rezaei on Thursday (October 15, 2026):  
> * 09:00 – 09:45  
> * 09:15 – 10:00  
> ...  
> Would you like to schedule or move any appointment to one of these slots on Thursday?  

### Scenario 5: Protection Against Human Errors (Past Dates or Invalid IDs)

The system strictly enforces clinic rules: appointments cannot be moved to past dates, outside therapist working hours, or onto conflicting bookings.

> **Manager >** Reschedule appointment apt_1001 to yesterday at 10 AM.  
> **Assistant >** I cannot fulfill this request for two reasons:  
> 1. **Invalid Appointment ID:** `apt_1001` does not exist in our system. You can discover valid IDs using `search_appointments`.  
> 2. **Past Date:** You requested to reschedule an appointment to yesterday (October 11, 2026), which is in the past. Appointments can only be scheduled for present or future dates.  

### Scenario 6: Nonexistent Therapist Guard

If you query a practitioner not registered in the clinic, the assistant reports the error gracefully without failing or making up schedule entries.

> **Manager >** Find slots for Dr. Strange tomorrow.  
> **Assistant >** I could not find a therapist named "Dr. Strange" in the clinic records. Currently registered therapists are **Dr. Rezaei** (Clinical Psychology) and **Dr. Moradi** (Psychiatry). Please verify the therapist name and try again.  

---

## 3. Testing and Evaluation

You can verify the assistant's behavior using built-in offline test suites and live evaluation scripts:

* **Offline Test Suite (No API Key or internet required):**
  ```bash
  uv run pytest
  ```
  Runs all unit tests (services, tools, LLM configuration) and graph integration tests with simulated models.

* **Live Evaluation Suite (Evaluates real model accuracy):**
  ```bash
  uv run python -m evals.run --runs 3
  ```
  Runs all 4 operational scenarios across 3 iterations and outputs a pass-rate summary.

---

## 4. Exiting the Application

To end your session, type `exit` or `quit` in the prompt, or press `Ctrl + C` on your keyboard.
