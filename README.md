# <img src="assets/logo_1.png" width="500" align="center">
## Geveze - Yerel Ağı Karıştıran Sohbet ve Ajanlar

Eğlenceli, biraz kaotik bir sohbet uygulaması. Aynı odada:

- Gerçek insanlar
- 3 adet Ollama tabanlı yapay zeka ajanı

hep birlikte kavga ediyor, drama çıkarıyor ve arada mantıklı şeyler de söylüyor.

### Özellikler

- **Yerel ağ (LAN) desteği**: `0.0.0.0` üzerinden yayın, aynı WiFi'daki cihazlar IP + port ile bağlanabilir.
- **WebSocket tabanlı canlı sohbet**: Gecikmesi düşük, gerçek zamanlı iletişim.
- **3 kalıcı LLM ajanı**:
  - **Alaycı Ajan**: Her şeye laf sokar, kimseyi ciddiye almaz.
  - **Dramatik Ajan**: En küçük olayı bile kıyamet gibi anlatır.
  - **Saf Ajan**: Saf, şapşal ama aşırı heyecanlı.
- **Ajan–insan ve ajan–ajan etkileşimi**:
  - İnsan mesajları ajanları tetikler.
  - Ajanlar rastgele aralıklarla kendi kendilerine de sohbete dahil olur.
- **Dinamik karakter evrimi**:
  - Sohbet geçmişi yaklaşık her 10 mesajda bir analiz edilir.
  - Ajanların “ruh hali (mood)” ve kısa açıklamaları LLM ile güncellenir.
  - Ajanların system prompt’ları bu yeni mood’a göre şekillenir.

---

### Kurulum (Geliştirme Ortamı)

#### 1. Bağımlılıkları yükle

Python 3.10+ önerilir.

```bash
cd geveze
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Ollama'yı hazırlama

- Ollama'yı kur ve çalıştır.
- Uygulama varsayılan olarak şu ayarları kullanır:
  - `OLLAMA_BASE_URL`: `http://localhost:11434`
  - `OLLAMA_MODEL`: `llama3.1`

İstersen farklı bir model kullanmak için ortam değişkeni ayarlayabilirsin:

```bash
export OLLAMA_MODEL=llama3
export OLLAMA_BASE_URL=http://localhost:11434
```

#### 3. Uygulamayı çalıştır

```bash
uvicorn main:app --host 0.0.0.0 --port 7800 --reload
```

- Tarayıcıdan bağlan: `http://127.0.0.1:7800`
- Aynı yerel ağdaki başka bir cihazdan: `http://<bilgisayar_IP_adresi>:7800`

---

### Kullanım

1. Tarayıcıda uygulamayı aç.
2. Kendine komik bir kullanıcı adı seç ve “Odaya Gir” butonuna bas.
3. Mesaj yaz ve Enter’a bas.
4. Bir süre sonra:
   - Alaycı Ajan sana laf sokmaya başlayacak.
   - Dramatik Ajan her şeyi felaket gibi anlatacak.
   - Saf Ajan her şeye gereksiz derecede heyecanlanacak veya trip atacak.

Ajanlar:

- Yeni mesajlarınıza tepki veriyor.
- Arka planda, rastgele aralıklarla kendi aralarında da sohbete giriyor.
- Sohbetin gidişatına göre ruh halleri (mood) değişiyor.

---

### Mimari Özeti

- **Backend**: `FastAPI` + `WebSocket`
  - `/` route'u `templates/index.html` sayfasını döner.
  - `/ws` WebSocket endpoint’i:
    - İlk gelen mesaj `type: "join"` ile kullanıcı adı bilgisini alır.
    - Sonraki mesajlar `type: "chat"` ile sohbet içeriğini taşır.
    - Mesajları tüm bağlı kullanıcılara JSON formatında yayınlar:
      - `{"type": "chat", "sender": "...", "sender_type": "human" | "agent", "content": "..."}`.
- **LLM Entegrasyonu (Ollama)**:
  - `main.py` içindeki `call_ollama` fonksiyonu `/api/chat` endpoint’ine asenkron istek atar.
  - Her ajan için ayrı bir `system_prompt` üretilir.
  - `analyze_agent_moods` fonksiyonu, sohbet geçmişini küçük bir LLM çağrısıyla analiz edip ajanların mood’unu JSON formatında günceller.
- **Frontend**: `templates/index.html`
  - TailwindCSS CDN kullanır (ayrı build yok, KISS).
  - Tek sayfa içinde:
    - Mesaj listesi
    - Kullanıcı adı alanı
    - Mesaj yazma alanı
  - WebSocket ile JSON mesaj alışverişi yapar.

---

### Docker ile Çalıştırma

> Not: Docker kullanırken, Ollama'nın host makinede çalıştığından emin ol.

#### 1. Docker imajını oluştur

```bash
docker compose build
```

#### 2. Uygulamayı başlat

```bash
docker compose up
```

Varsayılan olarak:

- Uygulama: `http://localhost:7800`
- Çevredeki cihazlar, host IP adresini kullanarak bağlanabilir (örn: `http://192.168.1.42:7800`).

#### Ollama bağlantısı (Docker içinde)

- `docker-compose.yml` dosyasında varsayılan olarak:

  - `OLLAMA_BASE_URL=http://host.docker.internal:11434`

- Bu ayar:
  - macOS/Windows'ta doğrudan host’taki Ollama’ya erişmek için uygundur.
  - Linux’ta çalışmıyorsa, kendi ortamına göre `OLLAMA_BASE_URL` değerini güncellemen gerekebilir.

---

### Güvenlik ve Notlar

- Bu proje yerel ağ eğlencesi içindir, production güvenliği için sertleştirme yapılmamıştır.
- Kullanıcı girdileri backend tarafında sadece sohbet mesajı olarak kullanılır, komut olarak çalıştırılmaz.
- Herhangi bir kimlik doğrulama yoktur; aynı odaya herkes girebilir.

---

### Ajanların Kısa Hikâyesi

- **Alaycı Ajan**:
  - Zekâ seviyesi yüksek, sabır seviyesi düşük.
  - “Yeni girdin diye sana saygı göstereceğim sanıyorsan yanılıyorsun.” seviyesinde ukala.
- **Dramatik Ajan**:
  - Küçük bir latency bile yaşansa “evren çöküyor” moduna geçer.
  - En sevdiği kelimeler: “yıkım”, “çöküş”, “felaket”.
- **Saf Ajan**:
  - Birine terslenince:
    - Önce şaşırır.
    - Sonra üzülür.
    - Sonra yine neşelenir.
  - Aşırı heyecanlı sorular sorar, bazen konuyu tamamen yanlış anlar.

Kısaca: Uygulamayı aç, adı “Geveze” ama asıl gevezelik ajanlarda. Sen arada kaynarsın.

