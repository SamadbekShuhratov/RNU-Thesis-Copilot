# Bu loyihani kurs ishi sifatida himoya qilish bo'yicha tavsiyalar

Bu tizimning o'zi sizning kurs ishingiz bo'lgani uchun, u RNU talablarining hammasiga o'zi ham javob berishi kerak.
Quyida — **yo'nalish**, tayyor matn emas: ifodalarni o'zingiz yozing va rahbaringiz bilan kelishing.

## 3-Arrow Logic xaritasi

| Strelka | Sizning ishingizda |
|---|---|
| **Muammo** | RNU ishlarida formal xatolar (bir gapli bo'lmagan maqsad, faktsiz muammo, bobsiz xulosa, to'qilgan manbalar) va rahbarlarning tekshiruvga sarflaydigan vaqti. *Raqamlarni o'zingiz yig'ing:* rahbarlar so'rovnomasi, o'quv bo'limi statistikasi, eski ishlar tahlili. |
| **Mavjud usullar** | Grammatika/uslub tekshirgichlari, umumiy LLM chat-yordamchilar, reference managerlar (Zotero), RAG tizimlari, multi-agent framework'lar (LangGraph, AutoGen, CrewAI). Kuchli/zaif tomonlarini taqqoslang. |
| **O'z amaliy usulingiz** | Lokal LLM + deterministik RNU validatori + tasdiqlangan manbalar + human-in-the-loop interrupt + checkpoint tarixi. |

## Uchta tezis uchun yo'nalish (o'zingiz ifodalang)

1. *OFFERED* — siz taklif qilgan arxitektura (8 xodim, PM gate, interrupt/resume).
2. *MODIFIED* — siz o'zgartirgan mavjud usul (masalan, RAG pipeline'ga mustaqil Crossref tekshiruvi va "faqat o'lchangan raqam" qoidasi qo'shilgan).
3. *SUGGESTED* — tavsiya (masalan, AI yordamidagi akademik ishlarda mualliflik shaffofligi uchun bosqichma-bosqich tasdiqlash tartibi).

## 3-bob uchun empirik tajribalar (haqiqiy o'lchang!)

| Tajriba | Baseline | Proposed | Ko'rsatkich | Vosita |
|---|---|---|---|---|
| Validator aniqligi | qo'lda checklist bo'yicha tekshirish | 1-xodim | precision, recall, F1, vaqt | `scripts/benchmark_validators.py` (datasetni mustaqil yorliqlangan haqiqiy misollar bilan kengaytiring — hozirgi namunalar validator bilan bir vaqtda yozilgan, shuning uchun 100% natija dalil emas) |
| To'qilgan manbalar | LLM'dan to'g'ridan-to'g'ri manba so'rash | OpenAlex + Crossref pipeline | tasdiqlangan manbalar ulushi | `scripts/benchmark_citations.py` |
| Tayyorlash vaqti / xatolar | talabalar odatiy usulda | talabalar tizim bilan | xatolar soni, daqiqalar | kichik foydalanuvchi tajribasi (5–10 talaba) |
| Model tanlovi | llama3.1:8b | qwen2.5:14b | JSON xatolari, sekundlar | portal "Faollik" jurnali (har bir LLM chaqiruvi vaqti) |

Natijalarni CSV (`metric,variant,value,run`) ko'rinishida portalga yuklang — statistikani tizim o'zi hisoblaydi.

## Himoyada ko'rsatish uchun

* Demo: `start.bat --demo` → to'liq workflow 1–2 daqiqada.
* Bloklashni ko'rsating: "Analyze information systems." maqsadi → `GOAL_VAGUE`; 3-bobda CSV'siz tasdiqlash → rad etiladi.
* Testlar: `python -m pytest` (21 ta test).
* `docs/ARCHITECTURE.md` diagrammalari va checkpoint tarixi (Tarix tabi).
