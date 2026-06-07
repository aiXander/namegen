"""Timing probe: is the OpenRouter embeddings endpoint actually batching?

Sends fresh (cache-busting) random texts in batch sizes 1, 10, 100 and times
each request. If a 100-input request takes ~100x a 1-input request, the
provider is processing inputs serially and client-side batching buys nothing.
"""

import asyncio
import random
import string
import time

from ai.llm import make_async_openrouter_client
from ai.embeddings import DEFAULT_EMBEDDING_MODEL


def random_word() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=8))


async def main():
    client = make_async_openrouter_client()
    try:
        for n in (1, 10, 100):
            texts = [random_word() for _ in range(n)]
            t0 = time.perf_counter()
            response = await client.embeddings.create(
                model=DEFAULT_EMBEDDING_MODEL, input=texts, encoding_format="float"
            )
            dt = time.perf_counter() - t0
            print(f"batch={n:4d}  {dt:6.2f}s  ({dt / n * 1000:7.1f} ms/text)  "
                  f"vectors={len(response.data)}  dim={len(response.data[0].embedding)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
