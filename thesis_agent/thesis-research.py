import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool

# 1. Set up your environment keys
# (Replace with your actual keys. Serper.dev provides 2,500 free search API tokens)
os.environ["OPENAI_API_KEY"] = "your-chatgpt-or-perplexity-key"
os.environ["SERPER_API_KEY"] = "your-serper-dev-search-key"

# Initialize the automated web search engine tool
search_tool = SerperDevTool()

# ==========================================
# 2. DEFINE THE AGENTS (The Virtual Students)
# ==========================================

literature_scout = Agent(
    role="Senior Academic Literature Scout",
    goal="Locate recent peer-reviewed papers, open-access articles, and whitepapers on {research_topic}.",
    backstory="""You are a meticulous Master's student who spends days reading academic databases. 
    You excel at looking through search results, reading abstracts, and extracting 
    the exact methodologies, systems, and algorithms used in recent publications (2024-2026).""",
    verbose=True,
    tools=[search_tool],
    allow_delegation=False
)

academic_analyst = Agent(
    role="Principal Research Gap Analyst",
    goal="Critique the collected literature and identify highly specific research gaps for a master's thesis.",
    backstory="""You are an analytical researcher with an eye for spotting what other scientists missed. 
    You look closely at the limitations, future work directions, assumptions, or performance bottlenecks 
    in existing systems to find gaps a student could realistically build a thesis around.""",
    verbose=True,
    allow_delegation=False
)

# ==========================================
# 3. DEFINE THE TASKS (The Action Items)
# ==========================================

scout_task = Task(
    description="""Search the web for recent research (2024-2026) regarding the topic: '{research_topic}'.
    Find at least 3-4 highly relevant papers. For each paper, extract the title, authors, 
    the core approach they took, and summarize what their system achieved.""",
    expected_output="A structured summary log of the top 3-4 papers found, mapping out their approaches.",
    agent=literature_scout
)

analyst_task = Task(
    description="""Review the literature summary log compiled by the Literature Scout. 
    Identify 3 distinct 'Research Gaps' or limitations across those approaches. 
    For each gap, pitch a concrete Master's Thesis direction. Include a suggested thesis title, 
    the technical problem to solve, and the potential methodology to use.""",
    expected_output="""A polished markdown thesis proposal document with 3 target directions. 
    Each direction must include: 
    1. Proposed Title 
    2. The Literature Background (Why it matters) 
    3. The Specific Research Gap
    4. Suggested Implementation Strategy.""",
    agent=academic_analyst
)

# ==========================================
# 4. LAUNCH THE CREW
# ==========================================
thesis_crew = Crew(
    agents=[literature_scout, academic_analyst],
    tasks=[scout_task, analyst_task],
    process=Process.sequential, # Task 1 must complete before Task 2 reads the data
    verbose=True
)

if __name__ == "__main__":
    # Input your broad research domain here
    target_topic = "Continuous Behavioral Authentication in AR/VR Headsets using IMU sensors"
    
    print(f"🚀 Kicking off autonomous thesis exploration for: '{target_topic}'...")
    final_report = thesis_crew.kickoff(inputs={"research_topic": target_topic})
    
    print("\n\n🎯 FINAL THESIS BLUEPRINT REPORT:")
    print(final_report)