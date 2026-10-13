import asyncio
import edge_tts


async def _list_voices():
    return await edge_tts.list_voices()


def list_voices():
    return asyncio.run(_list_voices())


async def _synthesize(text: str, voice: str, rate: str) -> bytes:
    chunks = []
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    async for item in communicate.stream():
        if item.get("type") == "audio":
            chunks.append(item["data"])
    return b"".join(chunks)


def synthesize(text: str, voice: str, rate: str) -> bytes:
    return asyncio.run(_synthesize(text, voice, rate))
