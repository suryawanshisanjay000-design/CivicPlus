import json
import os

from groq import Groq

from models import DepartmentCode, Priority, TriageResult

GROQ_SYSTEM_PROMPT = """You are a civic issue triage system. Analyze the complaint and return ONLY valid JSON with these exact fields:
{
  "department": "ROADS|WATER|SOLID_WASTE|ELECTRICAL|PUBLIC_HEALTH",
  "subcategory": "string",
  "priority": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "one-line summary",
  "urgency_score": 1-10
}

Rules:
- ROADS: potholes, road damage, drain, footpath, street
- WATER: leaks, pipes, sewer, flood, water supply
- SOLID_WASTE: garbage, trash, waste, dump, litter
- ELECTRICAL: lights, poles, wires, power, streetlight
- PUBLIC_HEALTH: mosquito, health, clinic, animal, sanitation, disease

Priority by urgency_score: 1-3=LOW, 4-6=MEDIUM, 7-8=HIGH, 9-10=CRITICAL"""


FALLBACK_KEYWORDS = {
    DepartmentCode.ROADS: (["pothole", "road", "street", "drain", "footpath", "crater", "asphalt"], Priority.HIGH),
    DepartmentCode.WATER: (["water", "leak", "pipe", "sewer", "flood", "sewage", "drainage"], Priority.HIGH),
    DepartmentCode.SOLID_WASTE: (["garbage", "trash", "waste", "dump", "litter", "rubbish"], Priority.MEDIUM),
    DepartmentCode.ELECTRICAL: (["light", "electric", "wire", "pole", "power", "streetlight", "lamp"], Priority.URGENT),
    DepartmentCode.PUBLIC_HEALTH: (["mosquito", "health", "clinic", "animal", "sanitation", "disease", "hygiene"], Priority.HIGH),
}


def fallback_triage(description: str, category: str) -> TriageResult:
    text = f"{description} {category}".lower()
    
    for dept, (keywords, priority) in FALLBACK_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            subcategory = category if category != "General" else dept.value
            return TriageResult(
                department=dept,
                subcategory=subcategory,
                priority=priority,
                summary=f"{dept.value} issue: {description[:100]}",
                urgency_score=7 if priority in [Priority.HIGH, Priority.URGENT] else 5
            )
    
    return TriageResult(
        department=DepartmentCode.ROADS,
        subcategory=category if category != "General" else "OTHER",
        priority=Priority.MEDIUM,
        summary=f"General issue: {description[:100]}",
        urgency_score=5
    )


async def groq_triage(description: str, category: str) -> TriageResult:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback_triage(description, category)
    
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": f"Description: {description}\nCategory: {category}"}
            ],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(completion.choices[0].message.content or "{}")
        
        # Validate enums
        department = DepartmentCode(result.get("department", "ROADS"))
        priority = Priority(result.get("priority", "MEDIUM"))
        
        return TriageResult(
            department=department,
            subcategory=result.get("subcategory", category),
            priority=priority,
            summary=result.get("summary", description[:100]),
            urgency_score=result.get("urgency_score", 5)
        )
    except Exception:
        return fallback_triage(description, category)