# Faz 07 — Gerçekte yapılan kontroller

Bu teslim hazırlık/preflight altyapısıdır; gerçek GPU eğitimi yapılmadı. Drive'daki gerçek baseline args/etkin ayar/optimizer/run özeti/veri manifesti ile gerçek Faz 06 raporu ve val manifesti okundu. Belgelenen dosya hash'leri bu indirilen küçük metadata dosyalarından hesaplandı. Kaynak ZIP/model ağırlığı indirilmedi; gerçek CUDA bellek uygunluğu, gecikme veya yeni model performansı ölçülmedi. İlk pretrained ve ZIP hash'leri tarihsel kayıttan okunmuştur; Colab preflight gerçek dosyalar üzerinde yeniden doğrular.

Sentetik fixture'lar gerçek model sonucu değildir. Notebook 07 GPU preflight'ı testte mock edilir. Gelecekteki eğitim yürütücüsünün kesinti/snapshot/yeniden-yönlendirme yolları mock trainer ile sınanır; bu gerçek Ultralytics GPU resume testi değildir. Yeni PyYAML bağımlılığı gerçek `args.yaml` dosyasını `safe_load` ile okumak içindir; Colab'da zaten Ultralytics bağımlılığıdır.

## Çalıştırılan komutlar

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tests/validate_notebook.py
.venv/bin/python tests/validate_real_audit_notebook.py
.venv/bin/python tests/validate_wisard_notebook.py
.venv/bin/python tests/validate_training_notebook.py
.venv/bin/python tests/validate_wisard_external_notebook.py
.venv/bin/python tests/validate_phase06_notebook.py
.venv/bin/python tests/validate_phase07_notebook.py
.venv/bin/python -m compileall -q src tests
git diff --check
```

Notebook 01–06 mevcut sentetik senaryolarının tamamı geçti. Notebook 07 sentetik hazırlık (dört mock probe), GPU-yok ve eksik-baseline yolları geçti; eğitim kapısının kapalı olduğu ve hiç attempt/eğitim oluşturulmadığı doğrulandı. Hazırlık özeti/tabloları kaydedilen notebook çıktılarında mevcuttur; yeni performans grafiği veya gerçek GPU ölçümü yoktur.

Birim testleri gerçek ayar dosyalarının zorunluluğunu, auto→etkin AdamW/LR çözümünü, args farklarının reddini, başlangıç/manifest hash'lerini, kaynak train/val üyelik ve dışlamalarını, test JSON/görüntülerinin okunmamasını, kol başına tek-faktör ve ortak batch kontrolünü, değişmeyen adayın atlanmasını, bütün-kol bellek onayını, GPU/ortam sapmasını, GPU-yok durum kaydını, varsayılan kapalı eğitim kapısını, gerçek optimizer grup kontrolünü, tamamlanmış kopyalarda hash/sınıf/kol aidiyetini, immutable yeni attempt içinde mock resume'u, bitmiş eğitimde yalnız değerlendirmeye devamı ve eşzamanlı/stale lock reddini kapsar.

Son teslim test sayıları ve sabit Colab kod commit'i aşağıda kaydedilir.

- Tüm Python testleri: **144 geçti** (52.964 saniye); yeni Faz 07 alt kümesi **17 geçti**.
- Notebook 01–06 mevcut doğrulamaları: tamamı geçti. Notebook 04 eğitim çağrıları sentetik mock'tur.
- Notebook 07: sentetik hazırlık, GPU-yok ve eksik-baseline senaryoları geçti; son CODE_REF sabitlemesinden sonra tekrar geçti.
- `compileall src tests` ve `git diff --check`: geçti.

Bazı notebook kernel kapanışlarında ortamın Jupyter imza uyarıları çıktı; başarılı hücre/çıktı assert'leri ve süreç çıkış kodları kontrol edildi. Gerçek Colab OAuth, GPU bellek ölçümü, uzun eğitim, gerçek native/fixed yeni model metrikleri ve gerçek checkpoint ile resume çalıştırılmadı.

Notebook 07 CODE_REF, **78cc680e8e7fb87e4692e91ba73f71846dfd921d** yardımcı kod commit’ine sabitlendi. GitHub’dan ayrı temiz checkout ile bu commit alınarak 17 Faz 07 testi ayrıca geçti (0.796 saniye). Sabitleme takip commit’indedir; notebook kendi commit hash’ine döngüsel referans vermez.
