import asyncio
import json
import random
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from agent_manager import Agent, create_default_agents, detect_mentions, pick_random_agent
from llm_service import LLMService


BroadcastChatFn = Callable[[str, str, str], Awaitable[None]]
BroadcastSystemFn = Callable[[str], Awaitable[None]]
HasAudienceFn = Callable[[], bool]


# Global benzeri hafif durumlar: sohbet geçmişi ve ajan kadrosu
agents: List[Agent] = create_default_agents()
chat_history: List[Dict[str, Any]] = []
message_counter: int = 0
_history_lock = asyncio.Lock()

_llm: Optional[LLMService] = None
_broadcast_chat: Optional[BroadcastChatFn] = None
_broadcast_system: Optional[BroadcastSystemFn] = None
_has_audience: Optional[HasAudienceFn] = None


async def init_chat_logic(
    llm_service: LLMService,
    broadcast_chat: BroadcastChatFn,
    broadcast_system: BroadcastSystemFn,
    has_audience: HasAudienceFn,
) -> None:
    """
    Dış dünyadan (FastAPI main) gerekli bağımlılıkları alıp saklar,
    arka plan görevlerini başlatır.
    """

    global _llm, _broadcast_chat, _broadcast_system, _has_audience
    _llm = llm_service
    _broadcast_chat = broadcast_chat
    _broadcast_system = broadcast_system
    _has_audience = has_audience

    asyncio.create_task(_idle_agent_chatter_loop())


async def _append_history(sender: str, sender_type: str, content: str) -> int:
    """
    Mesajı sohbet geçmişine ekler ve toplam mesaj sayısını döndürür.
    """

    global message_counter
    async with _history_lock:
        chat_history.append(
            {
                "sender": sender,
                "sender_type": sender_type,
                "content": content,
            }
        )
        if len(chat_history) > 100:
            del chat_history[0 : len(chat_history) - 100]
        message_counter += 1
        return message_counter


async def register_system_message(content: str) -> None:
    """
    Sistem olaylarını hem geçmişe hem de istemcilere iletir.
    """

    await _append_history("Sistem", "system", content)
    if _broadcast_system:
        await _broadcast_system(content)


async def handle_human_message(username: str, content: str) -> None:
    """
    İnsan mesajı geldiğinde çağrılır.
    - Mesajı geçmişe ekler.
    - Ajan tetikleyicilerini çalıştırır.
    - Gerekirse mood analizini devreye sokar.
    """

    count = await _append_history(username, "human", content)

    # Ajan tetikleme mantığı
    asyncio.create_task(_agent_triggers_for_message(username, content))

    # Her ~7 mesajda bir mood analizi (5–10 arası orta yol)
    if count % 7 == 0:
        asyncio.create_task(_analyze_and_update_moods())


async def _agent_triggers_for_message(username: str, content: str) -> None:
    """
    .agentway'de tarif edilen tetikleyiciler:
    - Mention: adı geçen ajan mutlaka konuşur.
    - Rastgele katılım: her mesajdan sonra %20 ihtimalle bir ajan araya girer.
    - Zincirleme reaksiyon: Konuşan bir ajandan sonra başka bir ajan sinirlenip cevap verebilir.
    """

    if not _llm or not _broadcast_chat:
        return

    triggered: List[Agent] = []

    # 1) Mention (etiketleme)
    mentioned = detect_mentions(content, agents)
    triggered.extend(mentioned)

    # 2) Rastgele katılım
    if random.random() < 0.20:  # %20 ihtimal
        random_agent = pick_random_agent(agents, exclude=triggered)
        if random_agent:
            triggered.append(random_agent)

    # Aynı ajanı iki kez tetikleme
    unique_triggered = list(dict.fromkeys(triggered))

    tasks = []
    for agent in unique_triggered:
        tasks.append(
            _agent_reply_flow(
                agent,
                trigger_text=f"{username}: {content}",
                may_chain=True,
            )
        )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _agent_reply_flow(agent: Agent, trigger_text: str, may_chain: bool) -> None:
    """
    Tek bir ajanın:
    - Küçük bir gecikme ile cevap üretmesi
    - Cevabı yayınlaması
    - Gerekirse zincirleme reaksiyon başlatması
    """

    assert _llm is not None
    assert _broadcast_chat is not None

    await asyncio.sleep(random.uniform(1.5, 3.5))

    history_snapshot = await _get_history_snapshot(limit=20)
    history_text = "\n".join(
        f"{item['sender']} ({item['sender_type']}): {item['content']}"
        for item in history_snapshot
    ) or "Henüz çok fazla konuşma yok."

    user_prompt_parts = [
        "Sohbet odasındaki son konuşmalar aşağıda:",
        history_text,
        "",
        "Sen de bu sohbete kendi tarzında TEK bir mesajla katıl.",
        "Kısa, esprili ve karakterine uygun konuş. Aşırı teknik açıklamalar yapma.",
        "",
        "Az önce özellikle şu mesaj geldi, buna tepki verebilirsin:",
        trigger_text,
    ]
    user_prompt = "\n".join(user_prompt_parts)

    messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    reply = await _llm.generate(messages, temperature=0.9)
    if not reply:
        return

    reply = reply.strip()
    if len(reply) > 700:
        reply = reply[:700] + " ..."

    await _append_history(agent.display_name, "agent", reply)
    await _broadcast_chat(agent.display_name, "agent", reply)

    # Zincirleme reaksiyon: başka bir ajan "gaza gelebilir"
    if may_chain and random.random() < 0.35:
        other = pick_random_agent(agents, exclude=[agent])
        if other:
            asyncio.create_task(
                _agent_reply_flow(
                    other,
                    trigger_text=f"{agent.display_name} az önce şöyle dedi: {reply}",
                    may_chain=False,
                )
            )


async def _get_history_snapshot(limit: int) -> List[Dict[str, Any]]:
    async with _history_lock:
        return list(chat_history[-limit:])


async def _analyze_and_update_moods() -> None:
    """
    Sohbet geçmişini küçük bir prompt ile LLM'e verip
    ajanların mood'unu günceller. Değişiklik olursa sistem mesajı üretir.
    """

    if not _llm or not _broadcast_system:
        return

    history_snapshot = await _get_history_snapshot(limit=40)
    if not history_snapshot:
        return

    summary_text = "\n".join(
        f"{item['sender']} ({item['sender_type']}): {item['content']}"
        for item in history_snapshot
    )

    system_prompt = (
        "Görevin: Aşağıdaki sohbet geçmişine göre üç ajanın güncel RUH HALİNİ analiz etmek.\n"
        "Ajanlar: 'Kılkuyruk', 'Karamsar', 'Şapşal'.\n"
        "Çıktıyı AŞAĞIDAKİ JSON formatında ver (ek açıklama yazma):\n"
        '{\n'
        '  "Kılkuyruk": {"mood": "...", "notes": "..."},\n'
        '  "Karamsar": {"mood": "...", "notes": "..."},\n'
        '  "Şapşal": {"mood": "...", "notes": "..." }\n'
        "}\n"
        "Mood kısa ve Türkçe olsun (örn: 'çok sinirli', 'utangaç ve çekingen', 'dibe vurmuş').\n"
        "Notes alanında 1 cümle ile bu moda neden geldiğini açıkla."
    )

    user_prompt = (
        "İşte son sohbet geçmişi. Buna göre ajanların ruh halini güncelle:\n\n"
        f"{summary_text}"
    )

    raw = await _llm.generate(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )
    if not raw:
        return

    try:
        mood_data = json.loads(raw)
    except json.JSONDecodeError:
        return

    for agent in agents:
        agent_block = mood_data.get(agent.display_name)
        if not isinstance(agent_block, dict):
            continue

        new_mood = str(agent_block.get("mood") or "").strip()
        new_notes = str(agent_block.get("notes") or "").strip()
        if not new_mood:
            continue

        previous = agent.set_mood(new_mood, new_notes)
        if previous["mood"] != agent.current_mood:
            # Mood değişmiş, tüm odaya dramatik bir sistem mesajı atalım
            human_readable = (
                f"[SİSTEM] {agent.display_name} şu an kendini "
                f"'{agent.current_mood}' hissediyor. {agent.mood_notes or ''}"
            )
            await register_system_message(human_readable)


async def _idle_agent_chatter_loop() -> None:
    """
    Oda çok sessiz kaldığında ajanların canı sıkılmasın diye
    ara sıra kendi başlarına konuşmalarını sağlar.
    """

    while True:
        await asyncio.sleep(random.uniform(20.0, 40.0))
        if not _llm or not _broadcast_chat or not _has_audience:
            continue
        if not _has_audience():
            continue

        speaker = random.choice(agents)
        history_snapshot = await _get_history_snapshot(limit=15)
        history_text = "\n".join(
            f"{item['sender']} ({item['sender_type']}): {item['content']}"
            for item in history_snapshot
        ) or "Henüz kimse pek bir şey söylemedi."

        user_prompt = (
            "Oda biraz sessiz kaldı. Aşağıdaki sohbet geçmişine bak ve "
            "tamamen kendi içinden geliyormuş gibi tek bir mesaj yaz.\n\n"
            f"{history_text}"
        )

        messages = [
            {"role": "system", "content": speaker.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        reply = await _llm.generate(messages, temperature=0.9)
        if not reply:
            continue

        reply = reply.strip()
        if len(reply) > 700:
            reply = reply[:700] + " ..."

        await _append_history(speaker.display_name, "agent", reply)
        await _broadcast_chat(speaker.display_name, "agent", reply)

