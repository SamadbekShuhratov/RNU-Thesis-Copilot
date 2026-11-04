# RNU Thesis Copilot

Riga Nordic University (RNU) talabalari uchun **lokal, ko'p agentli, human-in-the-loop** yordamchi:
kurs ishi, bitiruv ishi va **RNU Science Week 2027** maqolasini RNU qoidalari asosida bosqichma-bosqich tayyorlash.

> **Co-pilot, ghostwriter emas.** Agentlar qoralama yozadi va tekshiradi; talaba har bir bosqichni tahrirlaydi va tasdiqlaydi.
> Statistika, manbalar va o'lchovlar faqat haqiqiy bo'lishi mumkin — tizim to'qilgan raqamlar va tasdiqlanmagan
> manbalarni **bloklaydi** hamda AI qoralamasining qancha qismi o'zgartirilganini hujjat ilovasida ko'rsatadi.

*English summary at the bottom.*

---

## Imkoniyatlar

| | |
|---|---|
| **8 xodimli workflow** | Arxitektor (sarlavha, obyekt/predmet, SMART maqsad, uchta tezis) → 1-bob → adabiyotlar sharhi → nazariy asos → amaliy qism va tajribalar → umumiy xulosa → bibliografiya → yakuniy muvofiqlik tekshiruvi |
| **1-xodim (PM gatekeeper)** | Har bir qoralamani RNU *Output Constraints Matrix* bo'yicha tekshiradi, avtomatik qayta ishlash so'raydi, qoidalar buzilgan ekan tasdiqlashni bloklaydi |
| **Lokal LLM** | Ollama yoki OpenAI-compatible server (LM Studio, llama.cpp, vLLM, Jan). Matnlar kompyuterdan chiqmaydi. LLMsiz sinash uchun demo model |
| **Haqiqiy manbalar** | OpenAlex / Semantic Scholar qidiruvi, Crossref orqali mustaqil tekshiruv (DOI + sarlavha mosligi), BibTeX import. Agentlar faqat tasdiqlangan `[@key]`larga iqtibos keltira oladi |
| **Haqiqiy tajriba** | CSV o'lchovlar → Welch t-test, Mann–Whitney U, Cohen d, 95% CI, grafik. 3-bobdagi har bir raqam o'lchovlardan bo'lishi shart |
| **Ishlaydigan kod isboti** | Loyiha papkasidagi kod fayllari va testlar sanaladi, deploy URL tekshiriladi — faqat maket bo'lsa bloklanadi |
| **Science Week formasi** | 01–05 bo'limlar: mualliflar (≤10, bitta mas'ul), sarlavha, annotatsiya (≤400 so'z), texnik bo'lim, kalit so'zlar, rasmiy DOCX shablon, 4–6 bet (LibreOffice bilan aniq o'lchash) |
| **Eksport** | Thesis/course work DOCX (titul, mundarija, jadvallar, grafik, APA/IEEE, AI-use ilova), maqola DOCX, topshirish varag'i, JSON zaxira |
| **Ikki haftalik hisobot** | Faqat haqiqiy faollik jurnalidan; uz / en / ru / lv |
| **Ko'p tillilik** | Interfeys: o'zbek, ingliz, rus, latish. Yozish tili: 15 ta til (en, lv, ru, uz, uk, lt, et, pl, de, fr, es, it, pt, tr, kk) |
| **Tarix** | Har bir qadam checkpoint sifatida saqlanadi; istalgan holatga qaytish mumkin |

## O'rnatish (Windows / macOS / Linux)

1. **Python 3.10+** o'rnating.
2. **Ollama** o'rnating (<https://ollama.com>) va model yuklang:
   ```bash
   ollama pull qwen2.5:14b-instruct      # 16 GB RAM uchun; kuchli kompyuterda qwen2.5:32b-instruct
   ```
3. Loyihani ishga tushiring:
   * Windows: `start.bat` ni ikki marta bosing
   * macOS / Linux: `./start.sh`

   Birinchi ishga tushirishda virtual muhit yaratiladi va kutubxonalar o'rnatiladi. Brauzerda **http://localhost:8765** ochiladi.
4. *(ixtiyoriy)* **LibreOffice** — Science Week maqolasining aniq bet sonini o'lchash uchun.

LLMsiz sinab ko'rish: `./start.sh --demo` (yoki `start.bat --demo`).

Docker bilan: `docker compose up -d`, so'ng `docker compose exec ollama ollama pull qwen2.5:14b-instruct`.

## Ishlash tartibi

1. **Yangi loyiha** → hujjat turi (kurs ishi / bitiruv ishi / Science Week maqolasi), yozish tili, mavzu.
2. **Loyiha va faktlar** → haqiqiy statistikani manbasi bilan kiriting (F1, F2 …). 1-bob faqat shulardan foydalanadi.
3. **Jarayon** → 2-xodimni ishga tushiring, qoralamani tahrirlang, *Tasdiqlash* yoki *Qayta ishlashni so'rash* (butun bosqich yoki bitta bo'lim).
4. **Manbalar** → 4-xodim OpenAlex'dan topadi; qo'lda qidirish, DOI yoki BibTeX ham mumkin. Keraksizlarini o'chirib qo'ying.
5. **Amaliy qism va ma'lumotlar** → loyiha papkasi / repo, ishga tushirish buyrug'i, o'lchovlar CSV'si (`metric,variant,value,run`).
6. **Science Week formasi** (maqola uchun) → mualliflar, bo'lim, kalit so'zlar, rasmiy shablonni yuklash, betlarni o'lchash.
7. **Eksport va hisobotlar** → DOCX, topshirish varag'i, ikki haftalik xat.

## RNU qoidalari

Barcha qoidalar `app/rules/rnu_rules.yaml` faylida: tezis prefikslari (har bir til uchun), gap chegaralari, bet maqsadlari,
Science Week cheklovlari, formatlash. Rasmiy *Common Mistakes Checklist* va *RNU Thesis Example* bo'yicha tahrirlang,
so'ng **Sozlamalar → RNU qoidalar faylini qayta yuklash**.

> Lokalizatsiya qilingan tezis prefikslari (lv, ru, uz …) taklif sifatida berilgan — rasmiy ifodani rahbaringiz bilan tasdiqlang.

## Testlar va benchmark

```bash
python -m pytest                          # 21 ta test: validatorlar, to'liq workflow, eksport, HTTP API
python scripts/benchmark_validators.py    # 1-xodim aniqligi (precision/recall/F1) va tezligi
python scripts/benchmark_citations.py --topic "..." --out citations.csv   # LLM vs pipeline: to'qilgan manbalar ulushi
```

## Tuzilma

```
app/
  orchestrator/   engine.py (checkpoint + interrupt), graph.py (8 xodim, PM gate), employees.py, prompts/*.md,
                  langgraph_adapter.py (ixtiyoriy LangGraph runtime)
  validators/     rules.py (RNU matritsasi), text.py (gap/so'z/statistika), messages.py (uz/en/ru/lv)
  references/     sources.py (OpenAlex, Crossref, S2, BibTeX), formatting.py (APA/IEEE), library.py
  experiments/    analysis.py (statistika, grafik)
  export/         docx_writer.py (thesis + paper), submission.py (Science Week varag'i)
  reports/        progress.py + templates/ (ikki haftalik xat)
  llm/            Ollama, OpenAI-compatible, demo
  web.py          HTTP API (Starlette)       services.py  ilova servis qatlami
static/           veb-portal (build'siz ES modules, offline ishlaydi)
docs/             ARCHITECTURE.md, COURSE_WORK.md
```

---

## English summary

RNU Thesis Copilot is a local, human-in-the-loop multi-agent assistant for RNU course works, theses and RNU Science Week
papers. Eight "employees" follow the RNU 3-Arrow Logic (Problem → Existing methods → Own practical method); Employee 1
audits every draft against the RNU Output Constraints Matrix and blocks approval while rules are broken (one-sentence
SMART aim, 3–4 fact-backed sentences, three Nails with the required prefixes and unchanged terms, chapter conclusions,
working code plus real measurements, zero unverified citations). It runs on Ollama or any OpenAI-compatible local server,
retrieves sources only from OpenAlex/Semantic Scholar/Crossref/BibTeX, computes statistics from the student's own CSV,
exports DOCX (thesis or the 4–6 page Science Week paper inside the official template) and writes the bi-weekly progress
e-mail from the real activity log. Start with `start.bat` / `./start.sh` (add `--demo` to try it without a model).
