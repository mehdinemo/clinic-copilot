# راهنمای استفاده از دستیار هوشمند کلینیک (Clinic Operations Assistant)

به دستیار هوشمند مدیریت کلینیک خوش آمدید! این دستیار طراحی شده است تا کارهای زمان‌بر و روزمره کلینیک مانند پیدا کردن وقت‌های خالی، جابه‌جایی نوبت‌ها و بررسی تقویم درمانگران را به سادگی و با زبان محاوره برای شما انجام دهد.

این راهنما به شما نشان می‌دهد که چگونه برای اولین بار برنامه را اجرا کنید و با چند مثال واقعی، قدرت و هوشمندی این دستیار را در مدیریت خطاهای احتمالی ببینید.

---

## ۱. پیش‌نیازها و اجرای اولیه (فقط برای بار اول)

برای اینکه دستیار بتواند درخواست‌های شما را پردازش کند، به یک «مغز متفکر» (مدل هوش مصنوعی مثل Google Gemini یا OpenAI) نیاز دارد.

**مرحله اول: تنظیم کلید دسترسی (API Key)**

1. در پوشه اصلی برنامه، فایلی به نام `.env.example` وجود دارد. از این فایل یک کپی بگیرید و نام آن را دقیقاً `.env` بگذارید.
2. فایل `.env` را با یک ویرایشگر متن باز کنید.
3. کلید دسترسی گوگل (Google API Key) یا OpenAI خود را در این فایل قرار دهید (مثلاً جلوی `GOOGLE_API_KEY=`).

**مرحله دوم: اجرای برنامه**
ترمینال (یا خط فرمان) سیستم خود را باز کنید و دستور زیر را وارد کنید تا محیط چت با دستیار باز شود:

```bash
uv run python -m app.cli

```

پس از اجرای این دستور، پیام خوش‌آمدگویی، تاریخ و ساعت فعلی کلینیک را مشاهده خواهید کرد و خط فرمان `Manager >` منتظر دستورات شما خواهد ماند.

---

## ۲. مثال‌های عملی از امکانات دستیار

در ادامه، چند سناریوی واقعی از مکالمه با دستیار آورده شده است تا ببینید چطور در موقعیت‌های مختلف به شما کمک می‌کند.

### سناریو اول: جابه‌جایی هوشمند یک نوبت (بدون نیاز به جستجوی دستی)

شما فقط کافیست نام بیمار، پزشک و زمان حدودی را بگویید. دستیار خودش در دیتابیس می‌گردد، شناسه نوبت را پیدا می‌کند، اولین وقت خالی را می‌سنجد و نوبت را جابه‌جا می‌کند.

> **Manager >** Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest available slot after 2 PM.
> **Assistant >** Sara Ahmadi's appointment with Dr. Rezaei tomorrow (October 13, 2026) has been successfully rescheduled from 09:00 to the earliest available slot after 2:00 PM:
> * **New Appointment Time:** 2026-10-13 at 14:00 (until 14:45)
> * **Therapist:** Dr. Rezaei
> * **Patient:** Sara Ahmadi
> 
> 

### سناریو دوم: جلوگیری از اشتباهات به دلیل تشابه اسمی

اگر نام بیماری را ناقص بگویید (مثلاً فقط نام خانوادگی)، دستیار برای جلوگیری از جابه‌جایی اشتباه نوبت دیگران، هیچ اقدامی نمی‌کند و از شما می‌خواهد شخص مورد نظر را دقیقاً مشخص کنید.

> **Manager >** Move Ahmadi's appointment tomorrow to 2 PM.
> **Assistant >** I found multiple appointments matching the surname "Ahmadi" for tomorrow (October 13, 2026):
> 1. **Ali Ahmadi** with Dr. Rezaei (10:00 – 11:00)
> 2. **Ali Ahmadi** with Dr. Moradi (11:00 – 12:00)
> 3. **Sara Ahmadi** with Dr. Moradi (12:00 – 13:00)
> ...
> Could you please specify which patient and which appointment you would like to move to 2:00 PM?
> 
> 

### سناریو سوم: بررسی روزهای پر و اصلاح اشتباهات مدیر

اگر دکتری وقت خالی نداشته باشد، دستیار وقت خیالی نمی‌سازد. همچنین اگر شما در درخواست خود دچار اشتباه شوید (مثلاً نام دکتر را اشتباه به یاد بیاورید)، دستیار با بررسی تقویم، اشتباه شما را محترمانه اصلاح می‌کند.

> **Manager >** Find open slots for Dr. Moradi tomorrow and move my 10 AM session to one of them.
> **Assistant >** I checked Dr. Moradi's schedule for tomorrow (October 13, 2026), but there are currently **no available open slots** (all slots are fully booked).
> Additionally, looking at Dr. Moradi's schedule, there is no 10:00 AM session listed for you with Dr. Moradi; however, you do have a 10:00 AM session scheduled tomorrow with **Dr. Rezaei** (Ali Ahmadi).
> Would you like me to check available slots for Dr. Rezaei or another therapist instead?

### سناریو چهارم: حافظه مکالمه (درک زمینه گفتگو)

دستیار مکالمات قبلی شما را به یاد می‌آورد. اگر تقویم یک دکتر را بپرسید، در سوال بعدی نیازی نیست نام دکتر را تکرار کنید.

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

### سناریو پنجم: محافظت در برابر خطاهای انسانی (تایم‌های گذشته یا شناسه‌های نامعتبر)

سیستم اجازه نمی‌دهد نوبتی را به تاریخی در گذشته منتقل کنید یا با شناسه‌های نامعتبر کار کنید. دستیار خطای سیستم را به زبانی ساده برای شما ترجمه می‌کند.

> **Manager >** Reschedule appointment apt_1001 to yesterday at 10 AM.
> **Assistant >** I cannot fulfill this request for two reasons:
> 1. **Invalid Appointment ID:** `apt_1001` does not exist in our system.
> 2. **Past Date:** You requested to reschedule an appointment to yesterday (October 11, 2026), which is in the past. Appointments can only be scheduled for present or future dates.
> 
> 

---

## ۳. خروج از برنامه

برای پایان دادن به کار و بستن دستیار، کافیست در خط فرمان کلمه `exit` یا `quit` را تایپ کنید و یا کلیدهای `Ctrl + C` را روی کیبورد خود فشار دهید.
