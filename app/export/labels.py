"""Localized headings for the exported documents."""
from __future__ import annotations

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "course_work": "COURSE WORK", "thesis": "BACHELOR THESIS", "conference_paper": "PAPER",
        "author": "Author", "supervisor": "Supervisor", "contents": "CONTENTS", "abstract": "ABSTRACT",
        "keywords": "Keywords", "ch1": "INTRODUCTION AND PROBLEM FORMULATION", "topicality": "Topicality",
        "problem": "Problem formulation", "object_subject": "Research object and subject", "object": "Object",
        "subject": "Subject", "aim_tasks": "Research aim and tasks", "aim": "Aim", "tasks": "Tasks",
        "nails": "Defended thesis statements", "rq": "Research questions", "methods": "Research methods",
        "planned": "Planned results", "result": "Result", "metric": "Metric", "beneficiary": "Beneficiary",
        "novelty": "Novelty and practical significance", "structure": "Structure of the work",
        "ch_conclusion": "Chapter conclusion", "ch2": "LITERATURE REVIEW AND THEORETICAL FRAMEWORK",
        "comparison": "Comparison of existing methods", "approach": "Approach", "sources": "Sources",
        "strengths": "Strengths", "limitations": "Limitations", "gaps": "Identified research gaps",
        "lit_summary": "Summary of the literature review", "concepts": "Foundational concepts", "term": "Term",
        "definition": "Definition", "frameworks": "Theoretical and engineering frameworks",
        "gap_solution": "From gaps to the proposed solution", "gap": "Gap", "solution": "Solution element",
        "ch3": "PRACTICAL IMPLEMENTATION AND EMPIRICAL ANALYSIS", "architecture": "System architecture",
        "components": "System components", "component": "Component", "responsibility": "Responsibility",
        "technology": "Technology", "data_flow": "Data flow", "deployment": "Reproducible deployment",
        "experiment": "Experiment design", "results": "Results", "discussion": "Discussion of results",
        "metric_col": "Metric", "baseline": "Baseline", "proposed": "Proposed", "change": "Change",
        "p_value": "Welch p", "effect": "Cohen's d", "figure_results": "Measured results (mean ± 95% CI)",
        "general_conclusion": "GENERAL CONCLUSION", "future": "Future work", "lim": "Limitations",
        "references": "REFERENCES", "appendix_ai": "APPENDIX A. AI-USE DISCLOSURE AND AUTHORSHIP LOG",
        "appendix_impl": "APPENDIX B. IMPLEMENTATION EVIDENCE", "stage": "Stage", "ai_words": "AI draft words",
        "final_words": "Final words", "changed": "Changed by the student", "intro": "Introduction",
        "related": "Related work", "method": "Method and implementation", "results_sec": "Results and discussion",
        "conclusions": "Conclusions", "corresponding": "Corresponding author", "table": "Table", "figure": "Figure",
        "repo": "Repository", "local": "Local path", "run": "Run command", "deployed": "Deployed URL",
        "evidence": "Evidence",
        "ai_text": ("Draft text of this work was prepared with the help of RNU Thesis Copilot, a locally run "
                    "multi-agent assistant (model: {model}). Every stage was reviewed, edited and approved by the "
                    "author; all references were retrieved from OpenAlex/Crossref and verified; all numerical results "
                    "come from the author's own measurements. The table shows how much of each AI draft the author "
                    "changed."),
    },
    "lv": {
        "course_work": "KURSA DARBS", "thesis": "BAKALAURA DARBS", "author": "Autors", "supervisor": "Darba vadītājs",
        "contents": "SATURS", "abstract": "ANOTĀCIJA", "keywords": "Atslēgvārdi",
        "ch1": "IEVADS UN PROBLĒMAS FORMULĒJUMS", "topicality": "Aktualitāte", "problem": "Problēmas formulējums",
        "object_subject": "Pētījuma objekts un priekšmets", "object": "Objekts", "subject": "Priekšmets",
        "aim_tasks": "Pētījuma mērķis un uzdevumi", "aim": "Mērķis", "tasks": "Uzdevumi",
        "nails": "Aizstāvamās tēzes", "rq": "Pētījuma jautājumi", "methods": "Pētījuma metodes",
        "planned": "Plānotie rezultāti", "novelty": "Novitāte un praktiskā nozīme", "structure": "Darba struktūra",
        "ch_conclusion": "Nodaļas secinājumi", "ch2": "LITERATŪRAS APSKATS UN TEORĒTISKAIS IETVARS",
        "comparison": "Esošo metožu salīdzinājums", "gaps": "Identificētie trūkumi", "concepts": "Pamatjēdzieni",
        "frameworks": "Teorētiskie un inženiertehniskie ietvari", "gap_solution": "No trūkumiem līdz risinājumam",
        "ch3": "PRAKTISKĀ REALIZĀCIJA UN EMPĪRISKĀ ANALĪZE", "architecture": "Sistēmas arhitektūra",
        "components": "Sistēmas komponentes", "data_flow": "Datu plūsma", "deployment": "Atkārtojama izvietošana",
        "experiment": "Eksperimenta plāns", "results": "Rezultāti", "discussion": "Rezultātu analīze",
        "general_conclusion": "VISPĀRĪGIE SECINĀJUMI", "future": "Turpmākais darbs", "lim": "Ierobežojumi",
        "references": "IZMANTOTĀ LITERATŪRA", "lit_summary": "Literatūras apskata kopsavilkums",
    },
    "ru": {
        "course_work": "КУРСОВАЯ РАБОТА", "thesis": "БАКАЛАВРСКАЯ РАБОТА", "author": "Автор",
        "supervisor": "Научный руководитель", "contents": "СОДЕРЖАНИЕ", "abstract": "АННОТАЦИЯ",
        "keywords": "Ключевые слова", "ch1": "ВВЕДЕНИЕ И ПОСТАНОВКА ПРОБЛЕМЫ", "topicality": "Актуальность",
        "problem": "Постановка проблемы", "object_subject": "Объект и предмет исследования", "object": "Объект",
        "subject": "Предмет", "aim_tasks": "Цель и задачи исследования", "aim": "Цель", "tasks": "Задачи",
        "nails": "Положения, выносимые на защиту", "rq": "Исследовательские вопросы", "methods": "Методы исследования",
        "planned": "Планируемые результаты", "novelty": "Новизна и практическая значимость",
        "structure": "Структура работы", "ch_conclusion": "Выводы по главе",
        "ch2": "ОБЗОР ЛИТЕРАТУРЫ И ТЕОРЕТИЧЕСКАЯ ОСНОВА", "comparison": "Сравнение существующих методов",
        "gaps": "Выявленные пробелы", "concepts": "Базовые понятия", "frameworks": "Теоретические и инженерные модели",
        "gap_solution": "От пробелов к предлагаемому решению", "ch3": "ПРАКТИЧЕСКАЯ РЕАЛИЗАЦИЯ И ЭМПИРИЧЕСКИЙ АНАЛИЗ",
        "architecture": "Архитектура системы", "components": "Компоненты системы", "data_flow": "Поток данных",
        "deployment": "Воспроизводимое развертывание", "experiment": "Дизайн эксперимента", "results": "Результаты",
        "discussion": "Обсуждение результатов", "general_conclusion": "ЗАКЛЮЧЕНИЕ", "future": "Дальнейшая работа",
        "lim": "Ограничения", "references": "СПИСОК ЛИТЕРАТУРЫ", "lit_summary": "Итоги обзора литературы",
    },
    "uz": {
        "course_work": "KURS ISHI", "thesis": "BITIRUV MALAKAVIY ISHI", "author": "Muallif",
        "supervisor": "Ilmiy rahbar", "contents": "MUNDARIJA", "abstract": "ANNOTATSIYA", "keywords": "Kalit so'zlar",
        "ch1": "KIRISH VA MUAMMONING QO'YILISHI", "topicality": "Mavzuning dolzarbligi", "problem": "Muammoning qo'yilishi",
        "object_subject": "Tadqiqot obyekti va predmeti", "object": "Obyekt", "subject": "Predmet",
        "aim_tasks": "Tadqiqot maqsadi va vazifalari", "aim": "Maqsad", "tasks": "Vazifalar",
        "nails": "Himoyaga olib chiqiladigan tezislar", "rq": "Tadqiqot savollari", "methods": "Tadqiqot usullari",
        "planned": "Kutilayotgan natijalar", "novelty": "Ilmiy yangilik va amaliy ahamiyat",
        "structure": "Ishning tuzilishi", "ch_conclusion": "Bob bo'yicha xulosa",
        "ch2": "ADABIYOTLAR SHARHI VA NAZARIY ASOS", "comparison": "Mavjud usullarni taqqoslash",
        "gaps": "Aniqlangan bo'shliqlar", "concepts": "Asosiy tushunchalar", "frameworks": "Nazariy va muhandislik asoslari",
        "gap_solution": "Bo'shliqlardan taklif etilgan yechimga", "ch3": "AMALIY QISM VA EMPIRIK TAHLIL",
        "architecture": "Tizim arxitekturasi", "components": "Tizim komponentlari", "data_flow": "Ma'lumotlar oqimi",
        "deployment": "Qayta takrorlanadigan o'rnatish", "experiment": "Tajriba dizayni", "results": "Natijalar",
        "discussion": "Natijalar muhokamasi", "general_conclusion": "UMUMIY XULOSA", "future": "Keyingi ishlar",
        "lim": "Cheklovlar", "references": "FOYDALANILGAN ADABIYOTLAR", "lit_summary": "Adabiyotlar sharhi xulosasi",
    },
}


def labels(lang: str) -> dict[str, str]:
    base = dict(LABELS["en"])
    base.update(LABELS.get(lang, {}))
    return base
