import streamlit as st
import helper_function as hf

st.set_page_config(page_title = "Course Advisor Bot", page_icon = "🎓", layout = "wide")
st.title("🎓 Course Advisor Bot")
st.write("Welcome to the Course Advisor Bot! This tool helps you find courses that match your interests. Enter your interests, and get personalized course recommendations.")

interests = st.text_input("What are your interests? (e.g., programming, art, AI)", "")

if st.button("Find Courses") and interests.strip():
    with st.spinner("Analyzing your interests..."):
        # Part 1: search queries
        search_tool = hf.get_search_queries(interests)
        st.subheader("🤔 Thinking")
        st.write(search_tool.thinking)

        # Part 2: match courses
        matches = hf.find_courses_matching_queries(search_tool.queries)

        # Part 3: recommendations
        recs = hf.get_recommendations(interests, matches)
        st.subheader("✨ Recommendations")
        st.write(recs.thinking)
        for r in recs.recommendations:
            st.markdown(f"**{r.course_code}: {r.course_title}**")
            st.write(r.course_description)
            st.info(r.reasoning)