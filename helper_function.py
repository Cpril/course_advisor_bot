from openai import OpenAI
from typing import Literal
from pydantic import BaseModel
from pydantic import ValidationError
import json
import requests
TEST = False

# ----------- Load Course Catalog Data --------------
sections_json_url = "https://cs.calvin.edu/courses/cs/375/25sp/notebooks/AY25FA25_Sections.json"
sections_json = requests.get(sections_json_url)
sections_json.raise_for_status()
sections = sections_json.json()
if TEST == True:
    example_section = next(section for section in sections if section['SectionName'].startswith('CS 108'))
    print(example_section)


# ---------- Reorganize Course Descriptions BY Course --------------
course_descriptions = {
    section['SectionName'].split('-', 1)[0].strip(): (section["SectionTitle"], section["CourseDescription"])
    for section in sections
    if "CourseDescription" in section
    and section.get('AcademicLevel') == 'Undergraduate'
    and section.get('Campus') == 'Grand Rapids Campus'
}
if TEST == True:
    print("Found", len(course_descriptions), "courses")
    print(course_descriptions["CS 108"])

# ---------- Initialize OpenAI Client --------------
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
model = "gemma3:1b-it-qat"

# ---------- Search Interests Define Schema --------------
class SearchTool(BaseModel):
    tool_name: Literal["search_course_catalog"] = "search_course_catalog"
    thinking: str
    queries: list[str]

# ---------- Make api call to the model with the schema --------------
def get_search_queries(interests: str, model: str = "gemma3:1b-it-qat", temperature: float = 0.5) -> SearchTool:
    system_prompt = """
You are a course advisor assistant.
Return ONLY valid JSON with these keys:
- tool_name: always "search_course_catalog"
- thinking: a short explanation of why these courses might be relevant
- queries: a list of 5 - 10 specific search queries for the course catalog

Rules:
- Assume that queries will be run against a specific course catalog, no generic words like "course" or "department".
- JSON output only (no extra text)
- Each query would match the title of specific courses in an undergraduate program
"""

    user_prompt = f'Student interest: "{interests}"'

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )

    raw_output = response.choices[0].message.content

    # --- Clean JSON if wrapped in code fences ---
    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        if raw_output.startswith("json"):
            raw_output = raw_output[len("json"):].strip()

    try:
        return SearchTool.model_validate_json(raw_output)
    except ValidationError as e:
        print("❌ JSON validation failed:", e)
        print("⚠️ Falling back to manual JSON load...")
        data = json.loads(raw_output)
        return SearchTool(**data)
    
# ---------- Search Courses --------------
def search_courses(query: str):
    """
    Search for courses that match the query.
    """
    query = query.lower()
    matches = []
    for course, (title, description) in course_descriptions.items():
        if query in title.lower() or query in description.lower():
            matches.append((course, title)) # I deleted description for now
    return matches
if TEST == True:
    print("Search results for 'programming':")
    print(search_courses("programming"))

# ---------- find courses matching the queries --------------
def find_courses_matching_queries(queries: list[str]):
    """
    Find courses that match any of the queries.
    Right now, it returns a bunch of courses when the queries are too vague, 
    e.g. "art" or "AI".
    """
    return set(
        course
        for query in queries
        for course in search_courses(query)
    )
if TEST == True:
    print("Courses matching queries ['programming', 'art']:")
    print(find_courses_matching_queries(["programming", "art"]))

# ---------- Recommendation Output --------------
class CourseRecommendation(BaseModel):
    course_code: str
    course_title: str
    course_description: str
    reasoning: str

class RecommendTool(BaseModel):
    tool_name: Literal["recommend_course"] = "recommend_course"
    thinking: str
    recommendations: list[CourseRecommendation]

def get_recommendations(interests: str, matched_courses: list[tuple[str, str, str]], 
                        model: str = "gemma3:1b-it-qat", temperature: float = 0.5) -> RecommendTool:
    """
    Ask the LLM to recommend specific courses (with reasoning) from matched_courses.
    """
    # Format candidate courses for prompt
    formatted_courses = "\n".join(
        f"- {cid}: {title}\n  {desc}" for cid, title, desc in matched_courses
    )

    system_prompt = """
Your job is to recommend courses based on the student's interests.
Return ONLY valid JSON matching the RecommendTool schema:
- tool_name: always "recommend_course"
- thinking: a short thought about how you are making the recommendations
- recommendations: a list of 2-5 most relevant CourseRecommendation objects, each with:
    * course_code
    * course_title
    * course_description: summarize to 1 sentence
    * reasoning (why this course is relevant to the student)

Rules:
- JSON output only (no extra text)
- Only choose from the candidate courses provided, do not make up new courses
"""

    user_prompt = f"""
Student interests: "{interests}"

Candidate courses to choose from:
{formatted_courses}

"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature,
    )

    raw_output = response.choices[0].message.content

    # --- Clean JSON if wrapped in code fences ---
    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        if raw_output.startswith("json"):
            raw_output = raw_output[len("json"):].strip()

    return RecommendTool.model_validate_json(raw_output)

# ---------- Example usage --------------

if __name__ == "__main__":
    if TEST == True:
        interests = "I am interested in Programming."
        search_tool = get_search_queries(interests)
        # print("Student Interest Queries:", search_tool.queries)

        matched = find_courses_matching_queries(search_tool.queries)
        # print(matched)

        recs = get_recommendations(interests,matched)
        print("Recommendations:")
        for rec in recs.recommendations:
            print(f"- {rec.course_code}: {rec.course_title}")
            print(f"  {rec.course_description}")
            print(f"  Reasoning: {rec.reasoning}")
