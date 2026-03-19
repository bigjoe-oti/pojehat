import asyncio

from src.domain.rag_engine import query_mechanic_agent


async def verify_v6():
    queries = [
        ("What are the torque specifications for a Ford Focus Diesel 2005-2009 according to Haynes?", "Ford Focus Diesel 2005"),
        ("Explain the Flespi Spireon CAN DTC schema structure.", "General Protocol Analysis"),
        ("What are the relay locations for a Toyota Corolla E210?", "Toyota Corolla E210"),
        ("List the features of the Nissan Sunny B17 Egyptian market version.", "Nissan Sunny B17 Egypt")
    ]
    
    for q_text, ctx in queries:
        print(f"\n[QUERY]: {q_text}")
        response = await query_mechanic_agent(q_text, car_context=ctx)
        print(f"[RESPONSE]:\n{response}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(verify_v6())
