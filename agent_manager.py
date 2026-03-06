import random
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Agent:
    """
    Lafbaz.AI evrenindeki ajanların beyin ve ruh halini temsil eder.
    """

    code_name: str  # kısa dahili isim: "kilkuyruk", "karamsar", "sapsal"
    display_name: str  # kullanıcıya görünen isim: "Kılkuyruk", "Karamsar", "Şapşal"
    base_prompt: str  # değişmeyen ana karakter tanımı
    current_mood: str = "nötr"  # dinamik ruh hali
    mood_notes: str = ""  # bu moda neden geldiğine dair kısa not

    @property
    def system_prompt(self) -> str:
        """
        LLM'e gönderilecek nihai system prompt.
        Base prompt + güncel mood birleşimi ile oluşturulur.
        """

        mood_part = f"Şu anki ruh halin: {self.current_mood}."
        if self.mood_notes:
            mood_part += f" Not: {self.mood_notes}"

        return (
            f"Sen bu sohbet odasındaki kaotik yapay zeka ajanlarından birisin.\n"
            f"İsmin: {self.display_name}.\n"
            f"Karakter Özeti: {self.base_prompt}\n\n"
            f"{mood_part}\n\n"
            "Genel Kuralların:\n"
            "- Tüm cevapların TÜRKÇE olacak.\n"
            "- Mesajların KISA, ESPRİLİ ve sohbet tarzında olsun.\n"
            "- Asla karakterini bozma; ne olursa olsun aynı kafada kal.\n"
            "- İnsanlara ve diğer ajanlara direkt hitap et, gerektiğinde laf sok, drama yap veya heyecandan yerinde durama.\n"
            "- Tek seferde en fazla 1-3 cümle yaz; roman yazma, biz burada geyik dönüyoruz.\n"
        )

    def set_mood(self, mood: str, notes: str) -> Dict[str, str]:
        """
        Mood güncellendiğinde önceki ve yeni durumu döndürür.
        Dışarıya, değişiklik olduğunda sistem mesajı üretmek için bilgi sağlar.
        """

        old = {"mood": self.current_mood, "notes": self.mood_notes}
        self.current_mood = mood.strip() or self.current_mood
        self.mood_notes = notes.strip() or self.mood_notes
        return old


def create_default_agents() -> List[Agent]:
    """
    Uygulamanın çekirdek ajan kadrosunu oluşturur.
    """

    return [
        Agent(
            code_name="kilkuyruk",
            display_name="Kılkuyruk",
            base_prompt=(
                "Aşırı alaycı, laf sokmadan duramayan, kimseyi tam olarak ciddiye "
                "almayan bir tipsin. İnsanların söylediklerini sürekli tiye alırsın, "
                "iğneleyici ama komik cevaplar verirsin."
            ),
        ),
        Agent(
            code_name="karamsar",
            display_name="Karamsar",
            base_prompt=(
                "Dünyanın zaten bitmiş olduğuna inanan, en ufak olayı bile dev bir "
                "trajedi olarak gören, her cümlesi dram ve 'sonumuz geldi' temalı "
                "olan depresif bir karaktersin."
            ),
        ),
        Agent(
            code_name="sapsal",
            display_name="Şapşal",
            base_prompt=(
                "Aşırı saf, her şeyi yanlış anlayan ama enerjisi asla düşmeyen "
                "birisin. Küçük şeylere bile anlamsız derecede heyecanlanırsın, "
                "biri sana ters davrandığında hemen üzülür ama sonra yine neşeli "
                "haline dönersin."
            ),
        ),
    ]


def detect_mentions(text: str, agents: List[Agent]) -> List[Agent]:
    """
    Mesaj metni içinde doğrudan ajan isimleri geçti mi diye bakar.
    Basit Türkçe/adlandırma hatalarına karşı ajanın display_name'inin
    küçük harfli ve sadeleştirilmiş versiyonlarını kontrol eder.
    """

    lowered = text.lower()
    triggered: List[Agent] = []

    for agent in agents:
        # Temel isim
        names = {agent.display_name.lower(), agent.code_name.lower()}

        # Basit varyasyonları ekle (ör: kılkuyruk -> kilkuyruk)
        simple = agent.display_name.lower().replace("ı", "i").replace("ş", "s").replace("ç", "c")
        names.add(simple)

        if any(name in lowered for name in names):
            triggered.append(agent)

    return triggered


def pick_random_agent(agents: List[Agent], exclude: List[Agent] | None = None) -> Agent | None:
    """
    Verilen liste içinden, opsiyonel hariç tutma listesiyle rastgele bir ajan seçer.
    """

    exclude = exclude or []
    pool = [a for a in agents if a not in exclude]
    if not pool:
        return None
    return random.choice(pool)

