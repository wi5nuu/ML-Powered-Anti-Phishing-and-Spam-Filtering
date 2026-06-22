# AI Usage Disclosure

Proyek ini dikembangkan dengan bantuan AI dalam kapasitas berikut:

| Komponen | Alat AI | Peran AI |
|---|---|---|
| Perencanaan arsitektur | Claude Sonnet / opencode | Brainstorming pipeline, review trade-off desain |
| Scaffolding kode awal | Claude Sonnet / opencode | Draft awal `features.py`, `fusion.py`, `predict.py`, `pipeline_worker.py` |
| Dokumentasi | Claude Sonnet / opencode | Draft user manual, admin manual, inline docstring |
| Training & evaluasi | Manual developer | Tuning hyperparameter, interpretasi hasil SHAP |
| Testing | Manual developer + AI | Pembuatan fixture, adversarial test cases, struktur test |
| Debugging & perbaikan bug | opencode | Diagnostics label indexing, SHAP fallback, port conflicts, IMAP→POP3 migration |

Semua kode AI-generated telah diverifikasi, dimodifikasi, dan dipahami
oleh developer sebelum digunakan. Tidak ada kode yang dimasukkan tanpa
review dan pengujian manual.
