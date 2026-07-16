import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import Database
from app.models.entities import AITool, Prompt

TOOLS = [
    ("chatgpt", "ChatGPT", "General AI", "General-purpose conversational AI assistant.", "https://chatgpt.com", "Freemium", True),
    ("claude", "Claude", "General AI", "Assistant for writing, analysis, and coding.", "https://claude.ai", "Freemium", True),
    ("perplexity", "Perplexity", "Research", "AI answer engine with cited web research.", "https://www.perplexity.ai", "Freemium", True),
    ("github-copilot", "GitHub Copilot", "Coding", "AI pair programmer for development workflows.", "https://github.com/features/copilot", "Paid", True),
    ("cursor", "Cursor", "Coding", "AI-first code editor for repository-aware development.", "https://www.cursor.com", "Freemium", False),
    ("midjourney", "Midjourney", "Images", "Generative image creation platform.", "https://www.midjourney.com", "Paid", True),
    ("canva-magic", "Canva Magic Studio", "Design", "AI-assisted content and visual design tools.", "https://www.canva.com/magic-studio/", "Freemium", False),
    ("notion-ai", "Notion AI", "Productivity", "AI writing and knowledge features inside Notion.", "https://www.notion.so/product/ai", "Paid", False),
]

PROMPTS = [
    ("strategy-brief", "Business Strategy Brief", "Business", "Turn a goal into a concise strategy.", "Act as a strategy consultant. Analyze [business], [market], [goal], and [constraints]. Produce: situation, three strategic options, trade-offs, recommended direction, 90-day plan, KPIs, and key risks.", False, True),
    ("customer-persona", "Evidence-Based Customer Persona", "Marketing", "Build an actionable persona without inventing evidence.", "Using only the evidence below, create a customer persona with jobs-to-be-done, pains, desired outcomes, objections, buying triggers, channels, and messaging angles. Mark every unsupported assumption clearly. Evidence: [paste research].", False, True),
    ("content-calendar", "30-Day Content Calendar", "Marketing", "Plan channel-specific content around one objective.", "Create a 30-day content calendar for [brand] targeting [audience] on [channels]. Goal: [goal]. Include daily topic, hook, format, CTA, production effort, and success metric. Avoid repeating angles.", False, False),
    ("code-review", "Production Code Review", "Coding", "Review code for correctness, security, and operations.", "Review the following code as a senior production engineer. Identify correctness bugs, security risks, concurrency issues, performance bottlenecks, observability gaps, and missing tests. Rank findings by severity and provide precise patches. Code: [paste code].", False, True),
    ("meeting-decisions", "Meeting Decision Log", "Productivity", "Extract decisions and ownership from raw notes.", "Convert these meeting notes into: executive summary, decisions made, open questions, action items with owner and due date, risks, and topics deferred. Do not infer owners or dates that are absent. Notes: [paste notes].", False, False),
    ("board-memo", "Board-Ready Operating Memo", "Business", "Create an executive operating update.", "Write a board-ready operating memo from [data]. Include executive summary, KPI movement, drivers, misses, corrective actions, capital implications, risks, asks, and next-quarter commitments. Be concise and distinguish facts from interpretation.", True, True),
    ("research-synthesis", "Deep Research Synthesis", "Research", "Synthesize multiple sources with confidence labels.", "Synthesize the sources below into findings, areas of agreement, contradictions, methodology limits, and unanswered questions. Attach a confidence label to every major conclusion and cite the source identifier. Sources: [paste sources].", True, True),
]


async def seed() -> None:
    database = Database(get_settings())
    async with database.sessions() as session:
        for slug, name, category, description, url, pricing, featured in TOOLS:
            if not await session.scalar(select(AITool.id).where(AITool.slug == slug)):
                session.add(AITool(slug=slug, name=name, category=category, description=description, url=url, pricing=pricing, is_featured=featured))
        for slug, title, category, description, content, premium, featured in PROMPTS:
            if not await session.scalar(select(Prompt.id).where(Prompt.slug == slug)):
                session.add(Prompt(slug=slug, title=title, category=category, description=description, content=content, is_premium=premium, is_featured=featured))
        await session.commit()
    await database.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
