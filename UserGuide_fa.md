# راهنمای استفاده از دستیار هوشمند کلینیک (Clinic Operations Assistant)

به دستیار هوشمند مدیریت کلینیک خوش آمدید! این دستیار طراحی شده است تا کارهای زمان‌بر و روزمره کلینیک مانند پیدا کردن وقت‌های خالی، جابه‌جایی نوبت‌ها و بررسی تقویم درمانگران را به سادگی و با زبان محاوره برای شما انجام دهد.

این راهنما به شما نشان می‌دهد که چگونه برای اولین بار برنامه را اجرا کنید، تنظیمات مدل و پروکسی را پیکربندی نمایید، و با مثال‌های عملی، نحوه برخورد دستیار با درخواست‌ها و مدیریت خطاهای انسانی را مشاهده کنید.

---

## ۱. پیش‌نیازها و اجرای اولیه (فقط برای بار اول)

برای اینکه دستیار بتواند درخواست‌های شما را پردازش کند، به یک ارائه‌دهنده مدل هوش مصنوعی (مانند Google Gemini یا OpenAI) نیاز دارد.

### مرحله اول: تنظیم کلید دسترسی (API Key) و مدل

۱. در پوشه اصلی برنامه، فایلی به نام `.env.example` وجود دارد. از این فایل یک کپی بگیرید و نام آن را دقیقاً `.env` بگذارید.  
۲. فایل `.env` را با یک ویرایشگر متن باز کنید.  
۳. کلید دسترسی خود را وارد نمایید:  
   * **گوگل جمینای (پیشنهادی / دارای سهمیه رایگان):** کلید خود را جلوی `GOOGLE_API_KEY=` قرار دهید.  
   * **اوپن‌ای‌آی:** کلید خود را جلوی `OPENAI_API_KEY=` قرار دهید.  
۴. *(اختیاری)* انتخاب مدل با متغیر `LLM_MODEL`:  
   * `google_genai:gemini-3.5-flash-lite` (مدل پیش‌فرض و سبک، تایید شده در پلن رایگان Google AI Studio)  
   * `google_genai:gemini-3.8-flash` (مدل قدرتمند با استدلال بالا در پلن رایگان)  
   * `openai:gpt-4o-mini`  
   * *در صورت عدم تعیین مدل، برنامه به صورت خودکار بر اساس کلید وارد شده، ارائه‌دهنده مناسب را انتخاب می‌کند.*  
۵. *(اختیاری)* تنظیم پروکسی شبکه:  
   * در صورتی که در محیط شبکه خود نیاز به پروکسی (HTTP یا SOCKS5) دارید، متغیرهای پروکسی را در `.env` فعال کنید:  
     ```bash
     # پروکسی HTTP/HTTPS
     HTTPS_PROXY="http://127.0.0.1:8080"
     HTTP_PROXY="http://127.0.0.1:8080"

     # یا پروکسی SOCKS5
     SOCKS_PROXY="socks5://127.0.0.1:2080"
     ALL_PROXY="socks5://127.0.0.1:2080"
     ```  
   * دستیار به طور خودکار تمام ترافیک مدل را از طریق پروکسی تنظیم‌شده هدایت می‌کند.

### مرحله دوم: اجرای برنامه

ترمینال سیستم خود را در پوشه پروژه باز کرده و دستور زیر را اجرا کنید:

```bash
uv run python -m app.cli
```

یا در صورت تمایل می‌توانید برنامه را در کانتینر داکر اجرا کنید:

```bash
docker build -t clinic-copilot .
docker run --rm -it --env-file .env clinic-copilot
```

پس از اجرای این دستور، بنر آغازین به همراه ساعت نمایشی کلینیک، شناسه نشست و خط فرمان `Manager >` نمایش داده خواهد شد:

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

## ۲. مثال‌های عملی از امکانات دستیار

در ادامه، سناریوهای واقعی از مکالمه با دستیار آورده شده است تا ببینید چطور در موقعیت‌های مختلف به شما کمک می‌کند.

### سناریو اول: جابه‌جایی هوشمند یک نوبت (بدون نیاز به جستجوی دستی)

شما نیازی به حفظ کردن شناسه نوبت‌ها ندارید. کافیست نام بیمار، پزشک و زمان مورد نظرتان را بگویید. دستیار در دیتابیس جستجو کرده، شناسه نوبت را می‌یابد، وقت خالی را بررسی می‌کند و نوبت را منتقل می‌نماید:

> **Manager >** Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest available slot after 2 PM.  
> **Assistant >** Sara Ahmadi's appointment with Dr. Rezaei tomorrow (October 13, 2026) has been successfully rescheduled from 09:00 to the earliest available slot after 2:00 PM:  
> * **Appointment ID:** `apt_rezaei_01`  
> * **New Appointment Time:** 2026-10-13 at 14:00 (until 14:45)  
> * **Therapist:** Dr. Rezaei  
> * **Patient:** Sara Ahmadi  

### سناریو دوم: جلوگیری از اشتباهات به دلیل تشابه اسمی

اگر نام بیماری را ناقص بگویید (مثلاً فقط نام خانوادگی)، دستیار برای جلوگیری از جابه‌جایی اشتباه نوبت دیگران، هیچ عملیات تغییری انجام نمی‌دهد و از شما درخواست شفاف‌سازی می‌کند:

> **Manager >** Move Ahmadi's appointment tomorrow to 2 PM.  
> **Assistant >** I found multiple appointments matching the surname "Ahmadi" for tomorrow (October 13, 2026):  
> 1. **Ali Ahmadi** with Dr. Rezaei (10:00 – 11:00)  
> 2. **Ali Ahmadi** with Dr. Moradi (11:00 – 12:00)  
> 3. **Sara Ahmadi** with Dr. Moradi (12:00 – 13:00)  
> Could you please specify which patient and which appointment you would like to move to 2:00 PM?  

### سناریو سوم: بررسی روزهای پر و اصلاح اشتباهات مدیر

اگر دکتری وقت خالی نداشته باشد، دستیار وقت خیالی نمی‌سازد. همچنین اگر در درخواست خود اشتباه کنید (مثلاً نام پزشک جلسه خود را اشتباه بگویید)، دستیار با بررسی تقویم، شما را راهنمایی و اصلاح می‌کند:

> **Manager >** Find open slots for Dr. Moradi tomorrow and move my 10 AM session to one of them.  
> **Assistant >** I checked Dr. Moradi's schedule for tomorrow (October 13, 2026), but there are currently **no available open slots** (all slots are fully booked from 09:00 to 17:00).  
> Additionally, looking at Dr. Moradi's schedule, there is no 10:00 AM session listed for you with Dr. Moradi; however, there is a 10:00 AM session scheduled tomorrow with **Dr. Rezaei** (Ali Ahmadi).  
> Would you like me to check available slots for Dr. Rezaei or another therapist instead?  

### سناریو چهارم: حافظه مکالمه (درک زمینه گفتگو)

دستیار حافظه مکالمه دارد. اگر تقویم یک دکتر را بررسی کنید، در سوال بعدی نیازی به تکرار نام پزشک نخواهید داشت:

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

### سناریو پنجم: محافظت در برابر خطاهای انسانی (تایم‌های گذشته یا شناسه‌های نامعتبر)

سیستم به شدت قوانین کلینیک را کنترل می‌کند: نوبت‌ها نمی‌توانند به گذشته، خارج از ساعات کاری پزشک یا روی وقت‌های اشغال‌شده منتقل شوند:

> **Manager >** Reschedule appointment apt_1001 to yesterday at 10 AM.  
> **Assistant >** I cannot fulfill this request for two reasons:  
> 1. **Invalid Appointment ID:** `apt_1001` does not exist in our system. (You can find valid IDs using `search_appointments`).  
> 2. **Past Date:** You requested to reschedule an appointment to yesterday (October 11, 2026), which is in the past. Appointments can only be scheduled for present or future dates.  

### سناریو ششم: محافظت در برابر نام درمانگر ناشناخته

اگر نام پزشکی را جستجو کنید که در کلینیک ثبت نشده است، دستیار به صورت مودبانه و بدون خطا، نبود پزشک را اعلام می‌کند:

> **Manager >** Find slots for Dr. Strange tomorrow.  
> **Assistant >** I could not find a therapist named "Dr. Strange" in the clinic records. Currently registered therapists are **Dr. Rezaei** (Clinical Psychology) and **Dr. Moradi** (Psychiatry). Please verify the therapist name and try again.  

---

## ۳. اجرای آزمون‌ها و ارزیابی سیستم

برای بررسی صحت عملکرد دستیار، می‌توانید آزمون‌های آفلاین و ارزیابی زنده را اجرا کنید:

* **مجموعه تست‌های آفلاین (بدون نیاز به اینترنت و بدون نیاز به کلید API):**  
  ```bash
  uv run pytest
  ```  
  شامل تست‌های واحد سرویس‌ها، ابزارها، پیکربندی LLM و آزمون‌های یکپارچگی گراف.

* **مجموعه ارزیابی زنده مدل (تست دقت سناریوهای عملیاتی با مدل واقعی):**  
  ```bash
  uv run python -m evals.run --runs 3
  ```  
  اجرای هر ۴ سناریوی عملیاتی در ۳ تکرار و گزارش درصد موفقیت (Pass Rate).

* **بررسی استایل و سازگاری نوع ایستا (Linting & Type Checking):**  
  ```bash
  uv run ruff check .
  uv run mypy
  ```  
  بررسی ساختار و تمیزی کد با Ruff و تحلیل نوع ایستا با Mypy.

---

## ۴. خروج از برنامه

برای بستن دستیار و پایان نشست، کافیست در خط فرمان کلمه `exit` یا `quit` را وارد کنید یا کلیدهای `Ctrl + C` را روی صفحه‌کلید فشار دهید.
